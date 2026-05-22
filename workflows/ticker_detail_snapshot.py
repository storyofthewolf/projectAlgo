"""Ticker drill-down workflow.

Builds a full snapshot (quote + history + indicators + stats) for the
drill-down screen, and a lightweight quote-only refresh for the 30s repoll.

The screen never imports from marketdata or analysis directly — this module
is the single source of truth for ticker-detail data.
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from analysis.technical_analysis import calculate_rsi, calculate_sma
from config.settings import TickerDetailConfig
from core.quote import Quote
from marketdata.service import get_data_service

log = logging.getLogger(__name__)


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class IndicatorReadout:
    """SMA + RSI values plus % distance from current price."""
    sma_values: dict          # {20: 185.21, 50: 181.84, 200: 175.32}
    sma_vs_price_pct: dict    # {20: +1.19, 50: +3.07, 200: +6.90}
    rsi: Optional[float]
    rsi_regime: str           # "oversold" | "neutral" | "overbought" | "unknown"


@dataclass(frozen=True)
class TickerStats:
    """Derived stats from history + quote."""
    week_52_high: Optional[float]
    week_52_low: Optional[float]
    week_52_percentile: Optional[float]   # 0-100; where current price sits in 52w range
    day_high: Optional[float]
    day_low: Optional[float]
    avg_volume_30d: Optional[float]


@dataclass(frozen=True, eq=False)
class TickerDetailSnapshot:
    ticker: str
    name: Optional[str]           # company long name; None if unavailable
    quote: Optional[Quote]
    history: Optional[pd.DataFrame]  # OHLCV; index is DatetimeIndex; full lookback length
    indicators: Optional[IndicatorReadout]
    stats: Optional[TickerStats]
    error: Optional[str]          # only set on catastrophic failure
    quote_stale: bool             # True if quote repoll failed and we kept the old one
    timestamp: datetime           # when this snapshot was constructed


# ── Indicator computation ────────────────────────────────────────────────────

def _compute_indicators(
    history: pd.DataFrame,
    quote: Optional[Quote],
    config: TickerDetailConfig,
) -> IndicatorReadout:
    sma_values: dict = {}
    sma_vs_price_pct: dict = {}

    for w in config.sma_windows:
        if len(history) < w:
            sma_values[w] = None
            sma_vs_price_pct[w] = None
        else:
            sma_series = calculate_sma(history["Close"], window=w)
            sma = float(sma_series.iloc[-1])
            sma_values[w] = sma
            if quote is not None and sma != 0:
                sma_vs_price_pct[w] = (quote.price - sma) / sma * 100
            else:
                sma_vs_price_pct[w] = None

    rsi: Optional[float] = None
    rsi_regime = "unknown"

    if len(history) >= config.rsi_window + 1:
        rsi_series = calculate_rsi(history["Close"], window=config.rsi_window)
        last_rsi = rsi_series.iloc[-1]
        if not pd.isna(last_rsi):
            rsi = float(last_rsi)

    if rsi is None:
        rsi_regime = "unknown"
    elif rsi < config.rsi_oversold:
        rsi_regime = "oversold"
    elif rsi > config.rsi_overbought:
        rsi_regime = "overbought"
    else:
        rsi_regime = "neutral"

    return IndicatorReadout(
        sma_values=sma_values,
        sma_vs_price_pct=sma_vs_price_pct,
        rsi=rsi,
        rsi_regime=rsi_regime,
    )


# ── Stats computation ────────────────────────────────────────────────────────

def _compute_stats(
    history: pd.DataFrame,
    quote: Optional[Quote],
) -> TickerStats:
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    week_52_percentile: Optional[float] = None

    if len(history) >= 5:
        week_52_high = float(history["High"].tail(252).max())
        week_52_low = float(history["Low"].tail(252).min())

        if quote is not None and week_52_high is not None and week_52_low is not None:
            rng = week_52_high - week_52_low
            if rng > 0:
                pct = (quote.price - week_52_low) / rng * 100
                week_52_percentile = max(0.0, min(100.0, pct))

    # Quote does not have day_high/day_low; use most recent bar's High/Low as proxy.
    # yfinance fast_info provides these but they are not surfaced through get_live_quote.
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    if len(history) >= 1:
        day_high = float(history["High"].iloc[-1])
        day_low = float(history["Low"].iloc[-1])

    avg_volume_30d: Optional[float] = None
    if len(history) >= 5:
        avg_volume_30d = float(history["Volume"].tail(30).mean())

    return TickerStats(
        week_52_high=week_52_high,
        week_52_low=week_52_low,
        week_52_percentile=week_52_percentile,
        day_high=day_high,
        day_low=day_low,
        avg_volume_30d=avg_volume_30d,
    )


# ── Name lookup ──────────────────────────────────────────────────────────────

def _fetch_ticker_name(ticker: str) -> Optional[str]:
    # Known data-layer leak: calls yfinance directly rather than through DataService.
    # The architecture forbids source-specific code outside marketdata/sources/, but
    # longName is cosmetic metadata not exposed by the MarketDataSource interface.
    # Approach (b) from the spec: documented exception, wrapped to never raise.
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        return info.get("longName") or info.get("shortName") or None
    except Exception:
        return None


# ── Builders ─────────────────────────────────────────────────────────────────

def build_ticker_detail_snapshot(
    ticker: str,
    config: TickerDetailConfig,
    data_service=None,
    now: Optional[datetime] = None,
) -> TickerDetailSnapshot:
    """Full build — quote + history + derived. Used on screen open and on r."""
    data_service = data_service or get_data_service()
    now = now or datetime.now()
    ticker = ticker.upper()

    # Fetch quote
    quote: Optional[Quote] = None
    try:
        quote = data_service.get_live_quote(ticker)
    except Exception as exc:
        log.warning("get_live_quote(%s) failed: %s", ticker, exc)

    # Fetch history — overshoot by 1.5× to ensure enough trading days
    end_date = now.date()
    start_date = end_date - timedelta(days=int(config.history_lookback_days * 1.5))
    history: Optional[pd.DataFrame] = None
    try:
        df = data_service.get_historical_ohlcv(ticker, start_date, end_date, interval="1d")
        if df is not None and not df.empty:
            history = df.tail(config.history_lookback_days)
        else:
            history = None
    except Exception as exc:
        log.warning("get_historical_ohlcv(%s) failed: %s", ticker, exc)
        history = None

    # Catastrophic failure: no data at all
    if history is None and quote is None:
        return TickerDetailSnapshot(
            ticker=ticker,
            name=None,
            quote=None,
            history=None,
            indicators=None,
            stats=None,
            error=f"Ticker not found: {ticker}",
            quote_stale=False,
            timestamp=now,
        )

    # Compute indicators and stats from history
    indicators: Optional[IndicatorReadout] = None
    stats: Optional[TickerStats] = None

    if history is not None:
        indicators = _compute_indicators(history, quote, config)
        stats = _compute_stats(history, quote)

    # Fetch company name (cosmetic; non-blocking; failure is acceptable)
    name = _fetch_ticker_name(ticker)

    return TickerDetailSnapshot(
        ticker=ticker,
        name=name,
        quote=quote,
        history=history,
        indicators=indicators,
        stats=stats,
        error=None,
        quote_stale=False,
        timestamp=now,
    )


def build_ticker_quote_snapshot(
    ticker: str,
    data_service=None,
    now: Optional[datetime] = None,
) -> Optional[Quote]:
    """Quote only — used by the 30s repoll. Returns None on failure."""
    data_service = data_service or get_data_service()
    try:
        return data_service.get_live_quote(ticker.upper())
    except Exception as exc:
        log.warning("build_ticker_quote_snapshot(%s) failed: %s", ticker, exc)
        return None
