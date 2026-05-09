import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Dict, List

import pandas as pd
import requests
from stockstats import wrap

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.stockstats_utils import _clean_dataframe
from tradingagents.dataflows.utils import safe_ticker_component
from tradingagents.instruments import validate_coingecko_id


class CoinGeckoDataError(RuntimeError):
    pass


def _api_base() -> str:
    return "https://api.coingecko.com/api/v3"


def _headers() -> Dict[str, str]:
    config = get_config()
    api_key = config.get("coingecko_api_key") or os.getenv("COINGECKO_API_KEY")
    headers = {"accept": "application/json"}
    if api_key:
        headers["x-cg-demo-api-key"] = api_key
    return headers


def _get_json(path: str, params: Dict[str, Any] | None = None) -> Any:
    try:
        response = requests.get(f"{_api_base()}{path}", params=params or {}, headers=_headers(), timeout=30)
    except requests.RequestException as exc:
        raise CoinGeckoDataError(f"CoinGecko request failed: {exc}") from exc
    if response.status_code == 429:
        raise CoinGeckoDataError("CoinGecko rate limit exceeded. Retry later or set COINGECKO_API_KEY.")
    if response.status_code == 404:
        raise CoinGeckoDataError("CoinGecko id was not found. Use the exact CoinGecko coin id.")
    if not response.ok:
        raise CoinGeckoDataError(f"CoinGecko request failed with HTTP {response.status_code}: {response.text[:300]}")
    return response.json()


def _timestamp(date_text: str) -> int:
    dt = datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _normalize_market_chart_rows(prices: List[List[float]], market_caps: List[List[float]], volumes: List[List[float]]) -> pd.DataFrame:
    if not prices:
        raise CoinGeckoDataError("CoinGecko returned no price history for the requested range.")
    price_df = pd.DataFrame(prices, columns=["timestamp", "Close"])
    price_df["Date"] = pd.to_datetime(price_df["timestamp"], unit="ms", utc=True).dt.strftime("%Y-%m-%d")
    daily = price_df.groupby("Date", as_index=False)["Close"].agg(Open="first", High="max", Low="min", Close="last")
    volume_df = pd.DataFrame(volumes or [], columns=["timestamp", "Volume"])
    if not volume_df.empty:
        volume_df["Date"] = pd.to_datetime(volume_df["timestamp"], unit="ms", utc=True).dt.strftime("%Y-%m-%d")
        volume_df = volume_df.groupby("Date", as_index=False)["Volume"].sum()
        daily = daily.merge(volume_df, on="Date", how="left")
    else:
        daily["Volume"] = 0
    daily["Volume"] = daily["Volume"].fillna(0)
    daily = daily[["Date", "Open", "High", "Low", "Close", "Volume"]]
    return _clean_dataframe(daily)


def load_crypto_ohlcv(coin_id: str, curr_date: str) -> pd.DataFrame:
    coin_id = validate_coingecko_id(coin_id)
    config = get_config()
    quote_currency = str(config.get("crypto_quote_currency", "usd")).lower()
    safe_coin = safe_ticker_component(f"crypto-{coin_id}", max_len=128)
    curr_dt = pd.to_datetime(curr_date)
    today = pd.Timestamp.today().normalize()
    earliest_public_dt = today - pd.DateOffset(days=364)
    if curr_dt < earliest_public_dt:
        raise CoinGeckoDataError(
            f"CoinGecko public API only supports crypto historical data within the past 365 days. "
            f"Use a trade date on or after {earliest_public_dt.strftime('%Y-%m-%d')} or configure a paid CoinGecko plan."
        )
    start_dt = max(curr_dt - pd.DateOffset(days=364), earliest_public_dt)
    end_dt = min(curr_dt, today)
    start_str = start_dt.strftime("%Y-%m-%d")
    end_str = end_dt.strftime("%Y-%m-%d")
    os.makedirs(config["data_cache_dir"], exist_ok=True)
    data_file = os.path.join(config["data_cache_dir"], f"{safe_coin}-CoinGecko-{quote_currency}-{start_str}-{end_str}.csv")
    if os.path.exists(data_file):
        data = pd.read_csv(data_file, on_bad_lines="skip", encoding="utf-8")
    else:
        payload = _get_json(
            f"/coins/{coin_id}/market_chart/range",
            {"vs_currency": quote_currency, "from": _timestamp(start_str), "to": _timestamp(end_str)},
        )
        data = _normalize_market_chart_rows(
            payload.get("prices", []), payload.get("market_caps", []), payload.get("total_volumes", [])
        )
        data.to_csv(data_file, index=False, encoding="utf-8")
    data = _clean_dataframe(data)
    data = data[data["Date"] <= curr_dt]
    if data.empty:
        raise CoinGeckoDataError(f"No CoinGecko OHLCV history available for {coin_id} on or before {curr_date}.")
    return data


def get_crypto_ohlcv_data(
    coin_id: Annotated[str, "exact CoinGecko coin id"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    coin_id = validate_coingecko_id(coin_id)
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    try:
        data = load_crypto_ohlcv(coin_id, end_date)
    except CoinGeckoDataError as exc:
        return f"CoinGecko OHLCV data unavailable for '{coin_id}': {exc}"
    mask = (data["Date"] >= pd.to_datetime(start_date)) & (data["Date"] <= pd.to_datetime(end_date))
    filtered = data.loc[mask].copy()
    if filtered.empty:
        return f"No CoinGecko OHLCV data found for '{coin_id}' between {start_date} and {end_date}"
    quote_currency = str(get_config().get("crypto_quote_currency", "usd")).upper()
    csv_string = filtered.to_csv(index=False)
    header = f"# Crypto OHLCV data for {coin_id}/{quote_currency} from {start_date} to {end_date}\n"
    header += f"# Total records: {len(filtered)}\n"
    header += "# Source: CoinGecko aggregator-grade spot market data\n\n"
    return header + csv_string


def get_crypto_indicators_window(
    coin_id: Annotated[str, "exact CoinGecko coin id"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"],
) -> str:
    try:
        data = load_crypto_ohlcv(coin_id, curr_date)
    except CoinGeckoDataError as exc:
        return f"CoinGecko technical indicator data unavailable for '{coin_id}': {exc}"
    df = wrap(data.copy())
    df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")
    try:
        df[indicator]
    except Exception as exc:
        raise ValueError(f"Indicator {indicator} is not supported for CoinGecko OHLCV data: {exc}") from exc
    curr_dt = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_dt - timedelta(days=look_back_days)
    rows = df[(pd.to_datetime(df["Date"]) >= before) & (pd.to_datetime(df["Date"]) <= curr_dt)][["Date", indicator]]
    lines = [f"## {indicator} values for {coin_id}", "", "| Date | Value |", "|---|---|"]
    lines.extend(f"| {row['Date']} | {row[indicator]} |" for _, row in rows.iterrows())
    return "\n".join(lines)


def get_crypto_tokenomics(
    coin_id: Annotated[str, "exact CoinGecko coin id"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
) -> str:
    coin_id = validate_coingecko_id(coin_id)
    datetime.strptime(curr_date, "%Y-%m-%d")
    quote_currency = str(get_config().get("crypto_quote_currency", "usd")).lower()
    payload = _get_json(
        f"/coins/{coin_id}",
        {"localization": "false", "tickers": "false", "market_data": "true", "community_data": "false", "developer_data": "false", "sparkline": "false"},
    )
    market = payload.get("market_data", {})
    rows = [
        ("CoinGecko id", payload.get("id")),
        ("Name", payload.get("name")),
        ("Symbol", str(payload.get("symbol", "")).upper()),
        ("Market cap rank", payload.get("market_cap_rank")),
        (f"Market cap ({quote_currency.upper()})", market.get("market_cap", {}).get(quote_currency)),
        (f"24h volume ({quote_currency.upper()})", market.get("total_volume", {}).get(quote_currency)),
        ("Circulating supply", market.get("circulating_supply")),
        ("Total supply", market.get("total_supply")),
        ("Max supply", market.get("max_supply")),
        (f"Fully diluted valuation ({quote_currency.upper()})", market.get("fully_diluted_valuation", {}).get(quote_currency)),
    ]
    lines = [f"# CoinGecko tokenomics and market metadata for {coin_id} as of {curr_date}", "", "| Metric | Value |", "|---|---|"]
    lines.extend(f"| {metric} | {value if value is not None else 'N/A'} |" for metric, value in rows)
    lines.append("\nSource: CoinGecko aggregator-grade market data; not exchange-native execution data.")
    return "\n".join(lines)
