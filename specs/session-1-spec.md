# projectAlgo — Session 1 Handoff Spec: Foundation Refactor

## Role and context

You are Claude Sonnet 4.6 acting as the executor for a planned refactor of an existing Python project, `projectAlgo`. The architectural design has already been hashed out with the project owner in a separate planning conversation using Claude Opus 4.7. Your job in this session is **execution only**, not design. If you encounter genuine ambiguity not resolved by this spec, **stop and ask** rather than guessing — but the spec is intended to be complete enough that this should rarely be necessary.

The project owner is on a Claude Pro plan with a hard $5/month overage budget. Token efficiency matters. Work directly from this spec; do not re-derive decisions. If the spec contradicts itself somewhere, surface that immediately rather than picking one interpretation silently.

## Important constraint for this session: Schwab OAuth is not yet configured

The project owner has not yet completed Schwab OAuth setup. This means:
- Schwab end-to-end fetches will not work this session
- The Schwab `SchwabSource` class **still gets fully built and refactored** — we are not skipping the Schwab code
- Schwab acceptance criteria are deferred to when auth is configured
- The default `cockpit.toml` ships with `preferred_source = "yfinance"` for now
- The `DataService` fallback path (preferred source unavailable → fall back to other) becomes a positive test we verify this session

This is a useful constraint: it forces us to verify that the abstraction correctly handles "source unavailable" gracefully, which is a real-world failure mode we want robust.

## What this session is

This is a **foundation refactor**. The goal is to reorganize existing code into a layered architecture that supports a much larger future build (a TUI "cockpit" for market monitoring). User-visible behavior of every existing script (excluding Schwab-dependent ones) must be **functionally identical** before and after this session. No new features. No new analysis. No UI work.

If you find yourself adding capability rather than reorganizing it, you have left the scope of this session. Stop.

## Read these first

Before writing any code, read these existing files to understand the current state:

1. `README.md` — project overview
2. `CLAUDE.md` — current architecture notes (you will update this at the end)
3. `requirements.txt` — current dependencies
4. `data_manager/` — entire directory, all files (this is being absorbed into `marketdata/`)
5. `broker/market_data.py` — Schwab market data code (moves into `marketdata/sources/schwab_source.py`)
6. `broker/schwab_client.py` — Schwab auth singleton (stays put)
7. `broker/account.py` — Schwab account ops (stays put)
8. `core/financial_objects.py` — contains `Stock` and `Transaction` (will be split)
9. `scripts/get_data.py` — main entry point that uses `data_manager`
10. `scripts/run_backtest.py` — uses `Stock`, will need import updates
11. `scripts/correlations.py` — uses data layer
12. `scripts/account.py` and `scripts/quote.py` — use `broker/`
13. `analysis/market_analysis.py` — uses data loading
14. `strategies/base_strategy.py` and any concrete strategy files
15. `backtesting/engine.py`
16. `visualization/plot_static.py`, `visualization/view_stock.py`, `visualization/view_backtest.py`

After reading, also check `python --version` so you know whether to use stdlib `tomllib` (3.11+) or the `tomli` package (3.9–3.10).

Build a mental model of every call site that touches `data_manager`, `broker/market_data`, or `Stock`'s data-fetching methods. These are the surfaces that will need updating.

## Target architecture

After this session, the project layout is:

```
projectAlgo/
├── cockpit.toml                          [NEW - project root]
├── README.md                             [keep, do not modify]
├── CLAUDE.md                             [update at end]
├── requirements.txt                      [keep, possibly add tomli]
│
├── config/                               [NEW]
│   ├── __init__.py
│   └── settings.py                       [NEW]
│
├── marketdata/                           [NEW - replaces data_manager/]
│   ├── __init__.py
│   ├── service.py                        [NEW - DataService]
│   ├── cache.py                          [NEW - local CSV cache]
│   ├── exceptions.py                     [NEW - DataSourceError, etc.]
│   └── sources/
│       ├── __init__.py
│       ├── base.py                       [NEW - MarketDataSource ABC]
│       ├── yfinance_source.py            [NEW - was in data_manager/]
│       └── schwab_source.py              [NEW - was in broker/market_data.py]
│
├── core/
│   ├── __init__.py
│   ├── security.py                       [NEW - Stock as pure dataclass]
│   ├── quote.py                          [NEW - Quote dataclass]
│   ├── transaction.py                    [NEW - extracted Transaction]
│   └── financial_objects.py              [DELETE after split]
│
├── broker/                               [keep, slimmed down]
│   ├── __init__.py
│   ├── schwab_client.py                  [keep as-is]
│   ├── account.py                        [keep as-is]
│   └── market_data.py                    [DELETE - moved to marketdata/sources/schwab_source.py]
│
├── notes/                                [NEW - for session debriefs]
│   └── session-1-debrief.md              [NEW - created at end of session]
│
├── analysis/                             [keep, only import updates]
├── strategies/                           [keep, only import updates]
├── backtesting/                          [keep, only import updates]
├── visualization/                        [keep, only import updates]
├── scripts/                              [keep, only import updates]
│
└── data_manager/                         [DELETE entire directory]
```

The `data/` storage directory (where CSVs and pickles live) is **unchanged**. Only the package `data_manager/` is being removed.

## Interfaces and contracts

### `marketdata/exceptions.py`

```python
class DataSourceError(Exception):
    """Raised when a market data source fails to fulfill a request."""
    pass


class SourceUnavailableError(DataSourceError):
    """Raised when a source is not available (e.g., Schwab token expired)."""
    pass


class UnsupportedIntervalError(DataSourceError):
    """Raised when a source does not support the requested interval."""
    pass
```

### `marketdata/sources/base.py`

```python
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
```

### `core/quote.py`

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Quote:
    """A live or most-recent-available market quote."""
    ticker: str
    price: float
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    previous_close: Optional[float] = None
    
    @property
    def change(self) -> Optional[float]:
        if self.previous_close is None:
            return None
        return self.price - self.previous_close
    
    @property
    def change_pct(self) -> Optional[float]:
        if self.previous_close is None or self.previous_close == 0:
            return None
        return (self.price - self.previous_close) / self.previous_close
```

### `core/security.py`

```python
from dataclasses import dataclass, field
from typing import Any, Optional
import pandas as pd


@dataclass
class Stock:
    """A passive data container for a tradeable security.
    
    This class does NOT fetch data. It is a pure data structure.
    To populate `historical_data`, use marketdata.service.DataService.
    """
    ticker: str
    historical_data: Optional[pd.DataFrame] = None
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        self.ticker = self.ticker.upper()
    
    @property
    def has_data(self) -> bool:
        return self.historical_data is not None and not self.historical_data.empty
```

**This is the critical surgery.** The previous `Stock` class had `download_data()` and `load_local_data()` methods. Both are GONE. There is no `calculate_indicator()` method either (it was already marked for deprecation). All data fetching now happens through `DataService`. Construction sites that previously called `stock.download_data(...)` need to be updated to fetch the DataFrame via `DataService` and construct `Stock(ticker=..., historical_data=df)`.

### `core/transaction.py`

Extract the existing `Transaction` class from `core/financial_objects.py` verbatim into this new file. Preserve all behavior including `to_dict()`. Do not change its API.

### `marketdata/cache.py`

```python
from datetime import date
from pathlib import Path
from typing import Optional
import pandas as pd


class LocalCache:
    """CSV-based local cache for OHLCV data.
    
    File naming convention (unchanged from previous data_manager):
        {TICKER}_{interval}_{YYYYMMDD}_{YYYYMMDD}.csv
    
    Behavior:
    - If the exact file exists, load and return it.
    - If not, return None.
    - Writing always overwrites.
    - No smart invalidation in this session (TODO for future).
    """
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _filename(self, ticker: str, interval: str, start: date, end: date) -> Path:
        s = start.strftime('%Y%m%d')
        e = end.strftime('%Y%m%d')
        return self.cache_dir / f"{ticker.upper()}_{interval}_{s}_{e}.csv"
    
    def get(
        self, ticker: str, interval: str, start: date, end: date
    ) -> Optional[pd.DataFrame]:
        path = self._filename(ticker, interval, start, end)
        if not path.exists():
            return None
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df
    
    def put(
        self,
        ticker: str,
        interval: str,
        start: date,
        end: date,
        df: pd.DataFrame,
    ) -> Path:
        path = self._filename(ticker, interval, start, end)
        df.to_csv(path)
        return path
    
    def has(self, ticker: str, interval: str, start: date, end: date) -> bool:
        return self._filename(ticker, interval, start, end).exists()
```

**Match the exact filename format the existing `data_manager` produces.** Look at the existing code in `data_manager/` to confirm the format. If there is any discrepancy between this spec and the existing format, the existing format wins — we are not changing how cache files are named in this session.

### `marketdata/sources/yfinance_source.py`

This is the existing yfinance code, moved and conformed to the `MarketDataSource` interface. Key points:

- Look at the current `data_manager/` code for yfinance fetch logic and preserve its behavior.
- Translate the output DataFrame to canonical shape: index is `DatetimeIndex`, columns are exactly `['Open', 'High', 'Low', 'Close', 'Volume']` in that order. yfinance sometimes returns extra columns (`Adj Close`, `Dividends`, `Stock Splits`) — drop them. yfinance sometimes returns a MultiIndex column when fetching a single ticker — flatten it.
- `supports_interval` returns True for `'1d'`, `'1wk'`, `'1mo'`. Returns False for intraday for now (the existing project notes intraday yfinance is unreliable).
- `is_available` should return True under normal conditions. If you want a lightweight network check, do something cheap; otherwise just return True. **Must not raise.**
- `get_live_quote` uses yfinance to fetch the most recent available bar and returns a `Quote`. Document the delay disclaimer in the docstring.

### `marketdata/sources/schwab_source.py`

This is the existing `broker/market_data.py` code, moved and conformed to the interface.

- Import the Schwab auth singleton from `broker.schwab_client`.
- Preserve all existing Schwab fetching behavior — same period handling, same response parsing.
- The output DataFrame must match the canonical OHLCV shape exactly. If the existing Schwab code returns a slightly different shape than yfinance, align them now.
- `supports_interval` returns True for `'1d'`, `'1wk'`, `'1mo'`, and intraday intervals Schwab supports (`'1m'`, `'5m'`, `'15m'`, `'30m'`, `'1h'`). Verify against the existing code.
- `is_available` checks `schwab_client.is_authenticated()`. **Critical:** this must return `False` cleanly when no token is configured. It must not raise an exception. The owner does not have Schwab auth set up yet, so this method WILL be called and WILL return False during this session's testing. Make sure this path is handled gracefully — no exceptions, just a clean `False`.
- `get_live_quote` uses Schwab's quote endpoint and returns a `Quote`.

### `marketdata/service.py`

```python
from datetime import date
import logging
from typing import Optional

import pandas as pd

from config.settings import Settings
from core.quote import Quote
from marketdata.cache import LocalCache
from marketdata.exceptions import (
    DataSourceError,
    SourceUnavailableError,
    UnsupportedIntervalError,
)
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


# Module-level accessor for convenience
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
```

### `config/settings.py`

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Use stdlib tomllib if available (Python 3.11+), else fall back to tomli
try:
    import tomllib
except ImportError:
    import tomli as tomllib


@dataclass(frozen=True)
class Settings:
    preferred_source: str
    data_dir: Path
    backtest_results_dir: Path
    refresh_interval_seconds: int
    theme: str
    log_level: str
    
    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Settings":
        """Load settings from cockpit.toml at project root."""
        if path is None:
            path = Path(__file__).resolve().parent.parent / "cockpit.toml"
        
        with open(path, 'rb') as f:
            data = tomllib.load(f)
        
        return cls(
            preferred_source=data['data']['preferred_source'],
            data_dir=Path(data['data']['data_dir']),
            backtest_results_dir=Path(data['data']['backtest_results_dir']),
            refresh_interval_seconds=data['refresh']['interval_seconds'],
            theme=data['theme']['default'],
            log_level=data['logging']['level'],
        )
```

If the project is on Python 3.9 or 3.10, add `tomli>=2.0` to `requirements.txt`. If on 3.11+, no requirements change needed.

### `cockpit.toml` (project root)

**Note: `preferred_source` is set to yfinance for this session because Schwab OAuth is not yet configured. Owner will flip this to "schwab" after completing OAuth setup.**

```toml
# projectAlgo cockpit configuration

[data]
# Preferred source for market data. Options: "schwab", "yfinance".
# Set to "yfinance" until Schwab OAuth is configured; flip to "schwab" after.
preferred_source = "yfinance"
data_dir = "data/historical_data"
backtest_results_dir = "data/backtest_results"

[refresh]
interval_seconds = 30

[theme]
default = "claude-warm"

[logging]
level = "INFO"
```

## Call site updates

Every place that currently uses the old patterns needs updating. Find them all by searching the codebase for these import patterns:

```
from data_manager
import data_manager
from broker.market_data
from core.financial_objects
stock.download_data
stock.load_local_data
```

Replace per the following table:

| Old | New |
|---|---|
| `from data_manager import get_historical_data` | `from marketdata.service import get_data_service` |
| `from data_manager.utils import ...` | check actual current import, route via `marketdata.cache` or `marketdata.service` |
| `from broker.market_data import get_historical_ohlcv` | `from marketdata.service import get_data_service` |
| `from broker.market_data import get_live_quotes` | `from marketdata.service import get_data_service` |
| `from core.financial_objects import Stock` | `from core.security import Stock` |
| `from core.financial_objects import Transaction` | `from core.transaction import Transaction` |
| `stock.download_data(...)` | `df = service.get_historical_ohlcv(...); stock.historical_data = df` |
| `stock.load_local_data(...)` | same as above; cache handling is inside `DataService` |

**Concrete pattern for the most common case.** Where the old code looked like:

```python
stock = Stock("AAPL")
stock.download_data(start="2023-01-01", end="2024-12-31", interval="1d", data_dir="data/historical_data")
df = stock.historical_data
```

The new code looks like:

```python
from datetime import date
from marketdata.service import get_data_service
from core.security import Stock

service = get_data_service()
df = service.get_historical_ohlcv("AAPL", date(2023,1,1), date(2024,12,31), interval="1d")
stock = Stock(ticker="AAPL", historical_data=df)
```

Files that almost certainly need updates (verify and add any missed):

- `scripts/get_data.py`
- `scripts/run_backtest.py`
- `scripts/correlations.py`
- `scripts/account.py` — only if it imports market data (account ops stay)
- `scripts/quote.py`
- `scripts/inspect_pickle.py` — probably no changes needed, but verify
- `analysis/market_analysis.py`
- `strategies/base_strategy.py` and any concrete strategies
- `backtesting/engine.py` — if it constructs Stocks
- `visualization/plot_static.py`
- `visualization/view_stock.py`
- `visualization/view_backtest.py`

## What stays exactly as-is

Do not modify the internals of these files. Only update their imports if necessary:

- `analysis/technical_analysis.py`
- `analysis/performance_metrics.py`
- `analysis/market_analysis.py` (internal logic; only update imports)
- `strategies/sma_crossover.py` (logic stays; imports may change)
- `strategies/base_strategy.py` (logic stays; imports may change)
- `backtesting/engine.py` (logic stays; imports may change)
- `broker/schwab_client.py`
- `broker/account.py`
- `visualization/indicator_plot_configs.py`
- All visualization rendering logic

## Deletions

At the end of the session, after all call sites are updated and tests pass, delete:

- `data_manager/` (entire directory)
- `broker/market_data.py`
- `core/financial_objects.py`

Verify the deletions don't break anything by re-running the acceptance criteria below.

## Acceptance criteria

The session is complete when **all non-deferred** criteria pass. Deferred ones are documented for later verification.

**Pass these this session:**

1. `python -m scripts.get_data -t AAPL -i 1d -s 2023-01-01 -e 2024-12-31` produces a CSV in `data/historical_data/` with the same filename and content shape as before the refactor. Data comes from yfinance.
2. `python -m scripts.run_backtest -t AAPL -s 2023-01-01 -e 2024-12-31` runs to completion and produces a valid pickle bundle.
3. `python -m scripts.correlations -t AAPL MSFT NVDA` produces a correlation matrix.
4. `python -m visualization.plot_static -t AAPL -s 2023-01-01 -e 2024-06-11 -i 1d --indicators "sma:20"` produces a chart.
5. `python -c "import data_manager"` raises `ImportError`.
6. `python -c "from core.financial_objects import Stock"` raises `ImportError`.
7. `python -c "from broker.market_data import get_historical_ohlcv"` raises `ImportError`.
8. `python -c "from marketdata.service import get_data_service; s = get_data_service(); print(type(s).__name__)"` prints `DataService`.
9. `python -c "from core.security import Stock; s = Stock(ticker='AAPL'); print(s.ticker, s.has_data)"` prints `AAPL False`.
10. `python -c "from marketdata.sources.schwab_source import SchwabSource; s = SchwabSource(); print(s.is_available())"` prints `False` cleanly (no exceptions, no stack trace).
11. `cockpit.toml` exists at project root with `preferred_source = "yfinance"`.
12. Cache hit/miss path: running `python -m scripts.get_data -t AAPL -i 1d -s 2023-01-01 -e 2024-12-31` twice in a row results in a "Cache hit" log line on the second run.
13. **Fallback path test**: temporarily edit `cockpit.toml` to set `preferred_source = "schwab"`, run `python -m scripts.get_data -t MSFT -i 1d -s 2024-01-01 -e 2024-06-30`, and verify (a) a warning log line appears saying schwab is unavailable, (b) the fetch succeeds via yfinance fallback, (c) the CSV is written normally. Then restore `cockpit.toml` to `preferred_source = "yfinance"`.

**Deferred until Schwab OAuth is configured (do NOT test this session, but document in debrief):**

- `python -m scripts.get_data --source schwab` round-trip
- `python -m scripts.account`
- `python -m scripts.quote AAPL MSFT`
- `cockpit.toml` with `preferred_source = "schwab"` as the steady-state choice

These will be the owner's first tests after completing OAuth setup. If they pass, the entire Schwab refactor is validated by config change alone.

## CLAUDE.md update

After the refactor and all non-deferred acceptance criteria pass, update `CLAUDE.md` to reflect:

- New module layout (replace the "Architecture" section)
- New data flow: `marketdata → core → analysis/strategies → backtesting/visualization`
- New `DataService` as the canonical data entry point
- New `Stock` is passive; data fetching is via `DataService`
- `cockpit.toml` as the config source
- Updated "Common Commands" if any examples changed
- Remove references to `data_manager/` and old `Stock.download_data()` pattern
- Note current `preferred_source = "yfinance"` and that flipping to `"schwab"` is a one-line config change after OAuth
- Add a note: "The cockpit TUI is planned for future sessions and does not yet exist."

Keep `CLAUDE.md` concise and current. Do not let it grow into a history document.

## Session debrief

At the end of the session, create `notes/session-1-debrief.md` with:

1. **What got built** — a one-paragraph summary
2. **What surprised you** — anything in the existing code that was different than the spec assumed, anything you had to deviate on, anything that took longer than expected
3. **Schwab readiness check** — confirm that `SchwabSource` structurally compiles and that `is_available()` returns False cleanly. List the exact tests the owner should run after OAuth setup to validate Schwab.
4. **Open questions for the next planning round** — things the project owner should decide before Session 2
5. **Anything left undone** — if you ran short, what's the smallest cleanup needed before Session 2 can start

This file gets pasted back into the Claude.ai planning conversation to inform Session 2.

## Working style notes

- Read first, code second. The 16-file read list above is mandatory before changes.
- Make changes in small, verifiable batches. After creating each new package, smoke-test imports before moving on.
- Run the acceptance criteria as you go, not just at the end. Catch issues early.
- If something in the existing code conflicts with this spec (e.g. the cache filename format differs), surface it and ask before deviating. The spec is authoritative for intent but the existing code is authoritative for "what does the current behavior actually look like."
- Do not add tests beyond inline smoke checks. Test infrastructure is out of scope for this session.
- Do not add type checking (mypy) or linting (ruff) setup. Out of scope.
- Do not touch git — no commits, no branches. The project owner manages version control.

## What to do if you get stuck

If you hit ambiguity that this spec doesn't resolve: stop, write down what you're stuck on, and surface it to the user. Do not guess and move on. A 30-second clarification beats 30 minutes of rework.

If you hit a real bug in existing code that's blocking the refactor (e.g. a script that's broken before you touched it): fix it minimally and note it in the debrief. Don't redesign around it.

If the refactor turns out to be larger than expected and you're running out of context, **stop at a clean checkpoint** rather than leaving half-broken state. Document where you stopped in the debrief. It's better to leave Session 1 partially done with a clear handoff than to leave it broken.
