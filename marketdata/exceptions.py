class DataSourceError(Exception):
    """Raised when a market data source fails to fulfill a request."""
    pass


class SourceUnavailableError(DataSourceError):
    """Raised when a source is not available (e.g., Schwab token expired)."""
    pass


class UnsupportedIntervalError(DataSourceError):
    """Raised when a source does not support the requested interval."""
    pass
