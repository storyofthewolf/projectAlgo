"""Watchlist snapshot workflow.

Pure data in, pure data out. No Textual, no asyncio imports.
Callable from a cockpit, a Dash app, or a plain Python script.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from core.quote import Quote
from marketdata.service import get_data_service


@dataclass(frozen=True)
class TickerRow:
    """One successfully-fetched ticker in a watchlist snapshot."""
    ticker: str
    quote: Quote
    sparkline_closes: tuple[float, ...]  # last N daily closes, oldest first
    last_volume: Optional[int]           # from last historical bar
    quote_source: str                    # 'yfinance' or 'schwab'
    history_source: str                  # 'yfinance' or 'schwab'


@dataclass(frozen=True)
class TickerError:
    """A ticker that failed to fetch."""
    ticker: str
    error_message: str
    failed_stage: str  # 'quote' or 'history'


@dataclass(frozen=True)
class WatchlistSnapshot:
    """Result of building a watchlist view at a point in time."""
    provider_name: str        # 'yaml' or 'schwab'
    watchlist_name: str       # e.g. 'default', 'semis'
    rows: tuple[TickerRow, ...]
    errors: tuple[TickerError, ...]
    timestamp: datetime
    quote_sources: frozenset[str]  # for panel-level source indicator


def _fetch_one_ticker(
    ticker: str,
    sparkline_days: int,
) -> tuple[Optional[TickerRow], Optional[TickerError]]:
    """Fetch quote + history for one ticker. Returns (row, None) or (None, error)."""
    service = get_data_service()
    today = date.today()
    # 1.5× multiplier accounts for weekends/holidays so we get at least sparkline_days bars
    start = today - timedelta(days=int(sparkline_days * 1.5))

    # Quote first — if this fails we report 'quote' stage
    try:
        quote = service.get_live_quote(ticker)
    except Exception as exc:
        return None, TickerError(
            ticker=ticker,
            error_message=str(exc),
            failed_stage='quote',
        )

    # History for sparkline
    try:
        df = service.get_historical_ohlcv(ticker, start=start, end=today, interval='1d')
        closes = tuple(float(v) for v in df['Close'].iloc[-sparkline_days:].tolist())
        last_volume = int(df['Volume'].iloc[-1]) if 'Volume' in df.columns and len(df) > 0 else None
        history_source = service._select_source('1d', None).name
    except Exception as exc:
        return None, TickerError(
            ticker=ticker,
            error_message=str(exc),
            failed_stage='history',
        )

    quote_source = service._select_source('1d', None).name

    row = TickerRow(
        ticker=ticker,
        quote=quote,
        sparkline_closes=closes,
        last_volume=last_volume,
        quote_source=quote_source,
        history_source=history_source,
    )
    return row, None


def build_watchlist_snapshot(
    provider_name: str,
    watchlist_name: str,
    tickers: tuple[str, ...],
    *,
    sparkline_days: int = 30,
) -> WatchlistSnapshot:
    """Build a watchlist snapshot.

    Per-ticker errors are returned as TickerError entries, NOT raised.
    Configuration errors (empty ticker list, etc.) raise ValueError.
    """
    if not tickers:
        raise ValueError(
            f"Watchlist '{provider_name}/{watchlist_name}' has no tickers."
        )

    # Timestamp at start of build, not end
    timestamp = datetime.now()

    rows: list[TickerRow] = []
    errors: list[TickerError] = []

    for ticker in tickers:
        row, error = _fetch_one_ticker(ticker, sparkline_days)
        if row is not None:
            rows.append(row)
        else:
            errors.append(error)

    if rows and len(errors) == len(tickers):
        import logging
        logging.getLogger(__name__).warning(
            f"All tickers failed for watchlist '{provider_name}/{watchlist_name}'. "
            "Possible network outage or DataService-level problem."
        )

    quote_sources = frozenset(r.quote_source for r in rows)

    return WatchlistSnapshot(
        provider_name=provider_name,
        watchlist_name=watchlist_name,
        rows=tuple(rows),
        errors=tuple(errors),
        timestamp=timestamp,
        quote_sources=quote_sources,
    )
