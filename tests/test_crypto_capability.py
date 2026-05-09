import pandas as pd
import pytest

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
