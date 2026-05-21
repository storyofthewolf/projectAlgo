from .base import WatchlistProvider


class SchwabWatchlistProvider(WatchlistProvider):
    """Pulls watchlists from Schwab's saved-watchlists API.

    Implementation deferred to Session 8 (requires Schwab OAuth).
    This stub exists so the WatchlistRegistry interface is complete now,
    and Session 8 only needs to fill in method bodies.
    """

    @property
    def provider_name(self) -> str:
        return 'schwab'

    def list_watchlists(self) -> tuple[str, ...]:
        return ()

    def get_tickers(self, watchlist_name: str) -> tuple[str, ...]:
        raise KeyError("SchwabWatchlistProvider not yet implemented (Session 8)")

    def reload(self) -> None:
        pass

    def is_available(self) -> bool:
        return False
