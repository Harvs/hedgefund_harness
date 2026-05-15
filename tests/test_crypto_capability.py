import pandas as pd
import pytest
import requests

from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.instruments import resolve_instrument, validate_coingecko_id
from tradingagents.returns import fetch_returns


def test_validate_coingecko_id_accepts_exact_ids():
    assert validate_coingecko_id("bitcoin") == "bitcoin"
    assert validate_coingecko_id("wrapped-bitcoin") == "wrapped-bitcoin"


@pytest.mark.parametrize("value", ["bitcoin/usd", "../bitcoin", "bitcoin_", "-bitcoin"])
def test_validate_coingecko_id_rejects_aliases_and_unsafe_values(value):
    with pytest.raises(ValueError):
        validate_coingecko_id(value)


def test_resolve_crypto_instrument_uses_safe_storage_key():
    instrument = resolve_instrument("bitcoin", {"asset_class": "crypto", "crypto_quote_currency": "usd"})
    assert instrument.asset_class == "crypto"
    assert instrument.coin_id == "bitcoin"
    assert instrument.safe_storage_key == "crypto-bitcoin"


def test_crypto_routing_uses_coingecko_without_equity_fallback(monkeypatch):
    set_config({"asset_class": "crypto", "crypto_data_vendor": "coingecko", "crypto_quote_currency": "usd"})
    monkeypatch.setattr(
        "tradingagents.dataflows.interface.get_crypto_tokenomics",
        lambda ticker, curr_date: f"tokenomics:{ticker}:{curr_date}",
    )
    monkeypatch.setitem(
        __import__("tradingagents.dataflows.interface", fromlist=["VENDOR_METHODS"]).VENDOR_METHODS["get_fundamentals"],
        "coingecko",
        lambda ticker, curr_date: f"tokenomics:{ticker}:{curr_date}",
    )
    assert route_to_vendor("get_fundamentals", "bitcoin", "2024-01-01") == "tokenomics:bitcoin:2024-01-01"


def test_crypto_tokenomics_formatting(monkeypatch):
    from tradingagents.dataflows import coingecko

    set_config({"asset_class": "crypto", "crypto_quote_currency": "usd"})
    monkeypatch.setattr(
        coingecko,
        "_get_json",
        lambda path, params: {
            "id": "bitcoin",
            "name": "Bitcoin",
            "symbol": "btc",
            "market_cap_rank": 1,
            "market_data": {
                "market_cap": {"usd": 100},
                "total_volume": {"usd": 10},
                "circulating_supply": 19,
                "total_supply": 21,
                "max_supply": 21,
                "fully_diluted_valuation": {"usd": 110},
            },
        },
    )
    report = coingecko.get_crypto_tokenomics("bitcoin", "2024-01-01")
    assert "CoinGecko tokenomics" in report
    assert "Bitcoin" in report
    assert "Market cap" in report


def test_crypto_tokenomics_rate_limit_returns_unavailable_message(monkeypatch):
    from tradingagents.dataflows import coingecko

    set_config({"asset_class": "crypto", "crypto_quote_currency": "usd"})

    def raise_rate_limit(path, params):
        raise coingecko.CoinGeckoDataError("CoinGecko rate limit exceeded. Retry later or set COINGECKO_API_KEY.")

    monkeypatch.setattr(coingecko, "_get_json", raise_rate_limit)
    report = coingecko.get_crypto_tokenomics("bitcoin", "2024-01-01")
    assert "CoinGecko tokenomics data unavailable for 'bitcoin'" in report
    assert "rate limit exceeded" in report


def test_coingecko_no_key_retries_429_five_times(monkeypatch):
    from tradingagents.dataflows import coingecko

    class Response:
        status_code = 429
        ok = False
        text = ""
        headers = {}

    calls = []
    sleeps = []
    set_config({"coingecko_api_key": None})
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: calls.append((args, kwargs)) or Response())
    monkeypatch.setattr(coingecko.time, "sleep", sleeps.append)

    with pytest.raises(coingecko.CoinGeckoDataError):
        coingecko._get_json("/coins/bitcoin")

    assert len(calls) == 5
    assert sleeps == [1.0, 2.0, 4.0, 8.0]


def test_coingecko_retry_after_header_controls_backoff(monkeypatch):
    from tradingagents.dataflows import coingecko

    class Response:
        status_code = 429
        ok = False
        text = ""
        headers = {"Retry-After": "3"}

    sleeps = []
    set_config({"coingecko_api_key": None})
    monkeypatch.delenv("COINGECKO_API_KEY", raising=False)
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: Response())
    monkeypatch.setattr(coingecko.time, "sleep", sleeps.append)

    with pytest.raises(coingecko.CoinGeckoDataError):
        coingecko._get_json("/coins/bitcoin")

    assert sleeps == [3.0, 3.0, 3.0, 3.0]


def test_coingecko_key_mode_retries_429_twice(monkeypatch):
    from tradingagents.dataflows import coingecko

    class Response:
        status_code = 429
        ok = False
        text = ""
        headers = {}

    calls = []
    sleeps = []
    set_config({"coingecko_api_key": "demo-key"})
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: calls.append((args, kwargs)) or Response())
    monkeypatch.setattr(coingecko.time, "sleep", sleeps.append)

    with pytest.raises(coingecko.CoinGeckoDataError):
        coingecko._get_json("/coins/bitcoin")

    assert len(calls) == 2
    assert sleeps == [1.0]


def test_fetch_crypto_returns_benchmarks_non_btc_against_bitcoin(monkeypatch):
    def fake_load(coin_id, curr_date):
        prices = [100, 110, 120, 130, 140, 150] if coin_id == "ethereum" else [100, 105, 110, 115, 120, 125]
        return pd.DataFrame({
            "Date": pd.date_range("2024-01-01", periods=6, freq="D"),
            "Close": prices,
        })

    monkeypatch.setattr("tradingagents.returns.load_crypto_ohlcv", fake_load)
    raw, alpha, days = fetch_returns(
        "ethereum",
        "2024-01-01",
        {"asset_class": "crypto", "crypto_benchmark_coin_id": "bitcoin"},
        holding_days=5,
    )
    assert raw == pytest.approx(0.5)
    assert alpha == pytest.approx(0.25)
    assert days == 5


def test_fetch_crypto_returns_btc_uses_raw_only(monkeypatch):
    monkeypatch.setattr(
        "tradingagents.returns.load_crypto_ohlcv",
        lambda coin_id, curr_date: pd.DataFrame({"Date": pd.date_range("2024-01-01", periods=2), "Close": [100, 110]}),
    )
    raw, alpha, days = fetch_returns(
        "bitcoin",
        "2024-01-01",
        {"asset_class": "crypto", "crypto_benchmark_coin_id": "bitcoin"},
        holding_days=1,
    )
    assert raw == pytest.approx(0.1)
    assert alpha is None
    assert days == 1
