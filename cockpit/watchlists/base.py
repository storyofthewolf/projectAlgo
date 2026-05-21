from abc import ABC, abstractmethod


class WatchlistProvider(ABC):
    """A source of watchlist definitions (not quotes).

    Implementations may load from local files (YAML), remote APIs (Schwab),
    or anywhere else. The cockpit aggregates all registered providers and
    namespaces watchlists by provider.
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Short stable identifier, e.g. 'yaml', 'schwab'. Lower-case."""

    @abstractmethod
    def list_watchlists(self) -> tuple[str, ...]:
        """Return names of available watchlists in this provider.

        Order is provider-defined and stable across calls (until reload).
        """

    @abstractmethod
    def get_tickers(self, watchlist_name: str) -> tuple[str, ...]:
        """Return ticker symbols (upper-case) for the named watchlist.

        Raises KeyError if the name doesn't exist in this provider.
        """

    @abstractmethod
    def reload(self) -> None:
        """Re-read the underlying source. Called on manual 'r' refresh."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider can currently serve requests.

        E.g. False for SchwabWatchlistProvider when unauthenticated.
        """
