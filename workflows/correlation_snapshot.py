"""Correlation snapshot workflow.

Composes load_aligned_returns + calculate_correlation_matrix + summarize_correlations
into a typed snapshot consumed by both the home correlation panel and the
correlation deep-dive screen.

Pure data in, pure data out. No Textual, no asyncio imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from analysis.market_analysis import (
    calculate_correlation_matrix,
    load_aligned_returns,
    summarize_correlations,
)
from marketdata.service import get_data_service

_VALID_METHODS = ("pearson", "spearman", "kendall")
_MAX_LOOKBACK_DAYS = 3 * 365  # calendar-day safety cap


@dataclass(frozen=True)
class RankedPair:
    """One entry in the ranked-pair list."""
    ticker_a: str
    ticker_b: str
    correlation: float


@dataclass(frozen=True, eq=False)
class CorrelationSnapshot:
    """Typed result of build_correlation_snapshot.

    The matrix carries tickers as both row and column index. Tickers that
    failed to load are absent from the matrix and recorded in failed_tickers.
    """
    tickers: tuple[str, ...]
    requested_tickers: tuple[str, ...]
    failed_tickers: tuple[str, ...]
    method: str
    lookback_days: int
    matrix: Optional[pd.DataFrame]
    ranked_pairs: tuple[RankedPair, ...]
    as_of: datetime
    error: Optional[str] = None


def build_correlation_snapshot(
    tickers: list[str],
    lookback_days: int,
    method: str = "pearson",
    data_service=None,
    now: Optional[datetime] = None,
) -> CorrelationSnapshot:
    """Build a correlation snapshot for the given tickers and lookback.

    Fetches aligned returns, computes the correlation matrix, and produces
    a ranked pair list. Per-ticker fetch failures are tolerated; catastrophic
    failure (< 2 surviving tickers) sets error and returns matrix=None.
    """
    if method not in _VALID_METHODS:
        raise ValueError(
            f"method '{method}' is not valid; must be one of {_VALID_METHODS}"
        )
    if lookback_days < 2:
        raise ValueError(
            f"lookback_days must be >= 2, got {lookback_days}"
        )

    service = data_service if data_service is not None else get_data_service()
    now = now or datetime.now()
    now_date = now.date()
    requested = tuple(tickers)

    # Calendar window: lookback_days * 1.5 to cover weekends/holidays, capped.
    calendar_days = min(int(lookback_days * 1.5) + 5, _MAX_LOOKBACK_DAYS)
    start_date = now_date - timedelta(days=calendar_days)

    # Fetch each ticker individually so we can track per-ticker failures.
    failed: list[str] = []
    surviving: list[str] = []
    for ticker in tickers:
        try:
            df = service.get_historical_ohlcv(ticker, start_date, now_date, interval="1d")
            if df.empty:
                raise ValueError(f"no data returned")
            surviving.append(ticker)
        except Exception as e:
            print(f"Warning: could not load {ticker} — skipping. ({e})")
            failed.append(ticker)

    def _error_snap(msg: str) -> CorrelationSnapshot:
        return CorrelationSnapshot(
            tickers=(),
            requested_tickers=requested,
            failed_tickers=tuple(failed),
            method=method,
            lookback_days=lookback_days,
            matrix=None,
            ranked_pairs=(),
            as_of=now,
            error=msg,
        )

    if len(surviving) < 2:
        return _error_snap(
            f"insufficient data after alignment: only {len(surviving)} ticker(s) loaded"
        )

    # Single aligned fetch for all surviving tickers.
    returns_df = load_aligned_returns(
        surviving,
        start_date.strftime("%Y-%m-%d"),
        now_date.strftime("%Y-%m-%d"),
        interval="1d",
        data_service=service,
    )

    if returns_df.empty or returns_df.shape[1] < 2:
        return _error_snap("insufficient data after alignment")

    # Truncate to the most recent lookback_days trading days.
    returns_df = returns_df.iloc[-lookback_days:]

    if returns_df.shape[0] < 2:
        return _error_snap(
            f"insufficient rows after truncation: got {returns_df.shape[0]}"
        )

    actual_tickers = tuple(returns_df.columns.tolist())

    matrix = calculate_correlation_matrix(returns_df, method=method)

    pairs_df = summarize_correlations(matrix)
    ranked_pairs = tuple(
        RankedPair(
            ticker_a=row["ticker_a"],
            ticker_b=row["ticker_b"],
            correlation=float(row["correlation"]),
        )
        for _, row in pairs_df.iterrows()
    )

    return CorrelationSnapshot(
        tickers=actual_tickers,
        requested_tickers=requested,
        failed_tickers=tuple(failed),
        method=method,
        lookback_days=lookback_days,
        matrix=matrix,
        ranked_pairs=ranked_pairs,
        as_of=now,
    )
