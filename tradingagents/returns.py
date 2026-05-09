import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import yfinance as yf

from tradingagents.dataflows.coingecko import load_crypto_ohlcv

logger = logging.getLogger(__name__)


def _series_return(data: pd.DataFrame, holding_days: int) -> Tuple[Optional[float], Optional[int]]:
    if len(data) < 2:
        return None, None
    actual_days = min(holding_days, len(data) - 1)
    start = float(data["Close"].iloc[0])
    end = float(data["Close"].iloc[actual_days])
    if start == 0:
        return None, None
    return (end - start) / start, actual_days


def fetch_returns(identifier: str, trade_date: str, config: Dict[str, Any], holding_days: int = 5) -> Tuple[Optional[float], Optional[float], Optional[int]]:
    try:
        asset_class = config.get("asset_class", "equity")
        if asset_class == "crypto":
            trade_dt = pd.to_datetime(trade_date)
            end_dt = trade_dt + pd.DateOffset(days=holding_days + 1)
            coin = load_crypto_ohlcv(identifier, end_dt.strftime("%Y-%m-%d"))
            coin = coin[coin["Date"] >= trade_dt]
            raw, days = _series_return(coin, holding_days)
            if raw is None:
                return None, None, None
            benchmark_id = config.get("crypto_benchmark_coin_id", "bitcoin")
            if identifier == benchmark_id:
                return raw, None, days
            benchmark = load_crypto_ohlcv(benchmark_id, end_dt.strftime("%Y-%m-%d"))
            benchmark = benchmark[benchmark["Date"] >= trade_dt]
            bench_raw, bench_days = _series_return(benchmark, holding_days)
            if bench_raw is None:
                return raw, None, days
            return raw, raw - bench_raw, min(days, bench_days)

        start = datetime.strptime(trade_date, "%Y-%m-%d")
        end = start + timedelta(days=holding_days + 7)
        end_str = end.strftime("%Y-%m-%d")
        stock = yf.Ticker(identifier).history(start=trade_date, end=end_str)
        spy = yf.Ticker("SPY").history(start=trade_date, end=end_str)
        if len(stock) < 2 or len(spy) < 2:
            return None, None, None
        actual_days = min(holding_days, len(stock) - 1, len(spy) - 1)
        raw = float((stock["Close"].iloc[actual_days] - stock["Close"].iloc[0]) / stock["Close"].iloc[0])
        spy_ret = float((spy["Close"].iloc[actual_days] - spy["Close"].iloc[0]) / spy["Close"].iloc[0])
        return raw, raw - spy_ret, actual_days
    except Exception as e:
        logger.warning("Could not resolve outcome for %s on %s (will retry next run): %s", identifier, trade_date, e)
        return None, None, None
