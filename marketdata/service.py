import logging
from datetime import date
from typing import Optional

import pandas as pd

from config.settings import Settings
from core.quote import Quote
from marketdata.cache import LocalCache
from marketdata.exceptions import DataSourceError, SourceUnavailableError, UnsupportedIntervalError
from marketdata.sources.base import MarketDataSource
from marketdata.sources.schwab_source import SchwabSource
from marketdata.sources.yfinance_source import YFinanceSource

logger = logging.getLogger(__name__)


class DataService:
    """Unified entry point for all market data needs.

    Consumers should always go through DataService rather than instantiating
    sources directly. The service handles cache lookup, source selection,
    and fallback logic.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._sources: dict = {
            'schwab': SchwabSource(),
            'yfinance': YFinanceSource(),
        }
        self._cache = LocalCache(settings.data_dir)

    def get_historical_ohlcv(
        self,
        ticker: str,
        start: date,
        end: date,
        interval: str = '1d',
        source: Optional[str] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data, using cache when possible.

        Routing logic when source is None:
          1. Try settings.preferred_source.
          2. If it doesn't support the interval, try the other source.
          3. If preferred source is unavailable (e.g. expired token),
             log a warning and fall back to the other source.
        """
        ticker = ticker.upper()

        if use_cache:
            cached = self._cache.get(ticker, interval, start, end)
            if cached is not None:
                logger.info(f"Cache hit for {ticker} {interval} {start}–{end}")
                return cached

        chosen = self._select_source(interval, source)
        logger.info(f"Fetching {ticker} {interval} {start}–{end} from {chosen.name}")
        df = chosen.get_historical_ohlcv(ticker, start, end, interval)

        if use_cache:
            self._cache.put(ticker, interval, start, end, df)

        return df

    def get_live_quote(
        self, ticker: str, source: Optional[str] = None
    ) -> Quote:
        """Fetch a single live quote."""
        chosen = self._select_source('1d', source)  # interval irrelevant for quotes
        return chosen.get_live_quote(ticker.upper())

    def get_live_quotes(
        self, tickers: list, source: Optional[str] = None
    ) -> dict:
        """Fetch live quotes for multiple tickers.

        Default implementation calls get_live_quote per ticker. Sources may
        override this method in the future for batch efficiency.
        """
        return {t.upper(): self.get_live_quote(t, source=source) for t in tickers}

    def _select_source(
        self, interval: str, requested: Optional[str]
    ) -> MarketDataSource:
        """Resolve which source to use given preferences and constraints."""
        if requested is not None:
            if requested not in self._sources:
                raise ValueError(f"Unknown source: {requested}")
            return self._sources[requested]

        preferred_name = self.settings.preferred_source
        preferred = self._sources[preferred_name]
        other_name = 'yfinance' if preferred_name == 'schwab' else 'schwab'
        other = self._sources[other_name]

        if not preferred.supports_interval(interval):
            logger.warning(
                f"{preferred.name} does not support interval '{interval}', "
                f"falling back to {other.name}"
            )
            return other

        if not preferred.is_available():
            logger.warning(
                f"{preferred.name} is unavailable, falling back to {other.name}"
            )
            return other

        return preferred


_default_service: Optional[DataService] = None


def get_data_service() -> DataService:
    """Get or create the default DataService instance.

    Lazy-initialized so importing this module is cheap.
    Most callers should use this rather than constructing their own.
    """
    global _default_service
    if _default_service is None:
        _default_service = DataService(Settings.load())
    return _default_service
