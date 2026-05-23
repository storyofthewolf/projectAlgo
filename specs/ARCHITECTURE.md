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

Adding a new source means adding one implementation of `MarketDataSource` and registering it. Nothing else changes. The cockpit, analysis, and scripts all care about *data*, not where it came from.

### 4. Domain models are passive

A `Stock` is a data container with a ticker and optional price history. It does not know how to download itself, plot itself, or compute indicators. Those are jobs for other layers.

FORTRAN parallel: derived types hold state; subroutines act on them. You wouldn't bolt `read_netcdf_file()` onto a `grid_t` type.

### 5. Computation is stateless

Analysis functions (`analysis/`) are stateless: they take inputs, return outputs, no side effects. This makes them composable, testable, and reusable across different consumers (cockpit, scripts, future browser views).

### 6. Workflows orchestrate; UI renders

A **workflow** is a user-meaningful task that composes data fetching plus analysis into a typed result (a "snapshot"). The UI consumes snapshots and renders them. The UI never calls analysis functions directly; it never knows about data sources.

Workflows return data structures, not pixels. A `SectorSnapshot` is fields and arrays, not a rendered heatmap. This is what lets the same workflow be consumed by the cockpit TUI, a CLI command, or any future view.

FORTRAN parallel: workflows are the experiment driver scripts (messy glue that loads forcings, runs physics in order, checkpoints output). Analysis modules are clean numerical kernels.

### 7. Text-file configuration over UI menus

`cockpit.toml` for app settings. `watchlists.yaml` for watchlists. All hand-editable in vim. The owner prefers typing to clicking.

There is no "settings UI" inside the cockpit. To change behavior, edit the file and restart (or press `R` for hot-reload where applicable).

### 8. Terminal-first

The cockpit is the primary and sole UI. Browser-based deep-dives (Dash/Plotly) are a possibility for the future but are not a current architectural feature. No subprocess-launched Dash servers currently exist in the workflow.

### 9. Information density over whitespace

Aesthetic: Bloomberg-terminal layout density combined with Claude Code's warm color palette. Tight panels, all-caps tickers, decimal-aligned numbers, single-line box-drawing borders, em-dashes for missing data, flash-on-update for live changes.

The cockpit should feel *alive*. Refresh updates individual cells with color flashes, not full-screen redraws.

### 10. Python all the way down

No C/C++/Rust extensions. NumPy and pandas already use compiled BLAS/LAPACK for hot numerical paths. If a future bottleneck materializes (unlikely for personal-scale workloads), the escape ladder is: vectorize → Numba JIT → Cython → Polars. Never preemptively.

Rationale: flow-state development requires fast iteration. Python's edit-and-rerun cycle beats compiled-language toolchains for a project where the goal is the owner's own learning, not machine performance.

---

## The layers

### Data layer

**Package:** `marketdata/`

**Responsibility:** Fetching raw market data from external sources, caching it, providing a unified interface.

**Key types:**
- `MarketDataSource` (ABC) — interface every source implements
- `DataService` — the public entry point; handles routing and caching
- `LocalCache` — CSV-based local cache; one canonical file per `(ticker, interval)`, smart range-coverage merging on put
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

**Cache logic:** `{TICKER}_{interval}.csv` canonical filename. `get()` serves any sub-window the stored file covers; `put()` merges and widens. Legacy dated files are inert.

**Canonical DataFrame shape:** DatetimeIndex; columns `['Open', 'High', 'Low', 'Close', 'Volume']` in that order; float64 numeric except Volume which is int64.

### Domain models

**Package:** `core/`

**Responsibility:** Passive data containers that define the vocabulary of the system. No I/O, no computation, no behavior beyond simple property queries.

**Key types:**
- `Stock` (`core/security.py`) — ticker + optional `historical_data` DataFrame
- `Quote` (`core/quote.py`) — frozen dataclass: ticker, price, timestamp, optional bid/ask/volume/previous_close, computed `change` and `change_pct` properties

Future additions: `Option`, `OptionChain`, `Position`, `Portfolio`.

### Analysis

**Package:** `analysis/`

**Responsibility:** Stateless computational functions on market data.

**Current modules:**
- `technical_analysis.py` — `calculate_sma`, `calculate_rsi`
- `market_analysis.py` — `load_aligned_returns`, `calculate_relative_strength`, `calculate_correlation_matrix`, `summarize_correlations`

**Conventions:** functions take pandas Series/DataFrames, return same. No state. No side effects.

### Broker

**Package:** `broker/`

**Responsibility:** Schwab-specific code that is *not* market data. Authentication, account access.

**Modules:**
- `schwab_client.py` — OAuth singleton, auth token management
- `account.py` — balances, positions, account summary

### Workflows

**Package:** `workflows/`

**Responsibility:** Orchestration. Compose data fetching + analysis into typed snapshots that the UI consumes.

**Pattern:** each workflow defines a snapshot dataclass and exposes a `build_<name>(config, data_service=None)` function. `data_service` defaults to `get_data_service()` so screens never import the data layer directly. Per-cell failure tolerance: one bad ticker fails locally, panel still renders.

**Existing workflows:**

| Module | Snapshot | Purpose |
|--------|----------|---------|
| `watchlist_snapshot.py` | `WatchlistSnapshot` | Live quotes + recent history for a list of tickers |
| `market_pulse_snapshot.py` | `PulseSnapshot`, `PulseTicker` | 8 configurable macro tickers with sparklines |
| `sector_snapshot.py` | `SectorSnapshot`, `SectorCell` | 11 SPDR ETF RS vs SPY, gradient cells |
| `multi_timeframe_sector_snapshot.py` | `MultiTimeframeSectorSnapshot`, `SectorRow`, `TimeframeRS` | RS across configurable timeframes for sector deep-dive |
| `correlation_snapshot.py` | `CorrelationSnapshot`, `RankedPair` | Pairwise correlation matrix + ranked pairs |
| `ticker_metrics_snapshot.py` | `TickerMetrics` | Scalar metrics for ticker drill-down: quote + 52W range + SMAs + RSI + RS vs SPY |

Workflows are the **single source of truth** for "how is this computed." If the cockpit and a CLI command both want a sector snapshot, they call the same workflow.

### Cockpit

**Package:** `cockpit/`

**Responsibility:** The terminal-resident TUI built with Textual. The primary UI for monitoring.

**Structure:**
- `app.py` — `CockpitApp` (Textual `App` subclass); global `slash` binding + `action_open_ticker_finder()` with pop-then-push drill-down logic
- `themes.py` — color palette definitions, theme registration (`THEMES_CONFIG`, `THEMES`, `THEME_NAMES`)
- `styles.tcss` — Textual CSS using theme variables
- `format.py` — numeric formatting helpers (`fmt_price`, `fmt_pct`, `fmt_volume`, `fmt_change`, `fmt_arrow`, `fmt_ticker`) plus gradient color helpers (`relative_strength_to_color`, `correlation_to_color`, `_gradient_color`)
- `screens/` — screen modules (see table below)
- `widgets/` — reusable atoms (see table below)
- `watchlists/` — `yaml_provider.py`, `schwab_provider.py`, `registry.py`, `base.py`

**Screens:**

| Module | Class | Entry / Exit |
|--------|-------|-------------|
| `screens/home.py` | `HomeScreen` | App default |
| `screens/help.py` | `HelpScreen` | `?` / `Esc` |
| `screens/sectors.py` | `SectorDeepDiveScreen` | `S` / `Esc` |
| `screens/correlations.py` | `CorrelationDeepDiveScreen` | `C` / `Esc` |
| `screens/ticker_finder_modal.py` | `TickerFinderModal` | `/` (modal) |
| `screens/ticker_detail.py` | `TickerDetailScreen` | `/` + ticker enter / `Esc` |

**Widgets:**

| Module | Class | Purpose |
|--------|-------|---------|
| `widgets/clock_header.py` | `ClockHeader` | ET time, ticks every second, shows market state |
| `widgets/command_footer.py` | `CommandFooter` | `[KEY]LABEL` footer bar |
| `widgets/panel_frame.py` | `PanelFrame` | Border + title wrapper |
| `widgets/price_cell.py` | `PriceCell` | Flashes on price change, settles to directional color |
| `widgets/pct_cell.py` | `PctCell` | Same flash pattern as PriceCell |
| `widgets/sparkline.py` | `Sparkline` | 8-level unicode block sparklines |
| `widgets/watchlist_panel.py` | `WatchlistPanel`, `WatchlistRow` | Live quotes, hot-reload |
| `widgets/market_pulse_panel.py` | `MarketPulsePanel`, `PulseCell` | 4×2 grid; price/index/yield formats |
| `widgets/sector_panel.py` | `SectorPanel`, `SectorCell` | Single-row strip; gradient backgrounds |
| `widgets/sector_table.py` | `SectorTable` | Rich-markup table; column focus, sort, gradient cells |
| `widgets/correlation_panel.py` | `CorrelationPanel` | Home lower-triangle matrix, gradient cells |
| `widgets/correlation_table.py` | `CorrelationTable` | Deep-dive full N×N matrix |
| `widgets/ranked_pair_list.py` | `RankedPairList` | Deep-dive pairs ranked high→low, text-color gradient |
| `widgets/ticker_metrics_panel.py` | `TickerMetricsPanel` | Drill-down scalar metrics panel: 11 rows, two-column layout |

**Theme system:** dicts in `themes.py` define palettes. Active theme from `cockpit.toml`. Two themes currently: `claude-warm` (default, warm orange/cream on near-black) and `blue-orange` (colorblind-friendly). Cycle via `T`. `CockpitApp.get_css_variables()` is overridden to inject custom CSS variables (`$text-dim`, `$positive`, `$negative`, `$border`, `$gradient-positive`, `$gradient-negative`, `$gradient-neutral`, etc.) before every stylesheet parse — required because Textual resolves CSS vars from the default theme during first parse, which doesn't include our custom vars.

Themes also define a three-color gradient (`gradient_positive`, `gradient_negative`, `gradient_neutral`) used by sector, correlation, and ticker widgets for continuous-color magnitude encoding. Interpolated in linear RGB by `cockpit/format.py::_gradient_color()`.

**Numeric formatting rules:**
- Tickers: all-caps
- Prices: 2 decimals always (`187.42`)
- Percentages: signed, 2 decimals, `%` suffix (`+0.66%`)
- Volume: compact (`42.1M`, `1.2B`, `987K`)
- Changes: signed, 2 decimals
- Missing data: em dash (`—`)
- Sparklines: 8-level Unicode blocks (`▁▂▃▄▅▆▇█`)
- Direction: `▲ ▼ —`

**Layout target:** 120×30 minimum, 160×50 ideal. Below minimum: friendly resize overlay.

**Keyboard model:**

| Key | Action | Scope |
|-----|--------|-------|
| `Q` | Quit | global |
| `R` | Refresh data + reload config | global |
| `?` | Help screen | global |
| `T` | Cycle theme | global |
| `/` | Find ticker (drill-down) | global |
| `W` | Cycle watchlist | home |
| `S` | Open sector deep-dive | home |
| `C` | Open correlation deep-dive | home |
| `Esc` | Return to previous screen | all non-home |
| `Tab` / `Shift+Tab` | Focus next / previous panel | all |
| `← →` | Move column focus | sector deep-dive |
| `Enter` | Sort by focused column | sector deep-dive |
| `M` | Cycle method | correlation deep-dive |
| `[` / `]` | Decrease / increase lookback | correlation deep-dive |
| `P` | Cycle preset | correlation deep-dive |

### Configuration

**Package:** `config/`

**Files:**
- `cockpit.toml` (at project root) — app-wide settings
- `watchlists.yaml` (at project root) — watchlist definitions

**Module:** `config/settings.py` — `Settings` frozen dataclass with `load()` classmethod. Resolves paths relative to project root. Single source of truth.

**Config dataclasses:**

| Class | TOML section | Purpose |
|-------|-------------|---------|
| `SectorConfig` | `[sectors]` | Home sector panel: lookback, comparison ticker, intensity |
| `SectorDeepDiveConfig` | `[sector_deep_dive]` | Timeframe list, sort defaults, refresh cadence |
| `CorrelationConfig` | `[correlations]` | Home panel: tickers, method, lookback, refresh |
| `CorrelationDeepDiveConfig` | `[correlation_deep_dive]` | Deep-dive: presets, method, lookback options, refresh |
| `TickerDetailConfig` | `[ticker_detail]` | Drill-down: SMA windows, RSI config, refresh cadence |

### Scripts

**Package:** `scripts/`

**Responsibility:** CLI entry points. Not importable as library code.

**Current entry points:**

| Script | Purpose |
|--------|---------|
| `get_data.py` | Fetch and cache OHLCV |
| `account.py` | Schwab account summary |
| `quote.py` | Schwab live quotes |
| `cockpit.py` | Launch the TUI |
| `schwab_auth.py` | Schwab OAuth flow |
| `clean_data.py` | Cache maintenance utility |
| `run_analysis.py` | Legacy market analysis helper (pre-refactor; references old architecture) |
| `verify_session9.py` | Post-cleanup import-tree verifier |

---

## File layout (current state, post-Session-9)

```
projectAlgo/
├── cockpit.toml                  # app config
├── watchlists.yaml               # watchlist definitions
├── README.md
├── CLAUDE.md
├── DEVELOPER_NOTES.md
├── requirements.txt
│
├── config/
│   ├── __init__.py
│   └── settings.py               # Settings + all config dataclasses
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
│   └── quote.py                  # Quote
│
├── broker/                       # Schwab non-market-data
│   ├── __init__.py
│   ├── schwab_client.py
│   └── account.py
│
├── workflows/                    # orchestration layer
│   ├── __init__.py
│   ├── watchlist_snapshot.py
│   ├── market_pulse_snapshot.py
│   ├── sector_snapshot.py
│   ├── multi_timeframe_sector_snapshot.py
│   ├── correlation_snapshot.py
│   └── ticker_metrics_snapshot.py
│
├── analysis/                     # stateless computation
│   ├── __init__.py
│   ├── technical_analysis.py
│   └── market_analysis.py
│
├── cockpit/                      # the TUI
│   ├── __init__.py
│   ├── app.py
│   ├── themes.py
│   ├── styles.tcss
│   ├── format.py
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── home.py
│   │   ├── help.py
│   │   ├── sectors.py
│   │   ├── correlations.py
│   │   ├── ticker_finder_modal.py
│   │   └── ticker_detail.py
│   ├── widgets/
│   │   ├── __init__.py
│   │   ├── clock_header.py
│   │   ├── command_footer.py
│   │   ├── panel_frame.py
│   │   ├── price_cell.py
│   │   ├── pct_cell.py
│   │   ├── sparkline.py
│   │   ├── watchlist_panel.py
│   │   ├── market_pulse_panel.py
│   │   ├── sector_panel.py
│   │   ├── sector_table.py
│   │   ├── correlation_panel.py
│   │   ├── correlation_table.py
│   │   ├── ranked_pair_list.py
│   │   └── ticker_metrics_panel.py
│   └── watchlists/
│       ├── __init__.py
│       ├── base.py
│       ├── registry.py
│       ├── yaml_provider.py
│       └── schwab_provider.py
│
├── scripts/                      # CLI entry points
│   ├── get_data.py
│   ├── account.py
│   ├── quote.py
│   ├── cockpit.py
│   ├── schwab_auth.py
│   ├── clean_data.py
│   ├── run_analysis.py           # legacy; references pre-refactor architecture
│   └── verify_session9.py        # import-tree verifier
│
├── specs/                        # design documents
│   ├── ROADMAP.md
│   ├── ARCHITECTURE.md           # this file
│   └── session-{1..9}-spec.md   # historical record
│
├── notes/                        # session debriefs
│   └── session-{1..9}-debrief.md
│
└── data/                         # storage (not code)
    └── historical_data/          # cached CSV files
```

---

## Adding new capabilities

The architecture is designed so that adding a new feature follows a predictable recipe.

### Adding a new "room" (screen) to the cockpit

1. **New data?** Extend `marketdata/sources/` if a new source is needed. Usually not — most rooms reuse existing sources with different tickers.
2. **New domain concepts?** Add to `core/` if any. Usually not — most rooms are different views of `Stock`, `Quote`, etc.
3. **New computation?** Add functions to an existing `analysis/*.py` or create a new module.
4. **Compose into a snapshot.** Write a workflow in `workflows/` returning a typed dataclass.
5. **Render.** Write a screen in `cockpit/screens/`. Add a key binding. Render the snapshot.

The discipline: a UI screen never calls analysis functions directly; it always goes through a workflow. The workflow is the always-present middleman.

### Adding a new data source

1. Subclass `MarketDataSource` in `marketdata/sources/`.
2. Implement `name`, `get_historical_ohlcv`, `get_live_quote`, `supports_interval`, `is_available`.
3. Register in `DataService.__init__()`.
4. Add to `cockpit.toml` documentation as a valid `preferred_source` value.

### Adding a new theme

1. Add a dict entry to `THEMES_CONFIG` in `cockpit/themes.py` matching the existing shape (all required color keys including `gradient_positive`, `gradient_negative`, `gradient_neutral`).
2. Done. It appears in the `T` cycle automatically via `THEME_NAMES`.

### Adding a new keyboard binding

1. Add to `BINDINGS` in the relevant Textual app or screen.
2. Add the entry to the help screen (`cockpit/screens/help.py`) so users discover it.
3. Update `CommandFooter` if it's a global binding.

---

## Anti-patterns to avoid

These are patterns that look reasonable but violate the architecture. If a session spec or code change starts to look like one of these, stop and reconsider.

- **A UI screen calling `DataService` or analysis functions directly.** Always go through a workflow.
- **A workflow returning rendered output (HTML, terminal escape codes).** Workflows return data; UI renders.
- **A domain model with I/O methods.** `Stock.download_data()` was wrong; the same mistake should not return for `Option`, `Position`, etc.
- **Configuration scattered through code.** All settings come from `Settings` loaded once at startup.
- **Source-specific code outside `marketdata/sources/`.** If a workflow has `if source == 'schwab': ...`, the data layer is leaking.
- **Cockpit code that knows about specific data sources.** Cockpit only sees `DataService` and workflow snapshots.
- **Polishing things that aren't on the critical path.** The roadmap is the source of truth for what to build next.

---

## Cockpit workflow pattern (canonical)

All home-screen panels and deep-dive screens follow this template:

```
workflow function (pure data, no Textual, no asyncio)
    → HomeScreen/Screen reactive variable
    → @work(exclusive=True, group="group_name", thread=True) worker
       calls workflow, then call_from_thread(_set_var)
    → watch_<var>() reactive handler
    → panel widget .update_snapshot() or .update_metrics()
    → independent set_interval() timer for polling cadence
```

Rules:
- Workflows have no Textual imports and no asyncio
- Each panel has its own polling timer and exclusive worker group
- Timers run independently — one slow fetch doesn't block other panels
- Screens and widgets never import from `marketdata/` directly

---

## Performance notes

For context on what's fast enough:

- pandas/NumPy operations on daily-bar data for 10-100 tickers: milliseconds
- Schwab/yfinance API calls: 100-500 ms each (network bound)
- Correlation matrix (10 tickers, 252 days): ~5 ms
- Textual screen redraw: 5-20 ms
- Auto-refresh polling interval: 30s (pulse/watchlist), 5 min (sectors/correlations), 60s (deep-dive screens), 30s (ticker drill-down)

The system is **network-bound and human-bound**, not CPU-bound. Optimization energy should go into UI ergonomics and data quality, not performance.
