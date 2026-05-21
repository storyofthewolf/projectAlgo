# projectAlgo — Architecture

This document describes the architectural design of projectAlgo. It is the authoritative reference for "how is this codebase organized and why." Lives in `specs/ARCHITECTURE.md`, travels with the codebase.

When starting a new planning conversation, paste this along with `ROADMAP.md` and the latest debrief to bring a fresh Opus instance up to speed on design context.

---

## Design principles

These are the load-bearing decisions that everything else follows from.

### 1. Layered architecture with strict downward dependencies

The system is organized into layers. Each layer only depends on layers below it. Information flows up; dependencies flow down. No cycles.

This is the FORTRAN-equivalent of disciplined `USE` statements. The radiative transfer module knows nothing about which experiment is being run; the experiment driver knows about radiative transfer but not about plotting. Same principle.

### 2. The cockpit is a viewer, not a doer

Read-only. No order placement. No trading. The cockpit reads market data, presents it, and lets the human decide.

If live trading is ever added, it will be a *separate repository* that imports from this one, with a hard airlock. Mixing analysis code with order-placement code is how serious accidents happen.

### 3. The data layer is the center of gravity

Everything that wants market data goes through `DataService`. The service decides which source to use, handles caching, and abstracts away the differences between yfinance, Schwab, and any future source.

Adding a new source means adding one implementation of `MarketDataSource` and registering it. Nothing else changes. Strategies, the cockpit, analysis — all consumers — care about *data*, not where it came from.

### 4. Domain models are passive

A `Stock` is a data container with a ticker and optional price history. It does not know how to download itself, plot itself, or compute indicators. Those are jobs for other layers.

This was deliberately fixed in Session 1; the previous `Stock.download_data()` pattern violated single-responsibility and is gone.

FORTRAN parallel: derived types hold state; subroutines act on them. You wouldn't bolt `read_netcdf_file()` onto a `grid_t` type.

### 5. Computation is stateless

Analysis functions (`analysis/`), strategy logic (`strategies/`), options pricing (`options/`, future) are stateless: they take inputs, return outputs, no side effects. This makes them composable, testable, and reusable across different consumers (cockpit, scripts, future Dash apps).

### 6. Workflows orchestrate; UI renders

A **workflow** is a user-meaningful task that composes data fetching plus analysis into a typed result (a "snapshot"). The UI consumes snapshots and renders them. The UI never calls analysis functions directly; it never knows about data sources.

Workflows return data structures, not pixels. A `SectorSnapshot` is fields and arrays, not a rendered heatmap. This is what lets the same workflow be consumed by the cockpit TUI, a Dash deep-dive, or a CLI command.

FORTRAN parallel: workflows are the experiment driver scripts (messy glue that loads forcings, runs physics in order, checkpoints output). Analysis modules are clean numerical kernels.

### 7. Text-file configuration over UI menus

`cockpit.toml` for app settings. `watchlists.yaml` (future) for watchlists. Other config files as needed. All hand-editable in vim. The owner prefers typing to clicking.

There is no "settings UI" inside the cockpit. To change behavior, edit the file and restart (or press `r` for hot-reload where applicable).

### 8. Terminal-first, with browser for deep dives

The primary UI is the Textual TUI. Browser-based Dash apps are reserved for *exploratory deep-dives* where mouse interaction adds value (zooming a multi-year candlestick, hovering correlation cells in a 15×15 heatmap). The cockpit launches Dash deep-dives as subprocesses; they communicate via files on disk, not shared memory.

### 9. Information density over whitespace

Aesthetic: Bloomberg-terminal layout density combined with Claude Code's warm color palette. Tight panels, all-caps tickers, decimal-aligned numbers, single-line box-drawing borders, em-dashes for missing data, flash-on-update for live changes.

The cockpit should feel *alive*. Refresh updates individual cells with color flashes, not full-screen redraws.

### 10. Python all the way down

No C/C++/Rust extensions. NumPy and pandas already use compiled BLAS/LAPACK for hot numerical paths. If a future bottleneck materializes (unlikely for personal-scale workloads), the escape ladder is: vectorize → Numba JIT → Cython → Polars → maybe-someday-pybind11. Never preemptively.

Rationale: flow-state development requires fast iteration. Python's edit-and-rerun cycle beats compiled-language toolchains for a project where the goal is the owner's own learning, not machine performance.

---

## The layers

### Data layer

**Package:** `marketdata/`

**Responsibility:** Fetching raw market data from external sources, caching it, providing a unified interface.

**Key types:**
- `MarketDataSource` (ABC) — interface every source implements
- `DataService` — the public entry point; handles routing and caching
- `LocalCache` — CSV-based local cache (Parquet upgrade possible later)
- `YFinanceSource`, `SchwabSource` — implementations

**Public API:**
- `get_data_service()` — module-level lazy singleton
- `service.get_historical_ohlcv(ticker, start, end, interval, source=None, use_cache=True)`
- `service.get_live_quote(ticker, source=None)`
- `service.get_live_quotes(tickers, source=None)`

**Routing logic** when `source=None`:
1. Use `settings.preferred_source`
2. If preferred source doesn't support the interval → fall back
3. If preferred source is unavailable (e.g., expired token) → fall back with warning log

**Cache logic:** exact-match on `(ticker, interval, start, end)`. Filename format `{TICKER}_{interval}_{YYYYMMDD}_{YYYYMMDD}.csv` (unchanged from original codebase). No smart range-coverage matching yet — possible future enhancement.

**Canonical DataFrame shape:** DatetimeIndex; columns `['Open', 'High', 'Low', 'Close', 'Volume']` in that order; float64 numeric except Volume which is int64. All sources must return this shape.

### Domain models

**Package:** `core/`

**Responsibility:** Passive data containers that define the vocabulary of the system. No I/O, no computation, no behavior beyond simple property queries.

**Key types:**
- `Stock` (in `core/security.py`) — ticker + optional `historical_data` DataFrame + metadata dict
- `Quote` (in `core/quote.py`) — frozen dataclass: ticker, price, timestamp, optional bid/ask/volume/previous_close, computed `change` and `change_pct` properties
- `Transaction` (in `core/transaction.py`) — BUY/SELL records with slippage-adjusted price, shares, cost basis, realized P&L; produced by `Backtester`

Future additions: `Option`, `OptionChain`, `Position`, `Portfolio`.

### Analysis

**Package:** `analysis/`

**Responsibility:** Stateless computational functions on market data.

**Current modules:**
- `technical_analysis.py` — `calculate_sma`, `calculate_rsi`, etc.
- `performance_metrics.py` — Sharpe, drawdown, win rate, profit factor
- `market_analysis.py` — `load_aligned_returns`, `calculate_correlation_matrix`, `summarize_correlations`

**Conventions:** functions take pandas Series/DataFrames, return same. No state. No side effects. Same function callable from cockpit, scripts, Dash apps.

### Strategies

**Package:** `strategies/`

**Responsibility:** Signal generation for backtesting. Subclasses of `BaseStrategy` implement `calculate_indicator()` and `generate_signals()`.

Currently has `SMACrossoverStrategy`. Architecture supports adding more freely.

### Backtesting

**Package:** `backtesting/`

**Responsibility:** Event-driven backtest engine. FIFO position tracking, slippage application, equity curve generation, trade log.

Currently long-only, one-position-at-a-time. More sophisticated portfolio backtesting is a future enhancement.

### Broker

**Package:** `broker/`

**Responsibility:** Schwab-specific code that is *not* market data. Authentication, account access.

**Modules:**
- `schwab_client.py` — OAuth singleton, auth token management
- `account.py` — balances, positions, account summary

`broker/market_data.py` was removed in Session 1 (Schwab market data moved into `marketdata/sources/schwab_source.py`).

### Workflows

**Package:** `workflows/`

**Responsibility:** Orchestration. Compose data fetching + analysis into typed snapshots that the UI consumes.

**Pattern:** each workflow defines a snapshot dataclass and exposes a function that returns it.

**Existing workflows:**
- `WatchlistSnapshot` — quotes + recent history for a list of tickers (Session 3, built)
- `MarketPulseSnapshot` — major index quotes + sparklines for 8 configurable tickers (Session 4, built)

**Planned workflows:**
- `SectorSnapshot` — 11 SPDR sector ETFs with relative strength vs SPY (Session 5)
- `CorrelationSnapshot` — correlation matrix + ranked pair list (Session 7)
- `BacktestResult` — equity curve + trades + metrics (already implicit; would formalize)
- `MorningBriefing` — composite snapshot for a "what to know this morning" view (future)

Workflows are the **single source of truth** for "how is this computed." If the cockpit, a Dash app, and a CLI command all want a sector snapshot, they all call the same workflow.

The Session 3-4 workflows established the canonical pattern:
1. Module-level snapshot dataclass(es) — pure data, no methods
2. `build_<name>_snapshot(config, data_service=None, now=None) -> Snapshot` function
3. Optional `data_service` parameter (defaults to `get_data_service()`) so HomeScreen never needs to import the data layer directly
4. Per-cell error handling: one bad ticker fails locally, panel still renders
5. Panel-level error field for catastrophic failures (e.g., benchmark ticker unavailable in Session 5)

### Visualization

**Package:** `visualization/`

**Responsibility:** Static plots (mplfinance) and Dash apps. Pre-cockpit infrastructure that still works — `view_backtest.py` in particular is a useful Dash dashboard for backtest results.

**Future Dash apps** (spawned from cockpit as subprocesses) will live alongside these or in a dedicated `viz/` package.

### Cockpit

**Package:** `cockpit/`

**Responsibility:** The terminal-resident TUI built with Textual. The primary UI for monitoring.

**Structure:**
- `app.py` — `CockpitApp` (Textual `App` subclass)
- `themes.py` — color palette definitions, theme registration
- `styles.tcss` — Textual CSS using theme variables
- `bindings.py` — shared keyboard binding definitions
- `format.py` — numeric formatting helpers (`fmt_price`, `fmt_pct`, `fmt_volume`, `fmt_change`, `fmt_arrow`, `fmt_ticker`)
- `mock_data.py` — temporary hardcoded data (deleted as real data wiring lands)
- `screens/` — `home.py`, `help.py`, (future) `sectors.py`, `correlations.py`, `ticker_detail.py`
- `widgets/` — reusable atoms: `Sparkline`, `PriceCell`, `PctCell`, `PanelFrame`, `ClockHeader`, `CommandFooter`

**Theme system:** dicts in `themes.py` define palettes. Active theme from `cockpit.toml`. Two themes currently: `claude-warm` (default, warm orange/cream on near-black) and `blue-orange` (colorblind-friendly, blue-up / orange-down). Cycle via `t`. Per-screen theme override is a planned future extension; infrastructure supports it.

Starting in Session 5, themes also define a three-color gradient (`gradient_positive`, `gradient_negative`, `gradient_neutral`) used by the sector heatmap for continuous-color magnitude encoding. The gradient is interpolated in linear RGB by `cockpit/format.py::relative_strength_to_color()`. This is the first cockpit visual that uses a continuous color scale rather than binary up/down state.

**Numeric formatting rules:**
- Tickers all-caps
- Prices: 2 decimals always (`187.42`)
- Percentages: signed, 2 decimals, `%` suffix (`+0.66%`)
- Volume: compact (`42.1M`, `1.2B`, `987K`)
- Changes: signed, 2 decimals
- Missing data: em dash (`—`)
- Sparklines: 8-level Unicode blocks (`▁▂▃▄▅▆▇█`)
- Direction: `▲ ▼ —`

**Layout target:** 120×30 minimum, 160×50 ideal. Below minimum: friendly "please resize" overlay.

**Keyboard model:** one keystroke per intent. Current global bindings: `q` quit, `r` refresh, `?` help, `t` theme cycle, `Esc` back, `Tab`/`Shift+Tab` panel focus. Reserved for future: `a` account, `s` sectors, `c` correlations, `w` watchlists, `/` find ticker.

### Configuration

**Package:** `config/`

**Files:**
- `cockpit.toml` (at project root) — app-wide settings
- `watchlists.yaml` (at project root, added Session 3) — watchlist definitions

**Module:** `config/settings.py` — `Settings` frozen dataclass with `load()` classmethod. Resolves paths relative to project root (not CWD). Single source of truth — no other code reads the TOML directly.

### Scripts

**Package:** `scripts/`

**Responsibility:** CLI entry points. Not importable as library code.

**Current entry points:**
- `get_data` — fetch and cache OHLCV
- `run_backtest` — run a backtest
- `correlations` — pairwise correlation matrix
- `account` (Schwab-dependent) — account summary
- `quote` (Schwab-dependent) — live quotes
- `inspect_pickle` — inspect a saved backtest result
- `cockpit` (added Session 2) — launches the TUI
- `schwab_auth` — Schwab OAuth flow

---

## File layout (current state, post-Session-4)

```
projectAlgo/
├── cockpit.toml                  # app config
├── README.md
├── CLAUDE.md
├── requirements.txt
├── pyproject.toml                # if present
│
├── config/
│   ├── __init__.py
│   └── settings.py
│
├── marketdata/                   # the data layer
│   ├── __init__.py
│   ├── service.py                # DataService
│   ├── cache.py                  # LocalCache
│   ├── exceptions.py
│   └── sources/
│       ├── __init__.py
│       ├── base.py               # MarketDataSource ABC
│       ├── yfinance_source.py
│       └── schwab_source.py
│
├── core/                         # domain models
│   ├── __init__.py
│   ├── security.py               # Stock
│   ├── quote.py                  # Quote
│   └── transaction.py            # Transaction
│
├── broker/                       # Schwab non-market-data
│   ├── __init__.py
│   ├── schwab_client.py
│   └── account.py
│
├── workflows/                    # orchestration layer
│   ├── __init__.py
│   ├── watchlist_snapshot.py     # Session 3
│   └── market_pulse_snapshot.py  # Session 4
│
├── analysis/                     # stateless computation
│   ├── __init__.py
│   ├── technical_analysis.py
│   ├── performance_metrics.py
│   └── market_analysis.py
│
├── strategies/
│   ├── __init__.py
│   ├── base_strategy.py
│   └── sma_crossover.py
│
├── backtesting/
│   ├── __init__.py
│   └── engine.py
│
├── visualization/                # static plots + Dash apps
│   ├── __init__.py
│   ├── plot_static.py
│   ├── view_stock.py
│   ├── view_backtest.py
│   └── indicator_plot_configs.py
│
├── cockpit/                      # the TUI
│   ├── __init__.py
│   ├── app.py
│   ├── themes.py
│   ├── styles.tcss
│   ├── bindings.py
│   ├── format.py
│   ├── watchlists.py             # Session 3
│   ├── mock_data.py              # temporary; deletes as real data lands
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── home.py
│   │   └── help.py
│   └── widgets/
│       ├── __init__.py
│       ├── sparkline.py
│       ├── price_cell.py
│       ├── pct_cell.py
│       ├── panel_frame.py
│       ├── clock_header.py
│       ├── command_footer.py
│       ├── watchlist_panel.py    # Session 3
│       └── market_pulse_panel.py # Session 4
│
├── scripts/                      # CLI entry points
│   ├── __init__.py
│   ├── get_data.py
│   ├── run_backtest.py
│   ├── correlations.py
│   ├── account.py
│   ├── quote.py
│   ├── inspect_pickle.py
│   ├── cockpit.py
│   └── schwab_auth.py
│
├── specs/                        # design documents
│   ├── ROADMAP.md
│   ├── ARCHITECTURE.md           # this file
│   ├── session-1-spec.md
│   ├── session-2-spec.md
│   ├── session-3-spec.md
│   ├── session-4-spec.md
│   └── session-5-spec.md
│
├── notes/                        # session debriefs
│   ├── session-1-debrief.md
│   ├── session-2-debrief.md
│   ├── session-3-debrief.md
│   └── session-4-debrief.md
│
└── data/                         # storage (not code)
    ├── historical_data/          # cached CSV files
    └── backtest_results/         # pickled backtest bundles
```

**Future additions:**
- `workflows/sector_snapshot.py` and `cockpit/widgets/sector_panel.py` — Session 5
- `cockpit/screens/sectors.py` — Session 6 (sector deep-dive)
- `workflows/correlation_snapshot.py` and `cockpit/screens/correlations.py` — Session 7
- `cockpit/screens/ticker_detail.py` — Session 8
- `options/` package — far future, when options room is built
- Per-screen theme assignment infrastructure use — future

---

## Adding new capabilities

The architecture is designed so that adding a new feature follows a predictable recipe.

### Adding a new "room" (screen) to the cockpit

1. **New data?** Extend `marketdata/sources/` if a new source is needed. Usually not — most rooms reuse existing sources with different tickers.
2. **New domain concepts?** Add to `core/` if any. Usually not — most rooms are different views of `Stock`, `Quote`, etc.
3. **New computation?** Add functions to an existing `analysis/*.py` or create a new module (e.g., `analysis/event_studies.py`, `analysis/macro.py`).
4. **Compose into a snapshot.** Write a workflow in `workflows/` returning a typed dataclass.
5. **Render.** Write a screen in `cockpit/screens/`. Add a key binding. Render the snapshot.

The discipline: a UI screen never calls analysis functions directly; it always goes through a workflow. The workflow is the always-present middleman. This feels like an extra step when a screen is simple but pays off the third time you reuse a workflow from a different UI context.

### Adding a new data source

1. Subclass `MarketDataSource` in `marketdata/sources/`.
2. Implement `name`, `get_historical_ohlcv`, `get_live_quote`, `supports_interval`, `is_available`.
3. Register in `DataService.__init__()` (or in a future plugin registry).
4. Add to `cockpit.toml` documentation as a valid `preferred_source` value.

### Adding a new strategy

1. Subclass `BaseStrategy` in `strategies/`.
2. Implement `calculate_indicator()` (adds columns to `self._data`) and `generate_signals()` (sets `self._data['signal']` to 1/-1/0).
3. Register in `STRATEGY_REGISTRY` in `scripts/run_backtest.py`.

### Adding a new indicator

1. Add `calculate_<name>(data, window, column='Close')` to `analysis/technical_analysis.py`.
2. Register in `visualization/indicator_plot_configs.py` for visualization integration.
3. The backtest dashboard auto-detects RSI-prefixed columns for oscillator panels; others overlay on price.

### Adding a new theme

1. Add a dict entry to `THEMES` in `cockpit/themes.py` matching the existing shape.
2. Done. It appears in the `t` cycle automatically.

### Adding a new keyboard binding

1. Add to `BINDINGS` in the relevant Textual app or screen.
2. Add the entry to the help screen so users discover it.
3. Update `CommandFooter` if it's a global binding.

---

## Anti-patterns to avoid

These are patterns that look reasonable but violate the architecture. If a session spec or code change starts to look like one of these, stop and reconsider.

- **A UI screen calling `DataService` or analysis functions directly.** Always go through a workflow.
- **A workflow returning rendered output (HTML, terminal escape codes).** Workflows return data; UI renders.
- **A domain model with I/O methods.** `Stock.download_data()` was wrong; the same mistake should not return for `Option`, `Position`, etc.
- **Configuration scattered through code.** All settings come from `Settings` loaded once at startup.
- **Source-specific code outside `marketdata/sources/`.** If a strategy or workflow has `if source == 'schwab': ...`, the data layer is leaking.
- **Cockpit code that knows about specific data sources.** Cockpit only sees `DataService` and workflow snapshots.
- **Polishing things that aren't on the critical path.** The roadmap is the source of truth for what to build next.

---

## Performance notes

For context on what's fast enough:

- pandas/NumPy operations on daily-bar data for 10-100 tickers: milliseconds
- Schwab/yfinance API calls: 100-500 ms each (network bound)
- Correlation matrix (10 tickers, 252 days): ~5 ms
- Textual screen redraw: 5-20 ms
- Auto-refresh polling interval: 30 seconds default

The system is **network-bound and human-bound**, not CPU-bound. Optimization energy should go into UI ergonomics and data quality, not performance.
