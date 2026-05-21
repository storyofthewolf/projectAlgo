from .base import WatchlistProvider


class WatchlistRegistry:
    """Aggregates watchlists across multiple providers.

    Cycle order: providers in declaration order, watchlists within each
    provider in provider-defined order. yaml comes first, schwab second.
    """

    def __init__(self, providers: tuple[WatchlistProvider, ...]):
        self._providers = providers
        self._by_name: dict[str, WatchlistProvider] = {
            p.provider_name: p for p in providers
        }

    def cycle_order(self) -> tuple[tuple[str, str], ...]:
        """Return [(provider_name, watchlist_name), ...] in cycle order.

        Skips providers that report is_available() == False.
        """
        result: list[tuple[str, str]] = []
        for p in self._providers:
            if not p.is_available():
                continue
            for wl in p.list_watchlists():
                result.append((p.provider_name, wl))
        return tuple(result)

    def get_tickers(
        self, provider_name: str, watchlist_name: str
    ) -> tuple[str, ...]:
        """Look up tickers from the named provider+watchlist."""
        if provider_name not in self._by_name:
            raise KeyError(f"Unknown provider: '{provider_name}'")
        return self._by_name[provider_name].get_tickers(watchlist_name)

    def reload_all(self) -> None:
        """Reload every provider's underlying source."""
        for p in self._providers:
            p.reload()
