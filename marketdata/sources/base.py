from abc import ABC, abstractmethod
from datetime import date
import pandas as pd

from core.quote import Quote


class MarketDataSource(ABC):
    """Abstract base class for all market data sources.

    Implementations must return DataFrames with the canonical OHLCV shape:
    - DatetimeIndex
    - Columns: 'Open', 'High', 'Low', 'Close', 'Volume' (in that order)
    - All numeric columns as float64 except Volume which is int64
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short identifier for this source, e.g. 'schwab', 'yfinance'.
        Used for logging and cache file naming."""
        ...

    @abstractmethod
    def get_historical_ohlcv(
        self,
        ticker: str,
        start: date,
        end: date,
        interval: str,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data.

        Args:
            ticker: Ticker symbol (e.g. 'AAPL').
            start: Inclusive start date.
            end: Inclusive end date.
            interval: '1d', '1wk', '1mo', '1h', etc.

        Returns:
            DataFrame in canonical OHLCV shape (see class docstring).

        Raises:
            UnsupportedIntervalError: If this source cannot deliver the interval.
            SourceUnavailableError: If the source is currently unreachable.
            DataSourceError: For any other fetch failure.
        """
        ...

    @abstractmethod
    def get_live_quote(self, ticker: str) -> Quote:
        """Fetch the current (or most recent available) quote.

        Raises:
            SourceUnavailableError: If the source is unreachable.
            DataSourceError: For any other fetch failure.
        """
        ...

    @abstractmethod
    def supports_interval(self, interval: str) -> bool:
        """Return True if this source can deliver the given interval."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this source is currently usable.
        For Schwab, this means token is valid. For yfinance, this means
        internet is reachable (a lightweight check is fine here).

        Must NOT raise — return False for any unavailability condition."""
        ...
