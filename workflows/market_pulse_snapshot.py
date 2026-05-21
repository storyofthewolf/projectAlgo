"""Market pulse snapshot workflow.

Pure data in, pure data out. No Textual, no asyncio imports.
Callable from the cockpit, a Dash app, or a plain Python script.
"""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

from config.settings import PulseTicker as PulseTickerConfig
from marketdata.service import get_data_service


@dataclass
class PulseTicker:
    """One ticker's data for the pulse panel."""
    symbol: str
    label: str
    format_type: str                          # "price", "index", or "yield"
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    previous_close: Optional[float] = None
    sparkline_values: list[float] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class PulseSnapshot:
    """Complete pulse panel state at a point in time."""
    tickers: list[PulseTicker]
    quote_source: str     # e.g. "yfinance"
    timestamp: str        # ISO format — time of fetch start


def _fetch_one(
    cfg: PulseTickerConfig,
    service,
    lookback_days: int,
) -> PulseTicker:
    """Fetch quote + history for one pulse ticker. Errors populate the error field."""
    today = date.today()
    start = today - timedelta(days=int(lookback_days * 1.5))

    result = PulseTicker(
        symbol=cfg.symbol,
        label=cfg.label,
        format_type=cfg.format,
    )

    try:
        quote = service.get_live_quote(cfg.symbol)
        result.price = quote.price
        result.previous_close = quote.previous_close
        result.change = quote.change
        result.change_pct = quote.change_pct
    except Exception as exc:
        result.error = str(exc)
        return result

    try:
        df = service.get_historical_ohlcv(cfg.symbol, start=start, end=today, interval='1d')
        closes = df['Close'].iloc[-lookback_days:].tolist()
        result.sparkline_values = [float(v) for v in closes]
    except Exception:
        # Sparkline failure is non-fatal — price data still shows
        pass

    return result


def build_pulse_snapshot(
    pulse_config,
    data_service=None,
    lookback_days: int = 30,
) -> PulseSnapshot:
    """Build a market pulse snapshot.

    pulse_config: list/tuple of PulseTicker config objects (from Settings).
    data_service: optional DataService instance; defaults to get_data_service().
    Per-ticker errors populate the PulseTicker.error field, not raised.
    """
    service = data_service if data_service is not None else get_data_service()
    timestamp = datetime.now().isoformat(timespec='seconds')

    tickers = [_fetch_one(cfg, service, lookback_days) for cfg in pulse_config]

    # Derive quote source from service selection (same logic as watchlist)
    try:
        quote_source = service._select_source('1d', None).name
    except Exception:
        quote_source = "unknown"

    return PulseSnapshot(
        tickers=tickers,
        quote_source=quote_source,
        timestamp=timestamp,
    )
