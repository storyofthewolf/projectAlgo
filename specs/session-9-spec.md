# Session 9 Spec — Codebase Cleanup and Deletion

**Audience:** Claude Code (Sonnet), executing in the projectAlgo repo on Eric's
personal machine.

**Operating discipline:** This is a deletion session, not a build session. The
goal is to remove code cleanly without breaking the cockpit. Mistakes here look
like broken imports, orphaned references in docs, or a cockpit that won't
launch. The spec is organized in five phases. **Do not begin a phase until the
previous phase's acceptance criteria are met.** Stop and report if you hit any
of the explicit "STOP" signals.

---

## Context: what is being deleted and why

The project thesis was revised after Session 8. The original plan included
backtesting, TA strategy generation, and cross-sectional screening; those are
now explicitly out of scope indefinitely. The cockpit is a **viewer, not a
doer** — read-only market monitoring, with a Schwab account panel coming in
Session 11.

This session deletes everything that does not serve the revised thesis,
shrinks the surviving ticker drill-down to a scalar metrics panel, and updates
all documentation to match.

The source of truth for what to delete vs. keep is `specs/ROADMAP.md` ("Session
9 — Codebase cleanup and deletion") and `specs/ARCHITECTURE.md`. This spec
codifies and extends those documents.

---

## Phase 1 — Pre-flight inventory (read-only)

**Goal:** Map the dependency graph of what is about to be deleted, before
touching anything. Surface any surprises while the codebase is still
reversible.

### Tasks

1. From the repo root, run `rg` (ripgrep) to find every file that imports from
   each soon-to-be-deleted module or script. Run these queries individually
   and collect the results:

   ```bash
   rg -l "from backtesting" --type py
   rg -l "import backtesting" --type py
   rg -l "from strategies" --type py
   rg -l "import strategies" --type py
   rg -l "from analysis.screener" --type py
   rg -l "from analysis.performance_metrics" --type py
   rg -l "from visualization" --type py
   rg -l "import visualization" --type py
   rg -l "from core.transaction" --type py
   rg -l "from universes" --type py
   rg -l "cockpit.widgets.ohlc_table" --type py
   rg -l "cockpit.widgets.price_chart" --type py
   rg -l "cockpit.widgets.indicator_panel" --type py
   rg -l "cockpit.widgets.ticker_header" --type py
   rg -l "scripts.run_backtest" --type py
   rg -l "scripts.scan" --type py
   rg -l "scripts.correlations" --type py
   rg -l "scripts.inspect_pickle" --type py
   ```

2. Inspect `workflows/ticker_detail_snapshot.py` and list its imports. This
   workflow survives but will be shrunk in Phase 2. Record what it currently
   imports — confirm it pulls from `analysis/technical_analysis.py` (SMA, RSI)
   and `analysis/market_analysis.py` (for RS), and identify any unexpected
   imports.

3. Inspect `cockpit/screens/ticker_detail.py` and list the widgets it currently
   composes. Confirm: `TickerHeader`, `OHLCTable`, `PriceChart`,
   `IndicatorPanel`. Note any other widgets imported.

4. Confirm `requirements.txt` lists every dependency being removed:
   `pandas-ta`, `textual-plotext`, `mplfinance`, `dash`, `plotly`. Note their
   current pinned versions and exact line positions for the Phase 5 edit.

5. Produce a dependency report at `notes/session-9-preflight.md` with this
   structure:

   ```
   # Session 9 Preflight Inventory

   ## Dependents of modules to be deleted
   - backtesting/: [list of files importing from it]
   - strategies/: [...]
   - analysis/screener.py: [...]
   - analysis/performance_metrics.py: [...]
   - visualization/: [...]
   - core/transaction.py: [...]
   - universes/: [...]
   - cockpit/widgets/ohlc_table.py: [...]
   - cockpit/widgets/price_chart.py: [...]
   - cockpit/widgets/indicator_panel.py: [...]
   - cockpit/widgets/ticker_header.py: [...]

   ## Ticker detail workflow imports
   [imports from workflows/ticker_detail_snapshot.py]

   ## Ticker detail screen widget composition
   [widgets used in cockpit/screens/ticker_detail.py]

   ## requirements.txt lines to remove
   [exact lines and their positions]

   ## Surprises
   [anything unexpected — modules referenced from places not in the deletion
    list, orphan imports, etc. Empty section if none.]
   ```

### Acceptance criteria — Phase 1

- [ ] All `rg` queries run; results collected.
- [ ] `notes/session-9-preflight.md` exists and is complete.
- [ ] **STOP signal:** if any of the following is true, stop and report
  before continuing to Phase 2:
  - A surviving module (anything in `marketdata/`, `core/security.py`,
    `core/quote.py`, `config/`, `workflows/` other than ticker_detail,
    `cockpit/` other than the four orphan widgets, `analysis/` other than
    screener and performance_metrics) imports from a to-be-deleted module.
  - `workflows/ticker_detail_snapshot.py` imports from `analysis/screener.py`
    or `analysis/performance_metrics.py`.
  - The ticker drill-down screen composes a widget not in the expected list.

If you see any of these, write the finding to the "Surprises" section and
**stop**. Do not proceed.

---

## Phase 2 — Ticker drill-down rescope

**Goal:** Replace the ticker drill-down with a single scalar metrics panel.
Shrink the workflow to match. Leave the now-orphaned widget files
(`ohlc_table.py`, `price_chart.py`, `indicator_panel.py`, `ticker_header.py`)
on disk — Phase 4 deletes them. Decoupling deletion from rescoping keeps each
step's failure surface small.

### Design

#### The new scalar widget

Name: `TickerMetricsPanel`, in `cockpit/widgets/ticker_metrics_panel.py`.

Layout: a single panel, two columns (label | value), 10–12 rows. No scrolling.
Rendered with Rich markup inside a `Static` widget, similar in style to how
`IndicatorPanel` rendered before but without the chart context. Wrapped in a
`PanelFrame` with title `"<TICKER> — METRICS"`.

Rows (in this order):

| Label | Value | Notes |
|---|---|---|
| `PRICE` | `$XX.XX` | from quote |
| `CHANGE` | `+X.XX  +X.XX%` | today's change, signed, colored ±/neutral |
| `VOLUME` | `XX.XM` | compact format from `fmt_volume` |
| `52W HIGH` | `$XX.XX` | from 252-day window |
| `52W LOW` | `$XX.XX` | from 252-day window |
| `52W RANGE` | `XX%` | position within range, 0% = at low, 100% = at high |
| `SMA 20` | `$XX.XX  (+X.XX%)` | SMA value and % distance of price from it |
| `SMA 50` | `$XX.XX  (+X.XX%)` | same |
| `SMA 200` | `$XX.XX  (+X.XX%)` | same |
| `RSI(14)` | `XX.X  REGIME` | value + regime label (overbought/neutral/oversold) |
| `RS vs SPY (1M)` | `+X.XX%` | 21-day relative strength vs SPY |

That's 11 rows. The `% distance from SMA` and RS values should color positive
green/up and negative red/down using existing theme variables (`$positive`,
`$negative`). RSI regime label colors: overbought (≥70) = `$negative`,
oversold (≤30) = `$positive`, neutral = `$text-dim`. 52W RANGE position is
neutral-colored (it's not directional).

Use existing helpers from `cockpit/format.py`: `fmt_price`, `fmt_pct`,
`fmt_volume`, `fmt_change`. Add a new helper if needed for "price-with-pct-in-
parens" but prefer composing existing ones.

#### Workflow shrinkage

`workflows/ticker_detail_snapshot.py` currently returns a `TickerDetailSnapshot`
with full OHLC, full SMA series, full RSI series, and a stats sub-object. The
new UI consumes only terminal scalars, so the workflow should return only
terminal scalars.

Replace the existing dataclasses with:

```python
from dataclasses import dataclass
from datetime import datetime
from core.quote import Quote

@dataclass(frozen=True)
class TickerMetrics:
    ticker: str
    quote: Quote | None              # today's price, change, volume
    high_52w: float | None
    low_52w: float | None
    range_position_pct: float | None # 0-100, where 100 = at 52W high
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    pct_vs_sma_20: float | None      # signed, % distance of price above SMA
    pct_vs_sma_50: float | None
    pct_vs_sma_200: float | None
    rsi_14: float | None
    rsi_regime: str | None           # "overbought" | "neutral" | "oversold"
    rs_spy_1m: float | None          # 21-day RS vs SPY, percent
    as_of: datetime
    error: str | None = None

def build_ticker_metrics(ticker: str, config, data_service=None) -> TickerMetrics:
    """
    Build a scalar metrics snapshot for a single ticker.

    Fetches ~260 days of daily OHLCV for the ticker plus SPY (for RS),
    computes the scalars listed in TickerMetrics, returns. Any per-field
    failure leaves that field None and continues; overall fetch failure
    sets `error` and leaves all fields None.

    No yfinance.Ticker.info call. Company longName is not used.
    """
```

Rename the file to `workflows/ticker_metrics_snapshot.py` to reflect the
narrower scope. Old name leaks the "detail" framing the screen no longer
delivers.

Drop the `yfinance.Ticker(ticker).info` longName call entirely. This removes
a ~500ms blocking network call and a yfinance-specific dependency from the
workflow. The screen header uses the ticker symbol only.

The function takes `config: TickerDetailConfig` (for SMA windows + RSI period
+ refresh interval) and `data_service: DataService | None = None` (defaults
to `get_data_service()`). Match the existing signature pattern of other
workflows.

#### Screen rewrite

`cockpit/screens/ticker_detail.py` is replaced with a much simpler screen
composing the single `TickerMetricsPanel`. Class name stays
`TickerDetailScreen` (already wired into `app.py`'s pop-then-push logic for
`/`-launches). Keep the existing `__init__(ticker: str)` signature.

The screen:

- Composes a `ClockHeader`, a single `TickerMetricsPanel`, and a
  `CommandFooter`.
- Holds a `metrics: reactive[TickerMetrics | None] = reactive(None)`.
- Has a `@work(exclusive=True, group="ticker_metrics", thread=True)` worker
  that calls `build_ticker_metrics()` and updates the reactive via
  `call_from_thread`.
- Polls on the `refresh_interval_seconds` from `TickerDetailConfig`.
- Bindings: `Esc` (pop), `R` (refresh now), `Q` (quit), `T` (cycle theme),
  `?` (help).

Bindings removed: `J`/`K`/`↓`/`↑` (no scrolling, single panel fits in one
screen). Binding removed: `P` (no Dash launch).

#### Config

`TickerDetailConfig` in `config/settings.py` survives, but field usage
changes. Audit fields:

- `sma_windows: list[int]` — KEEP (used for SMA computation; default
  `[20, 50, 200]`).
- `rsi_period: int` — KEEP (default `14`).
- `rsi_overbought: float`, `rsi_oversold: float` — KEEP (default `70.0`,
  `30.0`).
- `refresh_interval_seconds: int` — KEEP.
- Anything else (number of OHLC display rows, chart configuration) — REMOVE
  from the dataclass.

Update the `[ticker_detail]` section of `cockpit.toml` to match the trimmed
dataclass. Keep the existing default values for surviving fields.

### Tasks

1. Write `workflows/ticker_metrics_snapshot.py` with `TickerMetrics` and
   `build_ticker_metrics()`.
2. Write `cockpit/widgets/ticker_metrics_panel.py` with `TickerMetricsPanel`.
3. Rewrite `cockpit/screens/ticker_detail.py` against the new widget +
   workflow. Keep class name `TickerDetailScreen`.
4. Trim `TickerDetailConfig` in `config/settings.py`. Update validators.
5. Trim `[ticker_detail]` section of `cockpit.toml`.
6. Add CSS for `TickerMetricsPanel` in `cockpit/styles.tcss` (it will reuse
   existing CSS vars; one new selector at most).
7. Delete `workflows/ticker_detail_snapshot.py`.
8. Smoke-test: `python3.14 -m scripts.cockpit`, press `/`, type a ticker
   (e.g., `AAPL`), confirm the metrics panel renders without errors, press
   `Esc`, confirm return to home, press `Q` to quit.

### Acceptance criteria — Phase 2

- [ ] `workflows/ticker_metrics_snapshot.py` exists, has docstrings,
  returns `TickerMetrics`.
- [ ] `workflows/ticker_detail_snapshot.py` is deleted.
- [ ] No remaining file in the repo imports from
  `workflows.ticker_detail_snapshot` (verify with `rg`).
- [ ] `cockpit/widgets/ticker_metrics_panel.py` exists with
  `TickerMetricsPanel` class.
- [ ] `cockpit/screens/ticker_detail.py` composes only `ClockHeader`,
  `TickerMetricsPanel`, `CommandFooter`. It does NOT import
  `OHLCTable`, `PriceChart`, `IndicatorPanel`, or `TickerHeader`.
- [ ] No remaining file imports `yfinance.Ticker(...).info` — search with
  `rg "\.Ticker\(" --type py` and confirm no `.info` access.
- [ ] `python3.14 -m scripts.cockpit` launches; `/` + `AAPL` + Enter shows
  the new scalar panel; `Esc` returns to home; `Q` quits cleanly.

---

## Phase 3 — Script deletions (leaf-of-graph)

**Goal:** Delete CLI scripts that have no internal dependents. These are
import-graph leaves; removing them is safe and fast.

### Tasks

Delete these files:

- `scripts/run_backtest.py`
- `scripts/scan.py`
- `scripts/correlations.py`
- `scripts/inspect_pickle.py`

After deletion, verify the cockpit still launches:

```bash
python3.14 -m scripts.cockpit
# Press Q to quit.
```

### Acceptance criteria — Phase 3

- [ ] Four script files are gone.
- [ ] `python3.14 -m scripts.cockpit` launches without error.
- [ ] `rg "scripts.run_backtest|scripts.scan|scripts.correlations|scripts.inspect_pickle" --type py`
  returns no results from surviving code (matches only in `notes/` and
  `specs/` are fine — those are historical record and should not be edited).

---

## Phase 4 — Module deletions

**Goal:** Delete entire directories and orphaned widget files. After each
sub-step, run an import smoke check to catch breakage immediately.

### Order

Do these in order. Run the import smoke check after each step.

#### 4.1 — Orphaned cockpit widgets

```bash
rm cockpit/widgets/ohlc_table.py
rm cockpit/widgets/price_chart.py
rm cockpit/widgets/indicator_panel.py
rm cockpit/widgets/ticker_header.py
```

If `cockpit/widgets/__init__.py` exports any of these, remove those exports.

**Smoke check:**
```bash
python3.14 -c "from cockpit.app import CockpitApp; print('ok')"
```

#### 4.2 — Backtesting and strategies

```bash
rm -rf backtesting/
rm -rf strategies/
```

**Smoke check:**
```bash
python3.14 -c "from cockpit.app import CockpitApp; print('ok')"
```

#### 4.3 — Analysis trims

```bash
rm analysis/screener.py
rm analysis/performance_metrics.py
```

If `analysis/__init__.py` exports anything from these, remove those exports.

**Smoke check:**
```bash
python3.14 -c "from cockpit.app import CockpitApp; print('ok')"
python3.14 -c "from analysis.technical_analysis import calculate_sma, calculate_rsi; print('ok')"
python3.14 -c "from analysis.market_analysis import load_aligned_returns, calculate_relative_strength, calculate_correlation_matrix, summarize_correlations; print('ok')"
```

#### 4.4 — Visualization

```bash
rm -rf visualization/
```

**Smoke check:**
```bash
python3.14 -c "from cockpit.app import CockpitApp; print('ok')"
```

#### 4.5 — Domain model trim and universes

```bash
rm core/transaction.py
rm -rf universes/
```

If `core/__init__.py` exports `Transaction`, remove that export.

**Smoke check:**
```bash
python3.14 -c "from cockpit.app import CockpitApp; print('ok')"
python3.14 -c "from core.security import Stock; from core.quote import Quote; print('ok')"
```

#### 4.6 — Deprecated mock data and backtest results directory

```bash
rm cockpit/mock_data.py
rm -rf data/backtest_results/
```

**Smoke check:**
```bash
python3.14 -c "from cockpit.app import CockpitApp; print('ok')"
python3.14 -m scripts.cockpit
# Press Q to quit.
```

### Acceptance criteria — Phase 4

- [ ] All listed files and directories are gone.
- [ ] All smoke checks pass (each printed `ok` or the cockpit launched).
- [ ] `rg "from backtesting|from strategies|from analysis.screener|from analysis.performance_metrics|from visualization|from core.transaction|from universes" --type py`
  returns no results from surviving code.
- [ ] No `cockpit/widgets/__init__.py` reference to deleted widgets.
- [ ] `python3.14 -m scripts.cockpit` launches; the `/` drill-down works;
  `S` sector deep-dive works; `C` correlation deep-dive works; `?` help
  works; `Esc` returns to home from each.

---

## Phase 5 — Documentation, requirements, and verifier

**Goal:** Update every document that references the deleted features. Write
a verifier script. Run it green.

This phase is the easiest to half-finish. Be thorough.

### 5.1 — `requirements.txt`

Remove these lines:

- `pandas-ta`
- `textual-plotext`
- `mplfinance`
- `dash`
- `plotly`

Preserve version pins on surviving dependencies. Do not reorder for cosmetics.

### 5.2 — `cockpit.toml`

The `[ticker_detail]` trim already happened in Phase 2. Audit the rest of the
file: no sections should reference deleted features. There should be nothing
to remove here, but verify.

### 5.3 — `CLAUDE.md`

Update against the post-cleanup repo. Sections to remove or rewrite:

- "Common Commands" section: remove `run_backtest.py`, `scan.py`,
  `correlations.py`, `inspect_pickle.py`, all `visualization.*` invocations.
- "Architecture" data flow diagram: trim `strategies → backtesting →
  visualization` from the chain. New chain:
  `UI / Views → Workflows → Analysis → Domain Models → Data Layer → Sources`.
  Note that `broker/` still sits alongside.
- "Key Data Structures": remove `Transaction`, `Backtester`, `BaseStrategy`.
- "Module Responsibilities" table: drop rows for deleted modules; update
  rows for surviving widgets/screens that changed; add row for
  `TickerMetricsPanel` and `workflows/ticker_metrics_snapshot.py`.
- "Adding a New Strategy", "Adding a New Indicator": delete these sections
  entirely.
- "Market Analysis" section: keep, but remove the CLI references to
  `scripts.correlations` (the CLI is gone). The library functions in
  `analysis/market_analysis.py` survive; document them as library-only.
- "Cross-Sectional Screening" section: delete entirely.
- "Cockpit TUI" → keyboard bindings table: remove `J/K` and `P` rows; remove
  any reference to OHLC table or Plotext chart in the package layout.
- "Known Limitations": update — drop bullets about backtest dashboard,
  Dash/Plotly heatmap subprocess, Plotext chart, `view_stock.py` subprocess.
  Keep the Schwab token expiration bullet and the
  `preferred_source = "yfinance"` bullet.

### 5.4 — `README.md`

Audit and trim. Same rules as `CLAUDE.md`: anything referencing deleted
features goes. If there's a quickstart example that uses `run_backtest.py`,
replace with `python3.14 -m scripts.cockpit`.

### 5.5 — `DEVELOPER_NOTES.md`

This file is dense with references to deleted features. Rewrite is more
efficient than surgical edits. Preserve only:

- "CLI Reference" sections for surviving scripts: `get_data.py`,
  `schwab_auth.py`, `account.py`, `quote.py`, `cockpit.py`, `clean_data.py`,
  `run_analysis.py`. Drop sections for everything else.
- "Workflows" section: keep entries for surviving workflows
  (`watchlist_snapshot`, `pulse_snapshot`, `sector_snapshot`,
  `multi_timeframe_sector_snapshot`, `correlation_snapshot`). Add entry for
  the new `build_ticker_metrics()` workflow. Drop entry for the old
  `build_ticker_detail_snapshot()`.
- "Cockpit Formatting Helpers" section: keep as-is.
- "Cockpit Widgets" section: drop entries for `OHLCTable`, `PriceChart`,
  `IndicatorPanel`, `TickerHeader`; add entry for `TickerMetricsPanel`.
- "Cockpit Screens" section: keep `CorrelationDeepDiveScreen` entry; update
  any other entries to reflect current state.
- "Configuration" section: update `cockpit.toml` and `config/settings.py`
  references to match the trimmed `TickerDetailConfig`.
- "Data Structures" section: replace the ticker-detail dataclasses with
  `TickerMetrics`.
- "Themes" section: keep as-is.
- "Key Constants" section: keep as-is.
- "Testing" section: replace "verify_session7.py" reference with a one-line
  pointer to the new `scripts/verify_session9.py`.
- "Session 7 Changes Summary" section: KEEP (it's historical record like
  `notes/`). Do not edit.

### 5.6 — `specs/ARCHITECTURE.md` — full rewrite

This document is the authoritative architectural reference. After the
cleanup, large portions of it are wrong. Rewrite it fully against the new
file tree.

Preserve the document's structure:

- "Design principles" (10 items) — review each; most survive untouched.
  Principle 5 ("Computation is stateless") references `strategies/` and
  `options/` — update. Principle 8 ("Terminal-first, with browser for deep
  dives") — Dash deep-dives are deferred indefinitely; rewrite to reflect
  that the cockpit is the sole UI and Dash is a possibility for the future,
  not a current architectural feature.
- "The layers" — drop "Strategies", "Backtesting", "Visualization" entirely.
  Keep "Data layer", "Domain models", "Analysis", "Broker", "Workflows",
  "Cockpit", "Configuration", "Scripts". Update each section's content
  against the post-cleanup tree. Update the workflow table to remove the
  old ticker detail row and add a `ticker_metrics_snapshot.py` row.
- "File layout (current state)" — full rewrite against the actual tree
  post-cleanup. Use `find . -type f -name "*.py" | sort` as a source of
  truth, plus `find . -maxdepth 2 -type d | sort` for directories. Update
  the heading from "post-Session-8" to "post-Session-9".
- "Adding new capabilities" — drop subsections for "Adding a new strategy",
  "Adding a new indicator", "Adding screener metrics". Keep "Adding a new
  room (screen)", "Adding a new data source", "Adding a new theme", "Adding
  a new keyboard binding".
- "Anti-patterns to avoid" — keep all; they all still apply.
- "Cockpit workflow pattern (canonical)" — keep as-is.
- "Performance notes" — update: drop the "yfinance.Ticker.info longName"
  bullet entirely (that call no longer exists). Other bullets survive.

The cockpit screens and widgets tables should be regenerated by inspection of
the actual files, not copy-paste from the pre-cleanup `ARCHITECTURE.md`.

### 5.7 — `scripts/verify_session9.py`

Write a single-purpose verifier script. It is a "did the surgery leave
everything connected" test, not a behavioral test.

Structure:

```python
"""
Session 9 verifier — confirms the post-cleanup tree is import-clean and
the cockpit's snapshot workflows can be instantiated.

Run: python3.14 -m scripts.verify_session9

Exit code 0 = all checks passed.
Exit code 1 = at least one check failed; details printed to stdout.
"""

import sys
import traceback

CHECKS = []  # list of (name, callable) pairs

def check(name):
    """Decorator to register a check."""
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator

# --- Imports of every surviving top-level module ---

@check("import config.settings")
def _():
    from config.settings import Settings
    Settings.load()  # confirms cockpit.toml parses

@check("import marketdata")
def _():
    from marketdata.service import get_data_service, DataService
    from marketdata.cache import LocalCache
    from marketdata.exceptions import DataSourceError
    from marketdata.sources.base import MarketDataSource
    from marketdata.sources.yfinance_source import YFinanceSource
    from marketdata.sources.schwab_source import SchwabSource

@check("import core")
def _():
    from core.security import Stock
    from core.quote import Quote
    # core.transaction should NOT be importable
    try:
        from core import transaction  # noqa: F401
        raise AssertionError("core.transaction should have been deleted")
    except ImportError:
        pass

@check("import broker")
def _():
    from broker import schwab_client
    from broker import account

@check("import analysis (trimmed)")
def _():
    from analysis.technical_analysis import calculate_sma, calculate_rsi
    from analysis.market_analysis import (
        load_aligned_returns,
        calculate_relative_strength,
        calculate_correlation_matrix,
        summarize_correlations,
    )
    # screener and performance_metrics should be gone
    for missing in ["analysis.screener", "analysis.performance_metrics"]:
        try:
            __import__(missing)
            raise AssertionError(f"{missing} should have been deleted")
        except ImportError:
            pass

@check("import workflows")
def _():
    from workflows.watchlist_snapshot import build_watchlist_snapshot
    from workflows.market_pulse_snapshot import build_pulse_snapshot
    from workflows.sector_snapshot import build_sector_snapshot
    from workflows.multi_timeframe_sector_snapshot import (
        build_multi_timeframe_sector_snapshot,
    )
    from workflows.correlation_snapshot import build_correlation_snapshot
    from workflows.ticker_metrics_snapshot import (
        build_ticker_metrics,
        TickerMetrics,
    )
    # old ticker_detail_snapshot should be gone
    try:
        import workflows.ticker_detail_snapshot  # noqa: F401
        raise AssertionError("workflows.ticker_detail_snapshot should be deleted")
    except ImportError:
        pass

@check("deleted modules are not importable")
def _():
    deleted = [
        "backtesting",
        "backtesting.engine",
        "strategies",
        "strategies.base_strategy",
        "strategies.sma_crossover",
        "visualization",
        "visualization.plot_static",
        "visualization.view_stock",
        "visualization.view_backtest",
    ]
    for mod in deleted:
        try:
            __import__(mod)
            raise AssertionError(f"{mod} should have been deleted")
        except ImportError:
            pass

@check("import cockpit app and screens")
def _():
    from cockpit.app import CockpitApp
    from cockpit.screens.home import HomeScreen
    from cockpit.screens.help import HelpScreen
    from cockpit.screens.sectors import SectorDeepDiveScreen
    from cockpit.screens.correlations import CorrelationDeepDiveScreen
    from cockpit.screens.ticker_finder_modal import TickerFinderModal
    from cockpit.screens.ticker_detail import TickerDetailScreen
    # Can instantiate the app class itself (Textual lets you do this without
    # running the event loop)
    CockpitApp()

@check("import cockpit widgets (surviving only)")
def _():
    from cockpit.widgets.clock_header import ClockHeader
    from cockpit.widgets.command_footer import CommandFooter
    from cockpit.widgets.panel_frame import PanelFrame
    from cockpit.widgets.price_cell import PriceCell
    from cockpit.widgets.pct_cell import PctCell
    from cockpit.widgets.sparkline import Sparkline
    from cockpit.widgets.watchlist_panel import WatchlistPanel
    from cockpit.widgets.market_pulse_panel import MarketPulsePanel
    from cockpit.widgets.sector_panel import SectorPanel
    from cockpit.widgets.sector_table import SectorTable
    from cockpit.widgets.correlation_panel import CorrelationPanel
    from cockpit.widgets.correlation_table import CorrelationTable
    from cockpit.widgets.ranked_pair_list import RankedPairList
    from cockpit.widgets.ticker_metrics_panel import TickerMetricsPanel
    # deleted widgets
    deleted = [
        "cockpit.widgets.ohlc_table",
        "cockpit.widgets.price_chart",
        "cockpit.widgets.indicator_panel",
        "cockpit.widgets.ticker_header",
        "cockpit.mock_data",
    ]
    for mod in deleted:
        try:
            __import__(mod)
            raise AssertionError(f"{mod} should have been deleted")
        except ImportError:
            pass

@check("import surviving scripts")
def _():
    # Importing scripts as modules confirms no syntax errors.
    # Note: some scripts have argparse at module level; import alone is fine.
    import scripts.get_data        # noqa: F401
    import scripts.account         # noqa: F401
    import scripts.quote           # noqa: F401
    import scripts.cockpit         # noqa: F401
    import scripts.schwab_auth     # noqa: F401
    import scripts.clean_data      # noqa: F401
    import scripts.run_analysis    # noqa: F401
    # deleted scripts
    deleted = [
        "scripts.run_backtest",
        "scripts.scan",
        "scripts.correlations",
        "scripts.inspect_pickle",
    ]
    for mod in deleted:
        try:
            __import__(mod)
            raise AssertionError(f"{mod} should have been deleted")
        except ImportError:
            pass

# --- Main ---

def main():
    failures = []
    for name, fn in CHECKS:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:
            failures.append((name, exc, traceback.format_exc()))
            print(f"  FAIL  {name}: {exc}")
    print()
    print(f"{len(CHECKS) - len(failures)} / {len(CHECKS)} checks passed.")
    if failures:
        print()
        for name, _exc, tb in failures:
            print(f"--- {name} ---")
            print(tb)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

This is the skeleton. The deleted-module list in
`deleted modules are not importable` may need extension based on what Phase 1
turned up.

Run it:

```bash
python3.14 -m scripts.verify_session9
```

All checks must pass. If any fail, **stop** and report — do not edit the
verifier to silence failures.

### 5.8 — Write `notes/session-9-debrief.md`

Write a debrief in the same style as prior session debriefs in `notes/`. It
should cover:

- What was deleted.
- The ticker drill-down rescope: design choices, what got kept and what got
  dropped, what the new widget renders.
- Any surprises from the Phase 1 inventory.
- Any deviations from this spec, with rationale.
- What the cockpit looks like post-cleanup (line count delta from
  `git diff --stat` if convenient).
- Recommended next steps for Session 10 (Schwab OAuth).

### Acceptance criteria — Phase 5

- [ ] `requirements.txt` has the five lines removed and nothing else changed.
- [ ] `CLAUDE.md`, `README.md`, `DEVELOPER_NOTES.md` are updated.
- [ ] `specs/ARCHITECTURE.md` is fully rewritten against the new tree.
- [ ] `scripts/verify_session9.py` exists and all checks pass.
- [ ] `notes/session-9-debrief.md` is written.
- [ ] `python3.14 -m scripts.cockpit` launches cleanly; `/`, `S`, `C`, `?`,
  `Esc`, `Q` all work end-to-end.

---

## What you must NOT do

- Do not edit anything in `notes/` (other than appending the new
  session-9-preflight and session-9-debrief files). Existing debriefs are
  historical record.
- Do not edit anything in `specs/` other than the full rewrite of
  `ARCHITECTURE.md` and adding this `session-9-spec.md`. Prior session specs
  are historical record.
- Do not "tidy up" surviving code that isn't related to the deletion. Resist
  the urge to refactor `cockpit/format.py` or rename anything in
  `analysis/market_analysis.py`. Out of scope.
- Do not add tests beyond `verify_session9.py`. There is no test framework
  in this repo; introducing one is a separate decision.
- Do not commit. Eric reviews the diff and commits manually.

---

## Final checklist before declaring complete

- [ ] Phases 1–5 all passed their acceptance criteria.
- [ ] `git status` shows only intended changes: deletions, the new widget +
  workflow + verifier, edits to docs and config files.
- [ ] `python3.14 -m scripts.verify_session9` exits 0.
- [ ] `python3.14 -m scripts.cockpit` launches; you can reach every
  surviving screen and return to home from each.
- [ ] `notes/session-9-debrief.md` is complete.

Report back with: the `git diff --stat`, the verifier output, the debrief
filename, and any deviations from this spec.
