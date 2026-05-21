import logging
import warnings
from pathlib import Path

import yaml

from .base import WatchlistProvider

logger = logging.getLogger(__name__)


class YamlWatchlistProvider(WatchlistProvider):
    """Loads watchlists from a YAML file at a fixed path."""

    def __init__(self, path: Path):
        self._path = path
        self._lists: dict[str, tuple[str, ...]] = {}
        self._default: str = ""
        self.reload()

    @property
    def provider_name(self) -> str:
        return 'yaml'

    def list_watchlists(self) -> tuple[str, ...]:
        return tuple(self._lists.keys())

    def get_tickers(self, watchlist_name: str) -> tuple[str, ...]:
        if watchlist_name not in self._lists:
            raise KeyError(f"Watchlist '{watchlist_name}' not found in yaml provider")
        return self._lists[watchlist_name]

    def reload(self) -> None:
        if not self._path.exists():
            logger.warning(
                f"watchlists.yaml not found at {self._path}. "
                "Creating default file with SPY."
            )
            self._create_default()
            return

        with open(self._path, 'r') as f:
            raw = yaml.safe_load(f)

        if not isinstance(raw, dict):
            raise ValueError(f"watchlists.yaml must be a YAML mapping, got {type(raw)}")

        # Warn on unknown keys
        known = {'default', 'lists'}
        for key in raw:
            if key not in known:
                logger.warning(f"watchlists.yaml: unknown top-level key '{key}' (ignored)")

        lists_raw = raw.get('lists', {})
        if not isinstance(lists_raw, dict) or len(lists_raw) == 0:
            raise ValueError("watchlists.yaml has no watchlists defined")

        new_lists: dict[str, tuple[str, ...]] = {}
        for name, tickers in lists_raw.items():
            if not isinstance(name, str) or not name.strip():
                raise ValueError(f"watchlists.yaml: watchlist name must be a non-empty string, got {name!r}")
            if not isinstance(tickers, list) or len(tickers) == 0:
                raise ValueError(f"watchlists.yaml: watchlist '{name}' must be a non-empty list of tickers")

            seen: set[str] = set()
            clean: list[str] = []
            for i, t in enumerate(tickers):
                if not isinstance(t, str):
                    raise ValueError(
                        f"watchlists.yaml: watchlist '{name}', item {i}: expected string, got {type(t)}"
                    )
                t = t.strip().upper()
                if not t:
                    raise ValueError(
                        f"watchlists.yaml: watchlist '{name}', item {i}: empty ticker string"
                    )
                if t in seen:
                    warnings.warn(
                        f"watchlists.yaml: duplicate ticker '{t}' in '{name}' (deduped)",
                        stacklevel=2,
                    )
                else:
                    seen.add(t)
                    clean.append(t)

            new_lists[name] = tuple(clean)

        self._lists = new_lists

        # Resolve default watchlist name
        default_raw = raw.get('default')
        if isinstance(default_raw, str) and default_raw in self._lists:
            self._default = default_raw
        else:
            self._default = next(iter(self._lists))
            if default_raw is not None:
                logger.warning(
                    f"watchlists.yaml: 'default' key '{default_raw}' not in lists; "
                    f"using first watchlist '{self._default}'"
                )

    def is_available(self) -> bool:
        return self._path.exists() and len(self._lists) > 0

    @property
    def default_watchlist(self) -> str:
        return self._default

    def _create_default(self) -> None:
        self._path.write_text(
            "# watchlists.yaml — projectAlgo watchlist definitions\n"
            "# Edit freely; reloaded on cockpit 'r' refresh.\n\n"
            "default: default\n\n"
            "lists:\n"
            "  default:\n"
            "    - SPY\n"
        )
        self._lists = {'default': ('SPY',)}
        self._default = 'default'
