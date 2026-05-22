# Session 7 Spec — Correlation Panel Real Data + Deep-Dive Screen

**Target executor:** Claude Sonnet 4.6 in Claude Code
**Estimated scope:** ~5–7 files new, ~6 files modified
**Pattern:** workflow → reactive → worker → renderer (5th application of this template; same shape as Sessions 3, 4, 5, 6)

---

## Mandatory read list

Before writing any code, read these in order:

1. `specs/ARCHITECTURE.md` — full document, focus on "The layers / Workflows" and "Anti-patterns to avoid"
2. `specs/ROADMAP.md` — Session 7 row in the session plan, plus "Status snapshot"
3. `notes/session-5-debrief.md` — sector heatmap pattern + gradient color machinery
4. `notes/session-6-debrief.md` — deep-dive screen pattern + `SectorTable` rendering approach
5. `workflows/market_pulse_snapshot.py` and `cockpit/widgets/market_pulse_panel.py` — the canonical small-panel template
6. `workflows/sector_snapshot.py` and `cockpit/widgets/sector_panel.py` — the gradient-color panel template
7. `workflows/multi_timeframe_sector_snapshot.py` and `cockpit/widgets/sector_table.py` — the deep-dive table template
8. `analysis/market_analysis.py` — already contains `load_aligned_returns`, `calculate_correlation_matrix`, `summarize_correlations`; you will compose these, not rewrite them
9. `scripts/correlations.py` — existing CLI; understand how `analysis/market_analysis.py` is currently called

Do not skip any of these. The pattern is established; this session is a faithful application of it.

---

## Goal

Replace the last mock panel on the home screen with real correlation data, and add a full-screen correlation deep-dive on `c`. After this session, **`_refresh_mock_panels` is deleted entirely** from `cockpit/screens/home.py`.

The home panel shows a small correlation matrix (gradient-shaded cells). The deep-dive shows a larger matrix plus a ranked pair list, with keyboard controls for method, lookback, and ticker preset.

**No Dash subprocess work in this session.** Deferred until the TUI is complete, Schwab is wired, and real-world use reveals where mouseover would help.

---

## Architectural fit

- **Workflow returns data, not pixels.** `CorrelationSnapshot` carries a `pd.DataFrame` (the matrix) and a `list[RankedPair]`. The renderer decides how to draw it.
- **UI goes through the workflow.** Home panel and deep-dive both consume the same snapshot type. Neither calls `DataService` or `analysis/` directly.
- **Stateless analysis is reused.** `load_aligned_returns`, `calculate_correlation_matrix`, `summarize_correlations` already exist. The workflow composes them; do not reimplement.
- **Gradient color machinery is reused.** Add `correlation_to_color()` to `cockpit/format.py` as a thin semantic wrapper around `relative_strength_to_color()` (or its underlying linear-RGB interpolator). Same math, different intent at the call site.
- **No new domain models.** `Stock` already suffices.

---

## File layout — new files

### `workflows/correlation_snapshot.py`

```python
"""Correlation snapshot workflow.

Composes load_aligned_returns + calculate_correlation_matrix + summarize_correlations
into a typed snapshot consumed by both the home correlation panel and the
correlation deep-dive screen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

import pandas as pd

from analysis.market_analysis import (
    calculate_correlation_matrix,
    load_aligned_returns,
    summarize_correlations,
)
from marketdata.service import DataService, get_data_service

_VALID_METHODS = ("pearson", "spearman", "kendall")
_MAX_LOOKBACK_DAYS = 3 * 365  # calendar-day safety cap


@dataclass(frozen=True)
class RankedPair:
    """One entry in the ranked-pair list."""
    ticker_a: str
    ticker_b: str
    correlation: float


@dataclass(frozen=True)
class CorrelationSnapshot:
    """Typed result of build_correlation_snapshot.

    The matrix carries tickers as both row and column index. Tickers that
    failed to load are absent from the matrix and recorded in failed_tickers.
    """
    tickers: tuple[str, ...]             # tickers actually used (post-failure pruning)
    requested_tickers: tuple[str, ...]   # what the caller asked for
    failed_tickers: tuple[str, ...]      # tickers dropped due to fetch/align errors
    method: str                           # "pearson" | "spearman" | "kendall"
    lookback_days: int                    # trading-day lookback used
    matrix: Optional[pd.DataFrame]        # square matrix indexed by tickers; None on catastrophic failure
    ranked_pairs: tuple[RankedPair, ...]  # sorted high → low
    as_of: datetime                       # snapshot wall-clock time
    error: Optional[str] = None           # panel-level catastrophic error message


def build_correlation_snapshot(
    tickers: list[str],
    lookback_days: int,
    method: str = "pearson",
    data_service: DataService | None = None,
    now: datetime | None = None,
) -> CorrelationSnapshot:
    """Build a correlation snapshot for the given tickers and lookback.

    Behavior:
      - Fetches each ticker via DataService.get_historical_ohlcv over a
        calendar window sized to comfortably yield lookback_days trading days.
      - Aligns returns via load_aligned_returns (forward-fill, inner-join).
      - Per-ticker failure tolerance: a ticker that fails to load is dropped
        and recorded in failed_tickers.
      - Catastrophic failure (< 2 surviving tickers, or alignment yields empty
        DataFrame) sets snapshot.error and returns matrix=None.
    """
    # ... implementation per the contract above
```

Implementation notes for Sonnet:
- Validate `method` against `_VALID_METHODS`; raise `ValueError` if invalid (caller's bug).
- Validate `lookback_days >= 2`; raise `ValueError` if below minimum.
- Compute calendar fetch start: roughly `lookback_days * 1.5` calendar days back (covers weekends/holidays), capped at `_MAX_LOOKBACK_DAYS`.
- For each requested ticker, try to fetch. On any exception, log a warning, add to `failed_tickers`, continue.
- After fetching surviving tickers, call `load_aligned_returns` on them. If the returns DataFrame is empty or has < 2 columns, set `error="insufficient data after alignment"` and return matrix=None.
- Truncate the aligned returns to the last `lookback_days` rows before computing the correlation matrix (this is the "lookback" semantic — most recent N trading days, not a calendar window).
- Compute matrix via `calculate_correlation_matrix(returns, method=method)`.
- Compute ranked pairs via `summarize_correlations(matrix)` — note this already returns sorted high → low. Wrap each row as a `RankedPair`.
- `as_of` defaults to `datetime.now()` if `now` is None.

### `cockpit/widgets/correlation_panel.py`

```python
"""Home-screen correlation panel.

Small matrix display, gradient-colored cells, ticker labels on both axes.
Renders the lower triangle plus diagonal (upper triangle is symmetric).
"""

from textual.widget import Widget
from textual.widgets import Static

from workflows.correlation_snapshot import CorrelationSnapshot
from cockpit.format import correlation_to_color, fmt_ticker
from cockpit.themes import THEMES


class CorrelationPanel(Widget):
    """Renders a CorrelationSnapshot as a small gradient-shaded matrix.

    Pure renderer: receives snapshot updates via update_snapshot() and rebuilds
    the static markup. Does not fetch data and does not own a timer.
    """

    def __init__(self, theme_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._theme_name = theme_name
        self._snapshot: CorrelationSnapshot | None = None

    def compose(self):
        yield Static(id="corr-grid")

    def update_snapshot(self, snapshot: CorrelationSnapshot) -> None:
        self._snapshot = snapshot
        self._rebuild()

    def update_theme(self, theme_name: str) -> None:
        self._theme_name = theme_name
        if self._snapshot is not None:
            self._rebuild()

    def _rebuild(self) -> None:
        # build Rich markup, gradient cell backgrounds via correlation_to_color
        # render lower-triangle + diagonal only
        # display matrix with ticker row/column labels
        ...
```

Implementation notes:
- Cells display the correlation value to 2 decimals (e.g. `0.67`, `-0.21`, `1.00`).
- Cell background = `correlation_to_color(rho, theme)`.
- Diagonal cells are always 1.00 — render with the strongest positive shade.
- If `snapshot.error is not None`, render an em-dash with the error message dimmed below.
- Failed tickers (in `snapshot.failed_tickers`) are not displayed in the panel — they're already absent from the matrix.

### `cockpit/screens/correlations.py`

```python
"""Correlation deep-dive screen.

Press 'c' on home to enter. Keyboard-controlled adjustment of method,
lookback, and ticker preset. Esc returns to home.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Static
from textual.worker import Worker, work

from workflows.correlation_snapshot import CorrelationSnapshot, build_correlation_snapshot


class CorrelationDeepDiveScreen(Screen):
    """Full-screen correlation matrix + ranked pair list."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=True),
        Binding("m", "cycle_method", "Method", show=True),
        Binding("[", "shrink_lookback", "Lookback −", show=True),
        Binding("]", "grow_lookback", "Lookback +", show=True),
        Binding("p", "cycle_preset", "Preset", show=True),
        Binding("r", "refresh_now", "Refresh", show=True),
    ]

    snapshot: reactive[CorrelationSnapshot | None] = reactive(None, layout=True)

    def __init__(self) -> None:
        super().__init__()
        cfg = self.app.settings.correlation_deep_dive_config
        self._method_index = _VALID_METHODS.index(cfg.default_method)
        self._lookback_steps = cfg.lookback_options  # tuple of ints, e.g. (10, 20, 60, 120, 252)
        self._lookback_index = self._lookback_steps.index(cfg.default_lookback_days)
        self._preset_names = tuple(cfg.presets.keys())
        self._preset_index = self._preset_names.index(cfg.default_preset)
        self._worker: Worker | None = None

    # composition: matrix on left, ranked-pair list on right
    # worker: @work(thread=True) calls build_correlation_snapshot and uses
    #         call_from_thread to assign self.snapshot
    # actions: cycle indices, kick worker
    # watch_snapshot: rebuild both child widgets
    ...
```

### `cockpit/widgets/correlation_table.py`

Larger matrix renderer for the deep-dive (full N×N, not just lower triangle). Same pattern as `SectorTable` from Session 6: build a Rich markup string in a single `Static`. Cell coloring via `correlation_to_color()`. Column-header row + row-label column. Diagonal cells highlighted.

### `cockpit/widgets/ranked_pair_list.py`

Right-side panel on the deep-dive: ordered list of pairs, highest correlation at top. Format:

```
TICKER_A — TICKER_B   +0.87
TICKER_A — TICKER_C   +0.71
...
TICKER_X — TICKER_Y   -0.42
```

Color the correlation value with `correlation_to_color()` text-color (not background) so the list reads cleanly.

---

## File layout — modified files

### `cockpit/format.py`

Add:

```python
def correlation_to_color(rho: float, theme: dict, intensity_max: float = 1.0) -> str:
    """Map a correlation value in [-1, +1] to a hex color from the theme gradient.

    Semantic wrapper: correlation magnitude maps to gradient intensity, sign
    maps to positive/negative gradient endpoint. Math is identical to
    relative_strength_to_color but the intent is different at the call site
    (statistical relationship vs. price relative-strength).
    """
    # delegate to the same linear-RGB interpolator already used by
    # relative_strength_to_color; clamp rho to [-intensity_max, intensity_max]
    ...
```

Do not duplicate the interpolation logic. If `relative_strength_to_color` has the interpolator inline, refactor it out into a private `_interpolate_gradient(value_in_range, theme)` helper that both functions call. This is a small refactor; preserve existing behavior exactly.

### `analysis/market_analysis.py`

No changes expected. Verify that:
- `load_aligned_returns` accepts a list of tickers and a date range and returns a DataFrame of returns indexed by date with one column per ticker.
- `calculate_correlation_matrix` accepts the returns DataFrame and a `method` kwarg.
- `summarize_correlations` returns pairs sorted high → low.

If any of these have signatures different from what `build_correlation_snapshot` needs, adapt the workflow — don't change the analysis functions.

### `config/settings.py`

Add two dataclasses and parsing:

```python
@dataclass(frozen=True)
class CorrelationConfig:
    """Home-screen correlation panel config."""
    tickers: tuple[str, ...]
    lookback_days: int
    method: str
    refresh_interval_seconds: int


@dataclass(frozen=True)
class CorrelationDeepDiveConfig:
    """Correlation deep-dive screen config."""
    presets: dict[str, tuple[str, ...]]   # name → ticker tuple
    default_preset: str
    default_method: str
    default_lookback_days: int
    lookback_options: tuple[int, ...]
    refresh_interval_seconds: int
```

Add `correlation_config: CorrelationConfig` and `correlation_deep_dive_config: CorrelationDeepDiveConfig` fields to `Settings`. Add `_parse_correlations()` and `_parse_correlation_deep_dive()` methods. Validate:
- `method` ∈ {pearson, spearman, kendall}; raise on invalid
- `lookback_days >= 2`; raise on invalid
- `default_preset` ∈ `presets`; raise on invalid
- `default_lookback_days` ∈ `lookback_options`; raise on invalid

### `cockpit.toml`

Add:

```toml
[correlations]
# Home-screen correlation panel. Small, stable, gradient-shaded matrix.
# Keep this list short (5–7 tickers) so the panel fits on home at 120×30.
tickers = ["SPY", "QQQ", "IWM", "TLT", "GLD", "VIX"]
lookback_days = 60
method = "pearson"
refresh_interval_seconds = 300   # 5 minutes; correlations move slowly

[correlation_deep_dive]
default_preset = "cross_asset"
default_method = "pearson"
default_lookback_days = 60
lookback_options = [10, 20, 60, 120, 252]
refresh_interval_seconds = 60

[correlation_deep_dive.presets]
cross_asset = ["SPY", "QQQ", "IWM", "TLT", "GLD", "VIX", "DXY", "CL=F"]
sectors = ["XLK", "XLF", "XLV", "XLY", "XLC", "XLI", "XLP", "XLE", "XLU", "XLRE", "XLB"]
mega_cap = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]
```

Note: VIX needs `^VIX`, DXY needs `DX-Y.NYB` for yfinance. Use those forms in the actual config values — the example above shows the user-facing names for clarity, but the working TOML must use the symbols yfinance understands. Cross-reference how `cockpit.toml`'s `[pulse]` section already handles these.

### `cockpit/screens/home.py`

1. Import `CorrelationPanel` and `CorrelationDeepDiveScreen`.
2. Replace the mock correlation panel with `CorrelationPanel`.
3. Add a `correlation_snapshot: reactive[...]` field and a `watch_correlation_snapshot` method.
4. Add `@work(thread=True) refresh_correlations` and a `set_interval` timer at `correlation_config.refresh_interval_seconds`.
5. Add binding: `Binding("c", "open_correlation_deep_dive", "Correlations", show=True)`.
6. Add `action_open_correlation_deep_dive(self)` that pushes the screen.
7. **Delete `_refresh_mock_panels` entirely.** Remove all calls to it. Verify nothing else references it.
8. Add to the global `r` (refresh) action: trigger the correlations worker alongside the existing workers.

### `cockpit/screens/help.py`

Add HOME SCREEN section if not already present (Session 6 may have added it):
- `c` — Correlations deep-dive

Add CORRELATION DEEP-DIVE SCREEN section:
- `Esc` — Back to home
- `m` — Cycle correlation method (Pearson → Spearman → Kendall)
- `[` / `]` — Decrease / increase lookback window
- `p` — Cycle ticker preset
- `r` — Refresh now

### `cockpit/styles.tcss`

Add CSS blocks for:
- `CorrelationPanel` — same border/padding pattern as `SectorPanel`
- `CorrelationDeepDiveScreen` — full-screen layout, two columns (matrix left ~70%, ranked list right ~30%)
- `CorrelationTable` — same approach as `SectorTable`
- `RankedPairList` — vertical list, right-aligned correlation values

Mirror the visual conventions of Session 5/6 widgets. Do not introduce new color tokens — use the existing theme variables.

---

## Acceptance criteria

### Automated (verifiable via a `scripts/verify_session7.py`-style script, follow Session 6 pattern)

1. `workflows/correlation_snapshot.py` exists and exports `CorrelationSnapshot`, `RankedPair`, `build_correlation_snapshot`.
2. `CorrelationSnapshot` is a frozen dataclass with all fields specified above.
3. `RankedPair` is a frozen dataclass with `ticker_a`, `ticker_b`, `correlation`.
4. `build_correlation_snapshot(["SPY","QQQ","IWM"], 30)` returns a snapshot with `matrix` being a 3×3 `pd.DataFrame`, diagonal = 1.0, symmetric.
5. `build_correlation_snapshot(["SPY","QQQ","IWM"], 30, method="spearman")` produces a different matrix than `method="pearson"` for the same inputs (sanity check that `method` is propagated).
6. `build_correlation_snapshot(["SPY","NOT_A_REAL_TICKER_XYZ","QQQ"], 30)` returns a 2×2 matrix (the bad ticker is dropped) and `failed_tickers == ("NOT_A_REAL_TICKER_XYZ",)`.
7. `build_correlation_snapshot(["NOT_A_TICKER_1","NOT_A_TICKER_2"], 30)` returns `matrix=None` and `error` is a non-empty string.
8. `build_correlation_snapshot(["SPY","QQQ"], 1)` raises `ValueError` (lookback below minimum).
9. `build_correlation_snapshot(["SPY","QQQ"], 30, method="kentucky")` raises `ValueError`.
10. `summarize_correlations` is imported and used — not reimplemented. (Grep test on source.)
11. `load_aligned_returns` and `calculate_correlation_matrix` are imported and used — not reimplemented.
12. Ranked pairs are sorted high → low: for any consecutive pair, `pairs[i].correlation >= pairs[i+1].correlation`.
13. `cockpit/format.py` exports `correlation_to_color(rho, theme, intensity_max=1.0)`.
14. `correlation_to_color(0.0, theme)` returns the theme's `gradient_neutral`.
15. `correlation_to_color(1.0, theme)` returns the theme's `gradient_positive`.
16. `correlation_to_color(-1.0, theme)` returns the theme's `gradient_negative`.
17. `relative_strength_to_color` still works after the refactor (Session 5 regression check).
18. `config/settings.py` exports `CorrelationConfig` and `CorrelationDeepDiveConfig`.
19. `Settings.load()` populates `correlation_config` and `correlation_deep_dive_config` from `cockpit.toml`.
20. `Settings.load()` with `method = "invalid"` in `[correlations]` raises a clear error.
21. `Settings.load()` with `default_preset = "missing"` in `[correlation_deep_dive]` raises a clear error.
22. `cockpit.toml` contains `[correlations]` and `[correlation_deep_dive]` sections with all required keys.
23. `cockpit/widgets/correlation_panel.py` defines `CorrelationPanel(Widget)`.
24. `cockpit/widgets/correlation_table.py` defines `CorrelationTable(Widget)` (or `Static` subclass, follow `SectorTable` precedent).
25. `cockpit/widgets/ranked_pair_list.py` defines `RankedPairList(Widget)`.
26. `cockpit/screens/correlations.py` defines `CorrelationDeepDiveScreen(Screen)` with BINDINGS for `m`, `[`, `]`, `p`, `r`, `escape`.
27. `cockpit/screens/home.py` no longer contains `_refresh_mock_panels` (grep test must return zero matches).
28. `cockpit/screens/home.py` contains `Binding("c", "open_correlation_deep_dive", ...)`.
29. `cockpit/screens/home.py` has a `correlation_snapshot` reactive and a `refresh_correlations` worker.
30. `cockpit/screens/help.py` mentions the `c` key and the deep-dive bindings (`m`, `[`, `]`, `p`).
31. All existing Session 3–6 acceptance criteria still pass (regression).

### Interactive (manual terminal verification, document in debrief)

32. Launching `python3.14 -m scripts.cockpit` shows a populated correlation panel on home (real values, gradient-colored).
33. Pressing `c` opens the deep-dive; pressing `Esc` returns to home.
34. On the deep-dive: pressing `m` cycles Pearson → Spearman → Kendall, refresh fires, matrix values change.
35. On the deep-dive: pressing `]` increases lookback; matrix values change. `[` decreases. Out-of-range presses are no-ops.
36. On the deep-dive: pressing `p` cycles ticker presets; matrix dimensions change accordingly.
37. The ranked pair list updates whenever the matrix updates and is sorted high → low.
38. Theme cycle (`t`) on the deep-dive: colors update on next refresh (same deferred behavior as sectors).
39. `_refresh_mock_panels` is gone — no panel falls back to mock data.

### Regression checks

40. Watchlist panel (Session 3) still polls and updates correctly.
41. Pulse panel (Session 4) still polls and updates correctly.
42. Sector panel (Session 5) still polls and updates correctly.
43. Sector deep-dive (Session 6) still works end-to-end (`s` → screen → Esc).
44. `python -m scripts.correlations -t AAPL MSFT NVDA --plot` still works (existing CLI must not be broken by any refactor).
45. `python -m scripts.get_data`, `python -m scripts.run_backtest`, `python visualization/view_backtest.py ...` all still work.

---

## What stays as-is (non-goals)

- **Dash subprocess for interactive heatmap.** Explicitly deferred. The roadmap will be updated to note this revisit happens after the TUI is complete and Schwab is wired.
- **`visualization/view_stock.py`, `view_backtest.py`, `plot_correlation.py`, `plot_static.py`.** Untouched. They remain CLI-standalone for now. Their integration story is post-cockpit-completion.
- **Per-screen theme override.** Infrastructure exists since Session 2; still not used.
- **Account panel.** Still placeholder; awaits Schwab session.
- **`_refresh_mock_panels` is deleted, not just emptied.** The method goes away entirely. Imports, references, and any harness that called it are removed too.

---

## What to do if stuck

- **If `load_aligned_returns` requires a different signature than expected:** adapt the workflow to match what's there. Do not change `analysis/market_analysis.py` — that would risk breaking `scripts/correlations.py`.
- **If `relative_strength_to_color` is hard to refactor cleanly:** implement `correlation_to_color` independently as a near-copy. Note the duplication in the debrief as tech debt. Do not block on the refactor.
- **If the deep-dive worker fires twice on screen entry (once from `on_mount`, once from the timer):** match the Session 6 sector deep-dive solution exactly. Look at `cockpit/screens/sectors.py`.
- **If `^VIX` or `DX-Y.NYB` symbols cause `load_aligned_returns` to fail differently than other tickers:** the workflow's per-ticker failure handling should already cover this. Confirm those special symbols appear in `failed_tickers` rather than crashing the whole snapshot.
- **If matrix gradient cells look unreadable in the terminal:** check that text foreground color is set to maintain contrast against the gradient background. Session 5's `SectorPanel` solved this — copy that approach.
- **If acceptance criterion 12 (monotonic ranked pairs) fails:** `summarize_correlations` from `analysis/market_analysis.py` may not actually sort. Check before wrapping. If it doesn't, sort in the workflow — do not modify `analysis/market_analysis.py`.

---

## Debrief expectations

Per the established pattern, produce `notes/session-7-debrief.md` covering:

- What was built (new files + modified files tables)
- Acceptance criteria results (X of Y automated pass; list interactive ACs awaiting manual verification)
- Technical findings and decisions (anything non-obvious encountered)
- Known limitations / deferred items
- Regression status (Sessions 3, 4, 5, 6 still working)
- What's next (Session 8 — ticker drill-down + polish)

Also note in the debrief: whether the `relative_strength_to_color` refactor into a shared `_interpolate_gradient` helper was clean or whether `correlation_to_color` ended up as a near-copy. This is useful information for future color-related work.

---

## Roadmap update (post-session, for the next planning chat)

After Session 7, `ROADMAP.md` should be updated to note:

- Sessions 1–7 complete; home screen fully wired to real data
- `_refresh_mock_panels` removed
- **Dash/Plotly integration timing:** explicitly deferred until after Session 8 (drill-down + polish) and Session 9 (Schwab end-to-end). Decision point is "after a few weeks of real use." The existing `visualization/*.py` Dash/mplfinance scripts remain functional as CLI tools in the meantime — their fate (integrate as subprocesses, refactor into cockpit, or deprecate) is deferred to the post-Schwab usage period.
