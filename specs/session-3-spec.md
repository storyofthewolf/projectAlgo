# Session 3 Spec — Watchlist Real-Data Wiring

**Target executor:** Sonnet 4.6 in Claude Code
**Estimated scope:** one focused Claude Code session
**Builds on:** Sessions 1 (data layer) and 2 (cockpit shell)
**Prerequisite:** Mandatory read list below

---

## 0. Mandatory read list

Read these before touching any code. They define vocabulary, constraints, and what already exists.

1. `specs/ROADMAP.md` — overall project plan and current state
2. `specs/ARCHITECTURE.md` — layered architecture, design principles, anti-patterns
3. `notes/session-2-debrief.md` — what shipped in Session 2, known issues, owner reactions
4. `cockpit/app.py`, `cockpit/screens/home.py`, `cockpit/mock_data.py` — what the watchlist panel currently does
5. `marketdata/service.py` — the public DataService API you will be calling
6. `core/quote.py` — the `Quote` dataclass you will be embedding in snapshots
7. Textual docs:
   - `set_interval()` on `Screen` / `App` — polling pattern
   - `reactive` attributes — automatic UI re-render on data change
   - `Worker` / `work` decorator — background task pattern
   - `DataTable` widget — likely the right primitive for the watchlist panel
   - `VerticalScroll` container — alternative if DataTable doesn't fit
8. `tomli` and `PyYAML` (or `ruamel.yaml`) docs for config parsing

---

## 1. Goals of this session

**Primary goal:** Wire the watchlist panel to real data via DataService. Prove the end-to-end pattern that Sessions 4-7 will replicate for the other panels.

**Secondary goals:**
- Fix two known issues from Session 2 (flash not firing, sparkline range compression)
- Establish the `workflows/` layer with one concrete example
- Establish the watchlist provider abstraction so Session 8 (Schwab) is a fill-in, not a refactor

**Out of scope (do not touch):**
- Account panel — still placeholder
- Market pulse panel — Session 4
- Sector heatmap panel — Session 5
- Correlation matrix panel — Session 6
- Ticker drill-down screens — Session 7
- Implementing the Schwab watchlist provider — Session 8 (stub only this session)
- Schwab OAuth wiring — owner does manually when ready

---

## 2. Pre-work: fix two issues from Session 2

Do these **first**, before any new wiring. Both block the visual quality of everything that follows.

### 2.1 Flash diagnostic and fix

**Symptom:** Owner reported flash-on-update is not visibly firing when pressing `r` to refresh mock data.

**Diagnostic steps:**

1. Increase mock data perturbation amplitude temporarily. `cockpit/mock_data.py` currently perturbs by ±0.5%. Bump to ±5% just for this diagnostic.
2. Launch cockpit, press `r` repeatedly, observe whether `PriceCell` and `PctCell` actually flash.
3. If they still don't flash, instrument the widget with a debug log on every value update. Confirm `watch_*` reactive handler is firing.
4. If reactive is firing but no CSS animation, inspect the Textual theme/styles — `:has(.flash-up)` or whatever selector the widget uses may have changed in Textual 8.x.

**Likely root causes (rank order):**

1. The flash CSS class is being applied and removed too fast for the user to see (< one frame)
2. The CSS class is applied but the variable it references resolves to the same color as the base text
3. The reactive `watch_*` handler isn't firing because the new value is being compared by reference, not value, and the dataclass is being treated as equal

**Fix the actual cause.** Revert the mock perturbation amplitude to ±0.5% once you've verified flash works.

**Acceptance:** Press `r` on the cockpit and *visibly* see PriceCell and PctCell flash green/red on values that changed, with the flash visible for at least 300ms.

### 2.2 Sparkline range-compression fix

**Symptom:** Owner reported the sparkline blocks are "too close together" and "resolution isn't very useful as currently shown."

**Diagnosis:** the current sparkline almost certainly maps `(min, max) → (0, 7)` linearly across the 8 block characters. With real daily data this is dynamic-range starved.

**Fix:**

1. In `cockpit/widgets/sparkline.py`, change the value-to-block mapping from absolute `(min, max)` to **percentile-based** normalization. Use the 5th and 95th percentiles of the input series as the visual range bounds. Values outside that range clip to the extreme blocks.
2. Ensure the sparkline renders exactly `N` characters wide where `N` is configurable via constructor (default to 12 cells). When the input has more samples than cells, downsample by taking every k-th value, *not* by averaging windows (averaging destroys the visible movement).
3. When input has fewer samples than cells, left-pad with the lowest block (`▁`) so the sparkline is right-aligned to "now."
4. When input is all-identical (flat), render the middle block (`▄`) for every cell rather than dividing by zero.

**Acceptance:** Construct a sparkline from AAPL's actual last 30 daily closes (fetched via DataService for verification). The result should show visible variation across cells, not look like a featureless block. Construct another from a flat synthetic series; it should show a flat row of middle blocks. Construct from a series with one outlier day; the outlier compresses to extreme block, rest of the data still has visible range.

---

## 3. Target file layout

After this session, the new and modified files are:

```
projectAlgo/
├── watchlists.yaml                    # NEW — at project root, hand-editable
│
├── workflows/                         # NEW — first concrete workflow package
│   ├── __init__.py
│   └── watchlist_snapshot.py          # NEW — build_watchlist_snapshot() + dataclasses
│
├── cockpit/
│   ├── screens/
│   │   └── home.py                    # MODIFIED — watchlist panel wired to workflow
│   ├── widgets/
│   │   ├── sparkline.py               # MODIFIED — percentile-based mapping
│   │   ├── price_cell.py              # MODIFIED if flash bug is here
│   │   ├── pct_cell.py                # MODIFIED if flash bug is here
│   │   └── watchlist_panel.py         # NEW — the focusable scrollable panel widget
│   ├── watchlists/                    # NEW — provider abstraction subpackage
│   │   ├── __init__.py
│   │   ├── base.py                    # WatchlistProvider ABC
│   │   ├── yaml_provider.py           # YamlWatchlistProvider
│   │   ├── schwab_provider.py         # SchwabWatchlistProvider stub
│   │   └── registry.py                # WatchlistRegistry aggregator
│   └── styles.tcss                    # MODIFIED — watchlist panel styling
│
└── config/
    └── settings.py                    # MODIFIED — add WatchlistSettings if needed
```

**Notes:**
- `watchlists.yaml` goes at the project root, not inside `cockpit/`, because conceptually it's user content, not cockpit machinery
- `workflows/` is at the project root, peer to `analysis/`, `strategies/`, etc.
- The watchlist *panel* widget lives in `cockpit/widgets/` because it's a Textual widget. The watchlist *provider* code lives in `cockpit/watchlists/` because it's cockpit-specific (other consumers might use DataService differently). Workflows live in `workflows/` because they're consumer-agnostic.

---

## 4. Interface signatures

These are exact. Type hints match Python 3.14 syntax. All dataclasses are frozen.

### 4.1 `workflows/watchlist_snapshot.py`

```python
from dataclasses import dataclass
from datetime import datetime
from core.quote import Quote


@dataclass(frozen=True)
class TickerRow:
    """One successfully-fetched ticker in a watchlist snapshot."""
    ticker: str
    quote: Quote
    sparkline_closes: tuple[float, ...]  # last 30 daily closes, oldest first
    quote_source: str                     # 'yfinance' or 'schwab'
    history_source: str                   # 'yfinance' or 'schwab'


@dataclass(frozen=True)
class TickerError:
    """A ticker that failed to fetch."""
    ticker: str
    error_message: str
    failed_stage: str  # 'quote' or 'history'


@dataclass(frozen=True)
class WatchlistSnapshot:
    """Result of building a watchlist view at a point in time."""
    provider_name: str       # 'yaml' or 'schwab'
    watchlist_name: str      # e.g. 'core', 'semis'
    rows: tuple[TickerRow, ...]
    errors: tuple[TickerError, ...]
    timestamp: datetime
    quote_sources: frozenset[str]  # for panel-level source indicator


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
```

**Implementation notes:**

- Use `marketdata.service.get_data_service()` for both quote and history fetches.
- Historical fetch: `service.get_historical_ohlcv(ticker, start=today - timedelta(days=sparkline_days*1.5), end=today, interval='1d')` — the 1.5× multiplier accounts for weekends/holidays so you get at least `sparkline_days` trading days. Trim to last `sparkline_days` rows.
- Quote fetch: `service.get_live_quote(ticker)`.
- Catch `Exception` per ticker. Translate into `TickerError`. The `failed_stage` field tells the UI whether quote or history failed; if both fail, record as `'quote'` since that's the more user-visible failure.
- Timestamp is `datetime.now()` at the start of the build, not the end. The cockpit will display this as "as of HH:MM:SS" so the time should reflect when the data was requested, not when the function happened to return.

### 4.2 `cockpit/watchlists/base.py`

```python
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
```

### 4.3 `cockpit/watchlists/yaml_provider.py`

```python
from pathlib import Path
import yaml  # PyYAML
from .base import WatchlistProvider


class YamlWatchlistProvider(WatchlistProvider):
    """Loads watchlists from a YAML file at a fixed path."""
    
    def __init__(self, path: Path):
        self._path = path
        self._lists: dict[str, tuple[str, ...]] = {}
        self.reload()  # initial load at construction
    
    @property
    def provider_name(self) -> str:
        return 'yaml'
    
    def list_watchlists(self) -> tuple[str, ...]:
        return tuple(self._lists.keys())
    
    def get_tickers(self, watchlist_name: str) -> tuple[str, ...]:
        return self._lists[watchlist_name]
    
    def reload(self) -> None:
        # Read, validate, populate self._lists.
        # On schema error, raise ValueError with a clear message.
        # See section 5 for the YAML schema.
        ...
    
    def is_available(self) -> bool:
        return self._path.exists() and len(self._lists) > 0
```

### 4.4 `cockpit/watchlists/schwab_provider.py`

```python
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
        return ()  # Empty until implemented
    
    def get_tickers(self, watchlist_name: str) -> tuple[str, ...]:
        raise KeyError(
            "SchwabWatchlistProvider not yet implemented (Session 8)"
        )
    
    def reload(self) -> None:
        pass  # No-op until implemented
    
    def is_available(self) -> bool:
        return False  # Always unavailable until Session 8
```

### 4.5 `cockpit/watchlists/registry.py`

```python
from .base import WatchlistProvider


class WatchlistRegistry:
    """Aggregates watchlists across multiple providers.
    
    Cycle order: providers in declaration order, watchlists within each
    provider in provider-defined order. yaml comes first, schwab second.
    """
    
    def __init__(self, providers: tuple[WatchlistProvider, ...]):
        self._providers = providers
    
    def cycle_order(self) -> tuple[tuple[str, str], ...]:
        """Return [(provider_name, watchlist_name), ...] in cycle order.
        
        Skips providers that report is_available() == False.
        """
    
    def get_tickers(
        self, provider_name: str, watchlist_name: str
    ) -> tuple[str, ...]:
        """Look up tickers from the named provider+watchlist."""
    
    def reload_all(self) -> None:
        """Reload every provider's underlying source."""
```

---

## 5. `watchlists.yaml` schema

The file lives at the project root. Schema:

```yaml
# watchlists.yaml — projectAlgo watchlist definitions
# Edit freely; reloaded on cockpit 'r' refresh.

default: default          # which watchlist to show on cockpit startup

lists:
  default:
    - SPY
```

**Validation rules** (enforced in `YamlWatchlistProvider.reload()`):

1. Top-level keys must be exactly `{default, lists}`. Extra keys: warn and ignore.
2. `default` must be a non-empty string referencing a key in `lists`. If missing, default to the first key in `lists`. If `lists` is empty, raise `ValueError("watchlists.yaml has no watchlists defined")`.
3. `lists` must be a mapping from non-empty string names to non-empty lists of strings.
4. Every ticker is normalized to upper-case and stripped of whitespace.
5. Empty ticker strings within a list raise `ValueError` with location info.
6. Duplicate tickers within a single watchlist: warn and dedupe.
7. The file ships with a single `default` watchlist containing just `SPY`, so a freshly-cloned cockpit boots with something non-empty.

**Owner action after Session 3:** edit `watchlists.yaml` to add real tickers. The session does not ship generic example lists.

---

## 6. Threading model and polling

This is the single most important section. Get it right and Sessions 4-7 follow effortlessly.

### 6.1 The workflow is synchronous

`build_watchlist_snapshot()` is a regular synchronous function. It uses pandas, makes blocking network calls via DataService, returns a snapshot. **It must never import Textual or asyncio.**

This is the architectural anchor. Pure data in, pure data out. Same workflow callable from a Dash app, a CLI script, or the cockpit.

### 6.2 The screen runs the polling loop

```python
# cockpit/screens/home.py — sketch

class HomeScreen(Screen):
    
    active_provider: reactive[str] = reactive('yaml')
    active_watchlist: reactive[str] = reactive('default')
    snapshot: reactive[WatchlistSnapshot | None] = reactive(None)
    
    def on_mount(self) -> None:
        # Initial load
        self.refresh_watchlist()
        # Then poll
        interval = self.app.settings.refresh.interval_seconds
        self.set_interval(interval, self.refresh_watchlist)
    
    @work(exclusive=True, thread=True)
    def refresh_watchlist(self) -> None:
        """Runs in a thread so network I/O doesn't block the UI."""
        registry = self.app.watchlist_registry
        tickers = registry.get_tickers(
            self.active_provider, self.active_watchlist
        )
        snapshot = build_watchlist_snapshot(
            self.active_provider, self.active_watchlist, tickers
        )
        # Cross-thread UI update via call_from_thread
        self.app.call_from_thread(self._set_snapshot, snapshot)
    
    def _set_snapshot(self, snapshot: WatchlistSnapshot) -> None:
        self.snapshot = snapshot  # triggers watch_snapshot()
    
    def watch_snapshot(
        self, old: WatchlistSnapshot | None, new: WatchlistSnapshot | None
    ) -> None:
        if new is None:
            return
        panel = self.query_one(WatchlistPanel)
        panel.update_from_snapshot(new)
```

**Why `@work(exclusive=True, thread=True)`:**
- `exclusive=True` cancels any in-flight refresh when a new one starts. This is what you want for a polling pattern — if a poll takes 40 seconds and the interval is 30, you don't want to stack them.
- `thread=True` runs the function in a thread pool, not on the event loop. Network calls don't block UI rendering or keystroke handling.

**Why `call_from_thread`:** mutating Textual reactive attributes from a non-event-loop thread is not safe. `call_from_thread` schedules the mutation back onto the event loop.

### 6.3 Cache contract for sparkline data

The 30-day sparkline does not need to refresh every 30 seconds. Daily bars don't update intra-day. To avoid hammering yfinance:

- Quote fetch: always hits the network (it's a live quote)
- History fetch: relies on `LocalCache`. The cache key is `(ticker, interval, start, end)`. As long as the same `(start, end)` is requested across polls within a single calendar day, every poll after the first is a cache hit.

**Implementation:** in `build_watchlist_snapshot`, compute `start` and `end` once based on `today`'s date. Within the same day, every poll computes the same `(start, end)`, so LocalCache serves from disk.

**Date rollover:** when the calendar date changes (e.g. user leaves cockpit running overnight), the next poll computes a new `end` date and the cache miss triggers a fresh fetch. This is correct behavior.

### 6.4 What `r` does

Pressing `r` triggers a "full refresh":
1. Call `registry.reload_all()` — re-reads `watchlists.yaml` from disk
2. If `active_watchlist` no longer exists in the reloaded provider, fall back to the first available watchlist
3. Trigger `refresh_watchlist()` — re-fetches all data

The auto-polling interval keeps running independently; `r` is a forced extra poll, not a reset of the timer.

---

## 7. Error handling contract

**Per-ticker failures: data, not exceptions.**

```python
try:
    quote = service.get_live_quote(ticker)
except Exception as e:
    errors.append(TickerError(
        ticker=ticker,
        error_message=str(e),
        failed_stage='quote',
    ))
    continue
```

**Configuration failures: loud exceptions.**

- Missing `watchlists.yaml` → raise at startup with a clear message and an offer to create a default file (or just create it silently with the SPY default)
- Schema violations in YAML → raise `ValueError` with location info
- Requesting a watchlist that doesn't exist → raise `KeyError`

**Network blips and rate limits:** these become `TickerError` entries. The panel shows the affected row as an error row (see 8.4). The polling loop continues; the next poll might succeed.

**Backoff on systemic failure:** if every ticker in a single poll fails (suggesting a network outage or DataService-level problem), log a warning. Do not implement exponential backoff in this session — keep it simple. If this becomes a real problem in practice, add it later.

---

## 8. Watchlist panel widget

### 8.1 Layout

The panel occupies the same grid cell it currently does in `HomeScreen`. Inside:

```
┌─ WATCHLIST: yaml/default · quotes: yfinance · 14:32:45 ET ────────┐
│ TICKER   PRICE        CHG        CHG%      SPARK         VOL      │
│ AAPL     187.42    +1.23    +0.66%  ▁▂▃▅▆▇▇█       42.1M       │
│ MSFT     412.78    -2.41    -0.58%  ▆▅▄▃▂▁▂▃       18.7M       │
│ NVDA     ─         ─       ─       [ERR]         ─    rate limit │
│ SPY      ...                                                       │
└────────────────────────────────────────────────────────────────────┘
```

Columns, left to right:
1. **TICKER** — 6 chars, uppercase
2. **PRICE** — 10 chars, right-aligned, 2 decimals
3. **CHG** — 9 chars, signed, 2 decimals
4. **CHG%** — 8 chars, signed, 2 decimals, `%` suffix
5. **SPARK** — 12 chars, the sparkline blocks
6. **VOL** — 7 chars, compact (`42.1M`, `1.2B`, `987K`)

When a row is an error row, columns 2-6 collapse: price/chg/chg%/vol show `—`, sparkline column shows `[ERR]`, and a final compressed message field after volume shows the error message (truncated to fit).

### 8.2 Header line

`WATCHLIST: {provider}/{watchlist}  ·  quotes: {source_indicator}  ·  {real_time_clock}`

- Provider/watchlist comes from the active selection
- Source indicator: if `quote_sources` has exactly one element, show it (`yfinance` or `schwab`). If multiple, show `mixed`.
- Real-time clock: ticks every second via the existing `ClockHeader` mechanism, formatted `HH:MM:SS ET`. This is current wall-clock, NOT the snapshot timestamp. Owner confirmed: "Real-time clock time."

### 8.3 Scrolling

The panel is focusable. When focused:
- `j` or `Down`: scroll one row down
- `k` or `Up`: scroll one row up
- `g`: jump to top
- `G`: jump to bottom (Shift+G)
- `Tab`/`Shift+Tab`: leave panel (existing global binding)

Use Textual's `DataTable` if its scrolling and focus behavior fit the needs. If `DataTable` is too constraining (e.g. can't easily put sparklines in cells), use a `VerticalScroll` containing custom row widgets. **Sonnet decides** based on what works cleanly with the cell-flash requirement — flash is a hard requirement, scrolling primitive is negotiable.

### 8.4 Error row styling

- Foreground color: dimmed text variable (`$text-dim` from the active theme)
- An error glyph at the start of the row (suggest `⚠` or `✗`)
- Numerical columns replaced with em-dash (`—`)
- Sparkline column shows `[ERR]` in dim text
- Trailing error message field, truncated to terminal-fit width with ellipsis

### 8.5 Flash on update

When `update_from_snapshot()` is called and a ticker's price differs from its previous value:
- Use the existing `PriceCell` and `PctCell` widgets — they already implement flash
- If flash isn't working after Session 2 fixes (see section 2.1), fix it before wiring real data on top, not after

### 8.6 Cycling watchlists with `w`

Add a global binding `w` that cycles to the next `(provider, watchlist)` pair in `WatchlistRegistry.cycle_order()`. Wrap around at the end. Update `active_provider` and `active_watchlist` reactive attrs; `watch_active_watchlist` triggers `refresh_watchlist`.

Since only one provider (`yaml`) is available this session, cycling stays within YAML watchlists. The Schwab provider returns empty `list_watchlists()`, so the registry skips it.

---

## 9. Concrete before/after — what the watchlist panel calls

### Before (current Session 2 state)

```python
# cockpit/screens/home.py — roughly

class HomeScreen(Screen):
    def compose(self):
        ...
        yield PanelFrame("WATCHLIST", id="watchlist") 
        ...
    
    def on_mount(self):
        # Populate panel from mock_data.py
        watchlist_data = mock_data.WATCHLIST_TICKERS
        for row in watchlist_data:
            # construct rows from hardcoded mock
            ...
```

### After

```python
# cockpit/screens/home.py — sketch

class HomeScreen(Screen):
    active_provider: reactive[str] = reactive('yaml')
    active_watchlist: reactive[str] = reactive('default')
    snapshot: reactive[WatchlistSnapshot | None] = reactive(None)
    
    def compose(self):
        ...
        yield WatchlistPanel(id="watchlist")
        ...
    
    def on_mount(self) -> None:
        # Initial load and start polling
        self.refresh_watchlist()
        interval = self.app.settings.refresh.interval_seconds
        self.set_interval(interval, self.refresh_watchlist)
    
    @work(exclusive=True, thread=True)
    def refresh_watchlist(self) -> None:
        registry = self.app.watchlist_registry
        try:
            tickers = registry.get_tickers(
                self.active_provider, self.active_watchlist
            )
        except KeyError:
            # Active watchlist no longer exists after a reload
            available = registry.cycle_order()
            if not available:
                self.app.call_from_thread(self._handle_no_watchlists)
                return
            self.active_provider, self.active_watchlist = available[0]
            tickers = registry.get_tickers(
                self.active_provider, self.active_watchlist
            )
        snapshot = build_watchlist_snapshot(
            self.active_provider, self.active_watchlist, tickers
        )
        self.app.call_from_thread(self._set_snapshot, snapshot)
    
    def _set_snapshot(self, snapshot: WatchlistSnapshot) -> None:
        self.snapshot = snapshot
    
    def watch_snapshot(self, old, new) -> None:
        if new is not None:
            self.query_one(WatchlistPanel).update_from_snapshot(new)
    
    def action_refresh(self) -> None:
        """Bound to 'r'. Full refresh: reload config + re-fetch data."""
        self.app.watchlist_registry.reload_all()
        self.refresh_watchlist()
    
    def action_cycle_watchlist(self) -> None:
        """Bound to 'w'. Cycle to next watchlist."""
        order = self.app.watchlist_registry.cycle_order()
        if not order:
            return
        try:
            i = order.index(
                (self.active_provider, self.active_watchlist)
            )
            next_i = (i + 1) % len(order)
        except ValueError:
            next_i = 0
        self.active_provider, self.active_watchlist = order[next_i]
        self.refresh_watchlist()
    
    def watch_active_watchlist(self, old, new) -> None:
        # Refresh when active watchlist changes (e.g. from 'w' cycle)
        self.refresh_watchlist()
```

The `CockpitApp` needs to construct and hold the `WatchlistRegistry`:

```python
# cockpit/app.py — added in on_mount or __init__

self.watchlist_registry = WatchlistRegistry(providers=(
    YamlWatchlistProvider(path=Path('watchlists.yaml')),
    SchwabWatchlistProvider(),
))
```

---

## 10. Acceptance criteria

Every item must pass before the session is considered complete. Test them in order.

### Pre-work fixes (Section 2)

1. **Flash visible:** Launch cockpit, press `r` three times. PriceCell and PctCell visibly flash green/red on values that changed. Flash duration is at least 300ms and at most 800ms.
2. **Sparkline range usable:** Construct a sparkline from real AAPL 30-day closes (a one-off script is fine). Output shows visible variation across multiple block levels, not a featureless ~2-level bar.
3. **Sparkline edge cases:** Flat input shows row of middle blocks (`▄▄▄...`). Single-outlier input compresses outlier to extreme, rest still varied. Short input (5 samples in 12 cells) left-pads correctly.

### Wiring (Sections 4-9)

4. **YAML loads:** Ship `watchlists.yaml` with `default: default` and `default: [SPY]`. Launch cockpit. Watchlist panel header shows `WATCHLIST: yaml/default`.
5. **Real data appears:** Within ~5 seconds of launch, the panel shows SPY's actual current price, change, change %, sparkline, and volume from yfinance (or Schwab if authed and preferred).
6. **Multiple tickers:** Edit `watchlists.yaml` to a list with AAPL, MSFT, NVDA, GOOGL, SPY. Press `r`. All five tickers appear with real data.
7. **Auto-refresh:** Leave cockpit open. Within `refresh.interval_seconds` (30s), the panel updates again. Quote values that changed flash.
8. **Sparkline is cached:** Watch network activity (e.g. `tcpdump` or a print statement in the cache code). Within a single day, repeated polls fetch quotes but NOT history. History only re-fetches on date rollover or first cache miss.
9. **Bad ticker handling:** Add `XXXXX` (invalid) to a watchlist, press `r`. The panel shows other tickers normally and shows XXXXX as a dimmed error row with `[ERR]` glyph and an error message snippet. The cockpit does NOT crash.
10. **`r` reloads YAML:** With cockpit running, edit `watchlists.yaml` to add a new ticker. Save file. Press `r`. The new ticker appears in the panel.
11. **`w` cycles watchlists:** Define two watchlists in YAML (e.g. `default` and `semis`). Press `w` — panel switches to `semis` with its tickers and data. Press `w` again — back to `default`.
12. **Panel scrolling:** Define a watchlist with 30 tickers. Focus the panel (via Tab). Press `j` — scrolls down. `k` — up. `g` — top. `G` — bottom.
13. **Header source indicator:** With `preferred_source = yfinance` in cockpit.toml, header reads `quotes: yfinance`. (Schwab-mixed case is deferred to Session 8 when Schwab actually works.)
14. **Real-time clock:** Header time ticks every second, independent of data refresh interval.
15. **Workflow isolation:** Open `workflows/watchlist_snapshot.py`. No imports from `cockpit`, `textual`, or `asyncio`. Function is callable from a plain Python script:
    ```python
    from workflows.watchlist_snapshot import build_watchlist_snapshot
    snap = build_watchlist_snapshot('yaml', 'default', ('SPY',))
    print(snap)
    ```
    This runs without involving Textual at all.

### Architectural acceptance

16. **Provider abstraction works:** `SchwabWatchlistProvider().is_available()` returns False; `WatchlistRegistry` skips it in `cycle_order()`. Stubs raise `NotImplementedError` or return empty as documented.
17. **No conflation:** Grep `workflows/` and `cockpit/watchlists/` for direct references to `yfinance` or `schwab-py`. There should be zero matches — all source-specific code stays in `marketdata/sources/`.
18. **No mock data in critical path:** The watchlist panel does not import from `cockpit/mock_data.py`. (Other panels still might until Sessions 4-7 land.)

---

## 11. What stays as-is

Explicit non-goals — do NOT touch these in Session 3:

- `cockpit/mock_data.py` — still used by other panels until Sessions 4-7 wire them
- Account panel — still a placeholder
- Market pulse panel — still mock data, real wiring is Session 4
- Sector heatmap — still mock, Session 5
- Correlation matrix — still mock, Session 6
- Themes — leave `claude-warm` and `blue-orange` alone unless a bug needs fixing for the flash
- All existing CLI scripts (`get_data`, `run_backtest`, etc.) — unchanged
- `marketdata/` — unchanged (Session 1 work; the API is what it is)
- `core/quote.py`, `core/security.py`, `core/transaction.py` — unchanged
- `broker/` — unchanged
- Schwab provider beyond the stub — Session 8

If you find yourself wanting to touch any of these, stop and ask the owner.

---

## 12. What to do if stuck

If you hit something not covered here:

1. **Textual API surprise:** Textual evolves fast; the version in this project (8.x or later per Session 2 debrief) may differ from docs/examples. Check the actual installed version (`python -c "import textual; print(textual.__version__)"`) and consult that version's docs. Falling back to a slightly different primitive (e.g. `VerticalScroll` instead of `DataTable`) is acceptable as long as the acceptance criteria pass.

2. **yfinance rate limit during testing:** If you trip yfinance's rate limit, wait 5-10 minutes and resume. Don't add exponential backoff in this session — the polling interval is already 30s which should be fine in practice. If it becomes an issue in real use, the owner will report it.

3. **Sparkline still looks bad after the fix:** The percentile-based approach should mostly work, but if real-world data still produces flat-looking sparklines, try plotting *daily percentage changes* instead of *prices*. That gives much more dynamic range. Document the decision in the debrief.

4. **Flash bug cause is exotic:** If the flash bug turns out to be a Textual version issue with no clean fix, document it in the debrief with what you tried, and ship the wiring without flash. Owner accepts shipping a useful-but-imperfect cockpit over polished delay.

5. **YAML hot-reload race:** If editing `watchlists.yaml` mid-poll causes problems, lock or copy the dict during reads. Don't over-engineer — just don't crash.

6. **Workflow becomes huge:** If `build_watchlist_snapshot` is creeping past ~150 lines, factor out helpers (one per ticker, e.g. `_fetch_one_ticker(ticker) -> TickerRow | TickerError`). Keep the public surface minimal.

7. **You think the architecture is wrong:** Stop and write it up in the debrief rather than refactoring. Architecture decisions go to Opus in a planning conversation, not executed unilaterally.

---

## 13. Debrief expectations

At session end, produce `notes/session-3-debrief.md` with:

1. Which acceptance criteria pass / partial / fail
2. Files created, files modified, files deleted (with line counts if convenient)
3. Findings: anything surprising about Textual, yfinance, DataService routing, etc.
4. Open questions for the next planning conversation
5. The actual root cause of the flash bug from Session 2
6. The actual root cause of the sparkline issue (was it range, downsampling, or something else)
7. Any anti-pattern temptations resisted and how
8. Estimated readiness for Session 4 (market pulse — same pattern, different tickers)

The debrief lives in `notes/`. Once written, Opus reviews it in the Session 4 planning chat.

---

## 14. Owner context reminders

Things to keep in mind that aren't strictly technical:

- Owner's background is FORTRAN scientific computing — FORTRAN analogies in comments and debrief are welcomed
- Owner prefers terminal/CLI and vim-editable config over UI menus — the YAML schema honors this
- Pro-plan budget cap: $5/month overage. Session must fit comfortably in one Claude Code session
- The cockpit is for the owner's learning and situational awareness, not for trading. Read-only, no order placement
- "Useful prototype over a beautiful unfinished one" — if you have to choose, ship working acceptance criteria over polish
