"""Ticker metrics workflow.

Builds a scalar metrics snapshot for the ticker drill-down screen.
The screen never imports from marketdata or analysis directly — this module
is the single source of truth for ticker-detail data.
"""
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from analysis.market_analysis import calculate_relative_strength
from analysis.technical_analysis import calculate_rsi, calculate_sma
from config.settings import TickerDetailConfig
from core.quote import Quote
from marketdata.service import get_data_service

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class TickerMetrics:
    """Scalar metrics snapshot for a single ticker."""
    ticker: str
    quote: Optional[Quote]              # today's price, change, volume
    high_52w: Optional[float]
    low_52w: Optional[float]
    range_position_pct: Optional[float] # 0-100, where 100 = at 52W high
    sma_20: Optional[float]
    sma_50: Optional[float]
    sma_200: Optional[float]
    pct_vs_sma_20: Optional[float]      # signed % distance of price above SMA
    pct_vs_sma_50: Optional[float]
    pct_vs_sma_200: Optional[float]
    rsi_14: Optional[float]
    rsi_regime: Optional[str]           # "overbought" | "neutral" | "oversold"
    rs_spy_1m: Optional[float]          # 21-day RS vs SPY, in percent
    as_of: datetime
    error: Optional[str] = None


def build_ticker_metrics(
    ticker: str,
    config: TickerDetailConfig,
    data_service=None,
) -> TickerMetrics:
    """Build a scalar metrics snapshot for a single ticker.

    Fetches ~260 days of daily OHLCV for the ticker plus SPY (for RS),
    computes the scalars listed in TickerMetrics, returns. Any per-field
    failure leaves that field None and continues; overall fetch failure
    sets `error` and leaves all fields None.

    No yfinance.Ticker.info call. The screen header uses the ticker symbol only.
    """
    data_service = data_service or get_data_service()
    now = datetime.now()
    ticker = ticker.upper()

    end_date = now.date()
    # Overshoot by 1.5x to guarantee enough trading days for SMA-200
    start_date = end_date - timedelta(days=int(260 * 1.5))

    # ── Fetch quote ──────────────────────────────────────────────────────────
    quote: Optional[Quote] = None
    try:
        quote = data_service.get_live_quote(ticker)
    except Exception as exc:
        log.warning("get_live_quote(%s) failed: %s", ticker, exc)

    # ── Fetch ticker history ─────────────────────────────────────────────────
    history: Optional[pd.DataFrame] = None
    try:
        df = data_service.get_historical_ohlcv(ticker, start_date, end_date, interval="1d")
        if df is not None and not df.empty:
            history = df
    except Exception as exc:
        log.warning("get_historical_ohlcv(%s) failed: %s", ticker, exc)

    if history is None and quote is None:
        return TickerMetrics(
            ticker=ticker,
            quote=None,
            high_52w=None,
            low_52w=None,
            range_position_pct=None,
            sma_20=None,
            sma_50=None,
            sma_200=None,
            pct_vs_sma_20=None,
            pct_vs_sma_50=None,
            pct_vs_sma_200=None,
            rsi_14=None,
            rsi_regime=None,
            rs_spy_1m=None,
            as_of=now,
            error=f"Ticker not found or no data: {ticker}",
        )

    # ── 52-week range ────────────────────────────────────────────────────────
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    range_position_pct: Optional[float] = None

    if history is not None and len(history) >= 5:
        try:
            high_52w = float(history["High"].tail(252).max())
            low_52w = float(history["Low"].tail(252).min())
            price = quote.price if quote is not None else None
            if price is not None and high_52w is not None and low_52w is not None:
                rng = high_52w - low_52w
                if rng > 0:
                    range_position_pct = max(0.0, min(100.0, (price - low_52w) / rng * 100))
        except Exception as exc:
            log.warning("52w range computation failed for %s: %s", ticker, exc)

    # ── SMAs ─────────────────────────────────────────────────────────────────
    sma_map: dict[int, Optional[float]] = {20: None, 50: None, 200: None}
    pct_map: dict[int, Optional[float]] = {20: None, 50: None, 200: None}

    if history is not None:
        price = quote.price if quote is not None else None
        for w in (20, 50, 200):
            if len(history) < w:
                continue
            try:
                sma_series = calculate_sma(history["Close"], window=w)
                sma_val = float(sma_series.iloc[-1])
                sma_map[w] = sma_val
                if price is not None and sma_val != 0:
                    pct_map[w] = (price - sma_val) / sma_val * 100
            except Exception as exc:
                log.warning("SMA-%d computation failed for %s: %s", w, ticker, exc)

    # ── RSI ───────────────────────────────────────────────────────────────────
    rsi_14: Optional[float] = None
    rsi_regime: Optional[str] = None

    if history is not None and len(history) >= config.rsi_window + 1:
        try:
            rsi_series = calculate_rsi(history["Close"], window=config.rsi_window)
            last_rsi = rsi_series.iloc[-1]
            if not pd.isna(last_rsi):
                rsi_14 = float(last_rsi)
                if rsi_14 < config.rsi_oversold:
                    rsi_regime = "oversold"
                elif rsi_14 > config.rsi_overbought:
                    rsi_regime = "overbought"
                else:
                    rsi_regime = "neutral"
        except Exception as exc:
            log.warning("RSI computation failed for %s: %s", ticker, exc)

    # ── RS vs SPY (21-day) ───────────────────────────────────────────────────
    rs_spy_1m: Optional[float] = None

    if history is not None and len(history) >= 22:
        try:
            spy_df = data_service.get_historical_ohlcv("SPY", start_date, end_date, interval="1d")
            if spy_df is not None and not spy_df.empty and len(spy_df) >= 22:
                ticker_returns = history["Close"].pct_change().dropna()
                spy_returns = spy_df["Close"].pct_change().dropna()
                # Align on common dates
                common_idx = ticker_returns.index.intersection(spy_returns.index)
                if len(common_idx) >= 21:
                    t_aligned = ticker_returns.loc[common_idx]
                    s_aligned = spy_returns.loc[common_idx]
                    rs_val, _ = calculate_relative_strength(t_aligned, s_aligned, 21)
                    rs_spy_1m = rs_val * 100  # convert decimal to percent
        except Exception as exc:
            log.warning("RS vs SPY computation failed for %s: %s", ticker, exc)

    return TickerMetrics(
        ticker=ticker,
        quote=quote,
        high_52w=high_52w,
        low_52w=low_52w,
        range_position_pct=range_position_pct,
        sma_20=sma_map[20],
        sma_50=sma_map[50],
        sma_200=sma_map[200],
        pct_vs_sma_20=pct_map[20],
        pct_vs_sma_50=pct_map[50],
        pct_vs_sma_200=pct_map[200],
        rsi_14=rsi_14,
        rsi_regime=rsi_regime,
        rs_spy_1m=rs_spy_1m,
        as_of=now,
        error=None,
    )
