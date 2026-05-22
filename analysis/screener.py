"""Cross-sectional screener engine.

Scans a universe of tickers and produces one row of metrics per ticker.
Pure computation: takes a ticker list, returns a DataFrame. The CLI
(scripts/scan.py) handles universe resolution, filtering, and display.

Metric columns produced per ticker:
    close                       last close price
    sma20, sma50, sma200        simple moving averages
    pct_sma20/50/200            % distance of close from each SMA
    rsi                         RSI(14)
    rsi_regime                  oversold / neutral / overbought / unknown
    ret_5d, ret_1m, ret_3m      trailing returns (%) over 5/21/63 trading days
    ret_ytd                     year-to-date return (%)
    volume                      last day's volume
    avg_vol                     30-day average volume
    vol_ratio                   last volume / avg_vol
    rs_spy_1m                   1-month return minus SPY's 1-month return (%)
"""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from analysis.technical_analysis import calculate_rsi, calculate_sma
from marketdata.service import get_data_service

log = logging.getLogger(__name__)

_BENCHMARK = "SPY"
_RSI_WINDOW = 14
_RSI_OVERSOLD = 30
_RSI_OVERBOUGHT = 70
_SMA_WINDOWS = (20, 50, 200)
# Trailing-return windows in trading days.
_RET_WINDOWS = {"ret_5d": 5, "ret_1m": 21, "ret_3m": 63}
# Bars to fetch — enough for SMA-200 plus headroom for weekends/holidays.
_LOOKBACK_CALENDAR_DAYS = 400


@dataclass
class ScanResult:
    """Outcome of a universe scan."""
    metrics: pd.DataFrame                       # one row per successful ticker
    failed: dict = field(default_factory=dict)  # ticker -> failure reason


def _trailing_return(closes: pd.Series, window: int) -> Optional[float]:
    """Percent return over the last `window` bars, or None if too short."""
    if len(closes) < window + 1:
        return None
    past = closes.iloc[-window - 1]
    last = closes.iloc[-1]
    if past == 0 or pd.isna(past) or pd.isna(last):
        return None
    return (last - past) / past * 100.0


def _ytd_return(closes: pd.Series, index: pd.DatetimeIndex) -> Optional[float]:
    """Percent return from the first bar of the current calendar year."""
    this_year = index[-1].year
    year_mask = index.year == this_year
    year_closes = closes[year_mask]
    if len(year_closes) < 2:
        return None
    first = year_closes.iloc[0]
    last = year_closes.iloc[-1]
    if first == 0 or pd.isna(first) or pd.isna(last):
        return None
    return (last - first) / first * 100.0


def _compute_row(ticker: str, df: pd.DataFrame, spy_ret_1m: Optional[float]) -> dict:
    """Build the metric dict for one ticker from its OHLCV history."""
    closes = df["Close"]
    index = df.index
    close = float(closes.iloc[-1])

    row: dict = {"ticker": ticker, "close": close}

    # SMAs and % distance from price
    for w in _SMA_WINDOWS:
        if len(closes) >= w:
            sma = float(calculate_sma(closes, window=w).iloc[-1])
            row[f"sma{w}"] = sma
            row[f"pct_sma{w}"] = (close - sma) / sma * 100.0 if sma else None
        else:
            row[f"sma{w}"] = None
            row[f"pct_sma{w}"] = None

    # RSI + regime
    rsi_val: Optional[float] = None
    if len(closes) >= _RSI_WINDOW + 1:
        last_rsi = calculate_rsi(closes, window=_RSI_WINDOW).iloc[-1]
        if not pd.isna(last_rsi):
            rsi_val = float(last_rsi)
    row["rsi"] = rsi_val
    if rsi_val is None:
        row["rsi_regime"] = "unknown"
    elif rsi_val < _RSI_OVERSOLD:
        row["rsi_regime"] = "oversold"
    elif rsi_val > _RSI_OVERBOUGHT:
        row["rsi_regime"] = "overbought"
    else:
        row["rsi_regime"] = "neutral"

    # Trailing returns
    for name, window in _RET_WINDOWS.items():
        row[name] = _trailing_return(closes, window)
    row["ret_ytd"] = _ytd_return(closes, index)

    # Volume
    volume = float(df["Volume"].iloc[-1])
    avg_vol = float(df["Volume"].tail(30).mean()) if len(df) >= 5 else None
    row["volume"] = volume
    row["avg_vol"] = avg_vol
    row["vol_ratio"] = volume / avg_vol if avg_vol else None

    # Relative strength vs SPY (1-month)
    if spy_ret_1m is not None and row["ret_1m"] is not None:
        row["rs_spy_1m"] = row["ret_1m"] - spy_ret_1m
    else:
        row["rs_spy_1m"] = None

    return row


def scan_universe(
    tickers: list[str],
    data_service=None,
    now: Optional[datetime] = None,
) -> ScanResult:
    """Scan a list of tickers; return a ScanResult with a metrics DataFrame.

    A ticker that fails to load or has too little history is recorded in
    `failed` and excluded from `metrics` — one bad ticker never kills the scan.
    The benchmark (SPY) is always fetched so rs_spy_1m can be computed.
    """
    data_service = data_service or get_data_service()
    now = now or datetime.now()
    end: date = now.date()
    start: date = end - timedelta(days=_LOOKBACK_CALENDAR_DAYS)

    # De-duplicate, upper-case, preserve order.
    seen: set[str] = set()
    universe: list[str] = []
    for t in tickers:
        tu = t.upper()
        if tu not in seen:
            seen.add(tu)
            universe.append(tu)

    def _fetch(ticker: str) -> Optional[pd.DataFrame]:
        df = data_service.get_historical_ohlcv(ticker, start, end, interval="1d")
        if df is None or df.empty:
            return None
        return df

    # Benchmark first — used for rs_spy_1m across the whole universe.
    spy_ret_1m: Optional[float] = None
    try:
        spy_df = _fetch(_BENCHMARK)
        if spy_df is not None:
            spy_ret_1m = _trailing_return(spy_df["Close"], _RET_WINDOWS["ret_1m"])
    except Exception as exc:
        log.warning("benchmark %s fetch failed: %s — rs_spy_1m will be blank", _BENCHMARK, exc)

    rows: list[dict] = []
    failed: dict = {}

    for ticker in universe:
        try:
            df = _fetch(ticker)
        except Exception as exc:
            failed[ticker] = f"fetch error: {exc}"
            continue
        if df is None:
            failed[ticker] = "no data"
            continue
        if len(df) < 2:
            failed[ticker] = f"insufficient history ({len(df)} bars)"
            continue
        try:
            rows.append(_compute_row(ticker, df, spy_ret_1m))
        except Exception as exc:
            failed[ticker] = f"compute error: {exc}"

    metrics = pd.DataFrame(rows)
    if not metrics.empty:
        metrics = metrics.set_index("ticker")
    return ScanResult(metrics=metrics, failed=failed)
