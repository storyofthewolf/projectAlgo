# Session 5 Spec — Sector Heatmap Real-Data Wiring (5a)

**Goal:** Wire the sector heatmap panel on the home screen to real data. Compute relative strength of 11 SPDR sector ETFs versus SPY over a configurable lookback window. Render as a 3×4 grid of bordered cells with continuous-gradient backgrounds, sparklines showing the relative-strength path, and theme-aware color endpoints. Deep-dive screen is **out of scope** — deferred to Session 6.

This session is pattern-replay of Session 4 plus new color-gradient machinery. The polling pattern (workflow → reactive → worker → renderer) is unchanged. The new work is: a stateless relative-strength function in `analysis/`, a theme-aware color-interpolation function in `cockpit/format.py`, a new `[sectors]` TOML section, and a new panel widget that applies inline background colors.

---

## Mandatory read list

Before writing any code, Sonnet must read:

1. `specs/ARCHITECTURE.md` — design principles, especially "workflows orchestrate; UI renders" and "computation is stateless"
2. `notes/session-4-debrief.md` — the first-flash bug pattern, the optional-`data_service` parameter pattern, the panel-as-pure-renderer pattern
3. `workflows/market_pulse_snapshot.py` — the structural template for this session's workflow
4. `cockpit/widgets/market_pulse_panel.py` — the structural template for this session's panel
5. `cockpit/screens/home.py` — to understand the reactive + worker + watch_* pattern already in use for pulse and watchlist
6. `cockpit/themes.py` — to understand how theme colors are defined and accessed
7. `analysis/market_analysis.py` — `load_aligned_returns()` will be reused
8. `cockpit/format.py` — to understand existing formatting conventions and where to add the new gradient function
9. `config/settings.py` — to understand how the `[pulse]` section parses, which is the template for `[sectors]`
10. `cockpit.toml` — to see the existing `[pulse]` section that the new `[sectors]` section mirrors

---

## Target file layout

**New files:**

```
workflows/sector_snapshot.py              # build_sector_snapshot(), SectorSnapshot, SectorCell
cockpit/widgets/sector_panel.py           # SectorPanel + SectorCell widget
```

**Modified files:**

```
analysis/market_analysis.py               # add calculate_relative_strength()
cockpit.toml                              # add [sectors] section
config/settings.py                        # add SectorConfig, sector_config field, defaults
cockpit/format.py                         # add relative_strength_to_color(), fmt_rs_pct()
cockpit/themes.py                         # add gradient_positive, gradient_negative, gradient_neutral to both themes
cockpit/screens/home.py                   # replace mock sector Static with SectorPanel; add reactive + worker
cockpit/styles.tcss                       # add SectorPanel and SectorCell styling
```

**Unmodified (despite being touched conceptually):**

```
cockpit/mock_data.py                      # mock sector function may remain for now if it exists,
                                          # but must no longer be called from anywhere
```

---

## Interface signatures

### `workflows/sector_snapshot.py`

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class SectorCell:
    """One cell in the sector heatmap."""
    symbol: str                           # e.g., "XLK"
    label: str                            # e.g., "Tech"
    relative_strength: Optional[float]    # signed decimal, e.g., 0.023 for +2.3%; None on error
    sparkline_values: list[float]         # length == lookback_days; relative-strength path
    error: Optional[str] = None           # error message if this cell failed; None on success

@dataclass
class SectorSnapshot:
    """Complete sector heatmap snapshot."""
    cells: list[SectorCell]               # always 12 entries: SPY + 11 sectors, in display order
    benchmark_symbol: str                 # "SPY"
    lookback_days: int                    # echoed from config for renderer use
    intensity_max_pct: float              # echoed from config for renderer use
    fetched_at: datetime
    error: Optional[str] = None           # panel-level error (e.g., SPY itself failed)


# Module-level constant — the 11 SPDR sector ETFs in SPY-weight order
SPDR_SECTORS: list[tuple[str, str]] = [
    ("XLK",  "Tech"),
    ("XLF",  "Financials"),
    ("XLV",  "Health"),
    ("XLY",  "Cons Disc"),
    ("XLC",  "Comm Svcs"),
    ("XLI",  "Industrial"),
    ("XLP",  "Cons Stap"),
    ("XLE",  "Energy"),
    ("XLU",  "Utilities"),
    ("XLRE", "RealEstate"),
    ("XLB",  "Materials"),
]

def build_sector_snapshot(
    sector_config,                        # config.settings.SectorConfig
    data_service=None,                    # optional DataService; defaults to get_data_service()
    now: Optional[datetime] = None,       # optional override for testing
) -> SectorSnapshot:
    """
    Build a sector heatmap snapshot.

    Fetches OHLCV history for SPY + 11 sector ETFs over `lookback_days * 2` calendar days
    (to ensure enough trading days), computes relative strength using
    `analysis.market_analysis.calculate_relative_strength`, and packages cells in display order.

    Failure modes:
      - SPY fetch fails → SectorSnapshot(cells=[], error="Benchmark SPY unavailable")
      - One sector fails → that cell has relative_strength=None, sparkline_values=[], error set;
        other cells render normally
      - All sectors fail but SPY succeeds → SectorSnapshot with all cells in error state
        (no panel-level error)
    """
```

### `analysis/market_analysis.py` — new function

```python
import pandas as pd

def calculate_relative_strength(
    sector_returns: pd.Series,
    benchmark_returns: pd.Series,
    lookback_days: int,
) -> tuple[float, list[float]]:
    """
    Compute cumulative relative strength of a sector vs a benchmark over the last N trading days.

    Returns:
        (relative_strength, rs_path)
        - relative_strength: cumulative sector return minus cumulative benchmark return,
          as a signed decimal (e.g., 0.023 for +2.3%)
        - rs_path: list of length `lookback_days` showing the relative-strength value
          at each day in the window (cumulative-to-date diff). Used for sparklines.

    Both inputs are pandas Series of daily simple returns (not log returns), indexed by date,
    already aligned (same index). Caller is responsible for alignment — use
    `load_aligned_returns()` for that.

    If either series has fewer than `lookback_days` observations, raises ValueError.
    """
```

Implementation note: cumulative return over N days = `(1 + r).prod() - 1`. The RS path is the cumulative diff at each step: `(1 + sector_returns.iloc[-N:]).cumprod() - (1 + benchmark_returns.iloc[-N:]).cumprod()`. Return both the final scalar and the list of intermediate values (call `.tolist()` on the Series).

### `config/settings.py` — additions

```python
@dataclass(frozen=True)
class SectorConfig:
    lookback_days: int = 20
    comparison_ticker: str = "SPY"
    intensity_max_pct: float = 5.0           # ±5% clamps to max color intensity
    refresh_interval_seconds: int = 300      # 5 minutes
```

Add `sector_config: SectorConfig` field to the `Settings` dataclass with appropriate default. In `Settings.load()`, parse a `[sectors]` table from `cockpit.toml`. If the section is missing, use `SectorConfig()` (all defaults).

### `cockpit/format.py` — new functions

```python
def relative_strength_to_color(
    rs_value: Optional[float],
    intensity_max_pct: float,
    gradient_positive: str,                 # hex color, e.g., "#c87a1a"
    gradient_negative: str,                 # hex color, e.g., "#8b1a1a"
    gradient_neutral: str,                  # hex color, e.g., "#1a1a1a"
) -> str:
    """
    Map a relative-strength value to a hex color via linear interpolation.

    - rs_value is a signed decimal (e.g., 0.023 for +2.3%).
    - intensity_max_pct is in percent units (5.0 = clamp at ±5%).
    - Values above +intensity_max_pct/100 clamp to gradient_positive.
    - Values below -intensity_max_pct/100 clamp to gradient_negative.
    - Zero returns gradient_neutral.
    - None returns gradient_neutral (used for error cells).
    - Interpolation is linear in RGB space.

    Returns a hex string like "#a35c1f" suitable for `widget.styles.background`.
    """

def fmt_rs_pct(value: Optional[float]) -> str:
    """
    Format a relative-strength value as a signed percentage with 2 decimals.

    Examples: 0.023 → "+2.30%", -0.0156 → "-1.56%", None → "—", 0.0 → "+0.00%".
    Note: this is distinct from fmt_pct in that the input is a decimal, not a percent.
    Internally just calls fmt_pct(value * 100) — exists as a named alias for readability
    at call sites.
    """
```

### `cockpit/themes.py` — additions

Each theme dict in `THEMES_CONFIG` gets three new keys:

```python
"gradient_positive": "#c87a1a",   # claude-warm: deep amber
"gradient_negative": "#8b1a1a",   # claude-warm: deep red
"gradient_neutral":  "#1a1a1a",   # claude-warm: near-black

# blue-orange theme:
"gradient_positive": "#1a5a8b",   # deep blue
"gradient_negative": "#c87a1a",   # deep orange
"gradient_neutral":  "#1a1a1a",   # near-black
```

Update `CockpitApp.get_css_variables()` to inject these as `$gradient-positive`, `$gradient-negative`, `$gradient-neutral` so the panel widget can read them at runtime via the app's theme lookup. (Reading colors from the active theme dict directly in Python is also acceptable — whichever pattern is cleanest given the existing code structure.)

### `cockpit/widgets/sector_panel.py`

```python
from textual.widget import Widget
from textual.containers import Horizontal, Vertical
from cockpit.widgets.panel_frame import PanelFrame
from cockpit.widgets.sparkline import Sparkline

class SectorCell(Widget):
    """Single sector cell with gradient background, label, RS value, and sparkline."""

    DEFAULT_CSS = """..."""               # see styling section below

    def __init__(self, symbol: str, label: str, **kwargs):
        super().__init__(**kwargs)
        self.symbol = symbol
        self.label = label
        # internal state
        self._rs_value: Optional[float] = None
        self._sparkline_values: list[float] = []
        self._is_error: bool = False

    def compose(self) -> ComposeResult:
        # Two-line content: top line = symbol + label, second line = RS% + sparkline
        ...

    def update_cell(
        self,
        rs_value: Optional[float],
        sparkline_values: list[float],
        intensity_max_pct: float,
        is_error: bool,
        theme_colors: dict,                # {gradient_positive, gradient_negative, gradient_neutral}
    ) -> None:
        """Update displayed values and apply gradient background."""
        ...


class SectorPanel(Widget):
    """3×4 grid of sector cells, wrapped in a PanelFrame."""

    DEFAULT_CSS = """..."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cells: dict[str, SectorCell] = {}  # symbol -> cell

    def compose(self) -> ComposeResult:
        # PanelFrame(title="SECTORS") wrapping a Vertical with 4 Horizontal rows of 3 cells each
        ...

    def update_snapshot(self, snapshot: SectorSnapshot) -> None:
        """
        Update all cells from the snapshot.
        If snapshot.error is set, display centered error message in place of grid.
        Otherwise call update_cell() on each child cell.
        """
        ...
```

---

## Concrete before/after patterns

### Pattern A: HomeScreen — reactive + worker

**Before (current state, mock data):**

```python
# In HomeScreen.compose(), in the sectors panel area:
yield Static(make_sector_display(MOCK_SECTORS), id="sectors-content")

# In HomeScreen._refresh_mock_panels():
def _refresh_mock_panels(self) -> None:
    regenerate_mock()
    self.query_one("#sectors-content", Static).update(
        make_sector_display(MOCK_SECTORS)
    )
    # ... correlation panel regeneration also here
```

**After:**

```python
# In HomeScreen.compose(), in the sectors panel area:
yield SectorPanel(id="sectors-panel")

# Add reactive declaration at class level:
sector_snapshot: reactive[Optional[SectorSnapshot]] = reactive(None)

# In on_mount(), add:
self.set_interval(
    self.app.settings.sector_config.refresh_interval_seconds,
    self.refresh_sectors,
)
self.refresh_sectors()  # immediate first load

# New worker method:
@work(exclusive=True, group="sectors")
async def refresh_sectors(self) -> None:
    snapshot = await asyncio.to_thread(
        build_sector_snapshot,
        self.app.settings.sector_config,
    )
    self.sector_snapshot = snapshot

# New watcher:
def watch_sector_snapshot(self, snapshot: Optional[SectorSnapshot]) -> None:
    if snapshot is None:
        return
    self.query_one("#sectors-panel", SectorPanel).update_snapshot(snapshot)

# In action_refresh():
def action_refresh(self) -> None:
    self.refresh_watchlist()
    self.refresh_pulse()
    self.refresh_sectors()       # NEW
    self._refresh_mock_panels()  # now only handles correlations

# In _refresh_mock_panels(): REMOVE all sector-related lines, keep correlation regeneration.
```

### Pattern B: Workflow — using `load_aligned_returns`

```python
from analysis.market_analysis import load_aligned_returns, calculate_relative_strength

def build_sector_snapshot(sector_config, data_service=None, now=None):
    service = data_service if data_service is not None else get_data_service()
    now = now or datetime.now()

    benchmark = sector_config.comparison_ticker
    sector_symbols = [s for s, _ in SPDR_SECTORS]
    all_tickers = [benchmark] + sector_symbols

    # Fetch enough history: lookback_days trading days back, with buffer for weekends/holidays
    end_date = now.date()
    start_date = end_date - timedelta(days=sector_config.lookback_days * 2 + 10)

    try:
        returns_df = load_aligned_returns(
            all_tickers,
            start=start_date,
            end=end_date,
            interval="1d",
            data_service=service,
        )
    except Exception as e:
        return SectorSnapshot(
            cells=[],
            benchmark_symbol=benchmark,
            lookback_days=sector_config.lookback_days,
            intensity_max_pct=sector_config.intensity_max_pct,
            fetched_at=now,
            error=f"Failed to load aligned returns: {e}",
        )

    if benchmark not in returns_df.columns:
        return SectorSnapshot(
            cells=[], benchmark_symbol=benchmark,
            lookback_days=sector_config.lookback_days,
            intensity_max_pct=sector_config.intensity_max_pct,
            fetched_at=now,
            error=f"Benchmark {benchmark} unavailable",
        )

    benchmark_returns = returns_df[benchmark]

    # Build cells in display order: SPY first, then 11 sectors in SPY-weight order
    cells = []

    # SPY reference cell — RS is always 0 by definition
    cells.append(SectorCell(
        symbol=benchmark,
        label="S&P 500",
        relative_strength=0.0,
        sparkline_values=[0.0] * sector_config.lookback_days,
    ))

    for symbol, label in SPDR_SECTORS:
        if symbol not in returns_df.columns:
            cells.append(SectorCell(
                symbol=symbol, label=label,
                relative_strength=None,
                sparkline_values=[],
                error=f"{symbol} unavailable",
            ))
            continue
        try:
            rs_value, rs_path = calculate_relative_strength(
                returns_df[symbol],
                benchmark_returns,
                sector_config.lookback_days,
            )
            cells.append(SectorCell(
                symbol=symbol, label=label,
                relative_strength=rs_value,
                sparkline_values=rs_path,
            ))
        except Exception as e:
            cells.append(SectorCell(
                symbol=symbol, label=label,
                relative_strength=None,
                sparkline_values=[],
                error=str(e),
            ))

    return SectorSnapshot(
        cells=cells,
        benchmark_symbol=benchmark,
        lookback_days=sector_config.lookback_days,
        intensity_max_pct=sector_config.intensity_max_pct,
        fetched_at=now,
    )
```

### Pattern C: SectorCell.update_cell with inline background

```python
def update_cell(self, rs_value, sparkline_values, intensity_max_pct, is_error, theme_colors):
    self._rs_value = rs_value
    self._sparkline_values = sparkline_values
    self._is_error = is_error

    # Compute and apply background color
    bg_hex = relative_strength_to_color(
        rs_value,
        intensity_max_pct,
        theme_colors["gradient_positive"],
        theme_colors["gradient_negative"],
        theme_colors["gradient_neutral"],
    )
    self.styles.background = bg_hex

    # Update displayed text — RS line
    rs_text = self.query_one(".sc-rs", Static)
    rs_text.update(fmt_rs_pct(rs_value))

    # Update sparkline
    sparkline = self.query_one(Sparkline)
    sparkline.update_values(sparkline_values)

    # Error state: dim text, em-dashes
    if is_error:
        rs_text.update("—")
        sparkline.update_values([])
```

### Pattern D: `[sectors]` TOML section

```toml
[sectors]
lookback_days = 20
comparison_ticker = "SPY"
intensity_max_pct = 5.0
refresh_interval_seconds = 300
```

### Pattern E: Layout — `#mid-row` and SectorPanel CSS

```css
/* Existing #mid-row likely has a height set. SectorPanel goes inside it. */
SectorPanel {
    width: 1fr;
    height: 1fr;
}

SectorPanel .sp-grid {
    layout: vertical;
    height: 1fr;
}

SectorPanel .sp-row {
    layout: horizontal;
    height: 1fr;
}

SectorCell {
    width: 1fr;
    height: 1fr;
    border: round $border;
    /* background is set imperatively per-cell */
}

SectorCell .sc-header {
    height: 1;
    /* symbol + label */
}

SectorCell .sc-rs {
    /* RS percentage, second line */
}

SectorCell Sparkline {
    /* sparkline aligned right of RS value */
}
```

Cell text color should be `#f0e0c0` (theme-warm cream) or equivalent light color from the theme, applied via CSS class. The gradient backgrounds are all dark-side colors (deep red through neutral to deep amber/blue), so light cream text remains readable across the entire gradient range.

---

## Acceptance criteria

All criteria are verifiable. Interactive/visual criteria are flagged as such.

1. **`build_sector_snapshot()` returns 12 cells.** Calling with default config returns a `SectorSnapshot` whose `cells` list has exactly 12 entries: SPY first, then XLK, XLF, XLV, XLY, XLC, XLI, XLP, XLE, XLU, XLRE, XLB in that order.

2. **SPY cell is always RS=0.** `snapshot.cells[0].symbol == "SPY"` and `snapshot.cells[0].relative_strength == 0.0`.

3. **Sector cells contain computed relative strength.** For each non-SPY cell, `relative_strength` is a float in a reasonable range (typically -0.20 to +0.20 for a 20-day window) and `sparkline_values` is a list of length `lookback_days`.

4. **Bad sector ticker handled per-cell.** If a sector ETF returns empty data, that cell has `relative_strength=None`, `sparkline_values=[]`, `error` set; other cells remain unaffected. Verified by temporarily substituting a bad symbol (e.g., "XLZZZ") in `SPDR_SECTORS` and confirming only that cell errors.

5. **Benchmark failure produces panel-level error.** If SPY itself fails to load, `snapshot.error` is set (string), `cells` is empty, and the panel renders a centered error message instead of the grid. Verified by patching `comparison_ticker` to a bad ticker.

6. **`calculate_relative_strength` returns tuple of (float, list).** Returns `(rs_value: float, rs_path: list[float])` where `len(rs_path) == lookback_days`. The final value of `rs_path` equals `rs_value` to within floating-point tolerance.

7. **`calculate_relative_strength` raises on insufficient data.** Calling with returns series shorter than `lookback_days` raises `ValueError` with a clear message.

8. **No Textual/asyncio imports in workflow.** `workflows/sector_snapshot.py` imports nothing from `textual`, `asyncio`, or `cockpit`. Verified by AST inspection or grep.

9. **No yfinance/schwab in `workflows/` or `cockpit/`.** Same grep pattern as Session 4. Workflows only see `marketdata.service`; cockpit only sees workflows.

10. **`cockpit.toml` has `[sectors]` section with all four parameters.** Section is present in the committed `cockpit.toml`; all four keys (`lookback_days`, `comparison_ticker`, `intensity_max_pct`, `refresh_interval_seconds`) are set.

11. **`Settings.load()` parses sectors config.** After loading, `settings.sector_config` is a `SectorConfig` instance with values from the TOML.

12. **Missing `[sectors]` section falls back to defaults.** Loading a minimal `cockpit.toml` with no `[sectors]` section yields `settings.sector_config == SectorConfig()` with default values.

13. **HomeScreen renders SectorPanel with real data within ~10s of launch.** (Interactive verify.) Launching the cockpit shows the SECTORS panel populated with 12 cells. First load typically completes in 5-10 seconds depending on yfinance latency.

14. **Each cell shows symbol, label, RS%, and sparkline.** (Interactive verify.) Each non-error cell visually displays the four elements. SPY shows "+0.00%" and a flat sparkline.

15. **Cell backgrounds vary by relative strength.** (Interactive verify.) Cells with positive RS are visibly tinted toward `gradient_positive`; cells with negative RS toward `gradient_negative`; the SPY cell is `gradient_neutral`. The visual gradient is continuous, not stepped.

16. **`relative_strength_to_color` clamps correctly.** Unit-verifiable: passing `rs_value = 0.10` with `intensity_max_pct = 5.0` returns exactly `gradient_positive`. Passing `-0.10` returns exactly `gradient_negative`. Passing `0.025` returns a color halfway between neutral and positive.

17. **`relative_strength_to_color` handles None.** Passing `rs_value = None` returns `gradient_neutral` (not a crash).

18. **Auto-refresh every `refresh_interval_seconds`.** `HomeScreen.on_mount` calls `set_interval(self.app.settings.sector_config.refresh_interval_seconds, self.refresh_sectors)`. Verified by inspection.

19. **`r` triggers immediate sector refresh.** `action_refresh()` calls `self.refresh_sectors()` along with the existing pulse and watchlist refreshes.

20. **Sector polling independent of pulse and watchlist.** `refresh_sectors` is a separate `@work` method with its own `group="sectors"`; its `set_interval` timer is independent of the others.

21. **`_refresh_mock_panels` no longer regenerates sector mock data.** Any code path that called a sector mock function from `_refresh_mock_panels` is removed. Correlation mock regeneration **remains** (correlations are wired in Session 7).

22. **HomeScreen does not import DataService or marketdata.** `grep "from marketdata" cockpit/screens/home.py` returns nothing. `grep "DataService" cockpit/screens/home.py` returns nothing. The workflow handles all data layer access.

23. **SectorPanel does not import workflows or marketdata.** `grep -E "from workflows|from marketdata" cockpit/widgets/sector_panel.py` returns nothing. The panel only knows about `SectorSnapshot` as a type, imported for type hints if needed — but at runtime accepts any object with the expected attributes.

24. **`sector_panel.py` does not import `mock_data`.** `grep "mock_data" cockpit/widgets/sector_panel.py` returns nothing.

25. **Theme dicts have three new gradient keys.** Both `claude-warm` and `blue-orange` entries in `THEMES_CONFIG` have `gradient_positive`, `gradient_negative`, and `gradient_neutral` keys with valid hex strings.

26. **Theme cycling preserves correctness.** (Interactive verify.) Pressing `T` to cycle from claude-warm to blue-orange updates sector cell backgrounds to the new gradient on the next refresh (or immediately if the panel listens for theme changes). If immediate update is too complex, the next 5-minute refresh is acceptable for Session 5 — flag in debrief.

---

## What stays as-is (non-goals)

- **Sector deep-dive screen** — entirely deferred to Session 6. No `s`-key binding, no new screen file. The cells are not focusable and pressing them does nothing.
- **Correlation panel** — still mock data; still regenerated by `_refresh_mock_panels`. Wired in Session 7.
- **Account panel** — still placeholder.
- **Multi-timeframe relative strength** — only one lookback window (configurable, single value) for now. The deep-dive screen in Session 6 will show 1D/1W/1M/3M/YTD; the home panel intentionally shows only one.
- **Flash on update** — sector cells do **not** flash on refresh. The gradient *is* the visual; flashing on top of a colored background would be visually noisy. Cells just update their background and RS value silently on refresh. This is a deliberate departure from pulse/watchlist behavior.
- **Sorting by RS** — display order is fixed (SPY-weight). Sortable sectors are a deep-dive feature.
- **Live intraday data** — daily-bar data via `DataService` is sufficient. Sector relative strength at a 20-day lookback does not need intraday granularity.
- **Customizable sector list** — the 11 SPDR sectors are the industry standard and hardcoded in `SPDR_SECTORS`. Not a config knob.
- **Removal of `mock_data.py` sector functions** — if the mock sector data function exists, it can stay in the file (correlations may still use shared helpers). Just verify no live code path calls it.

---

## What to do if stuck

**If `load_aligned_returns` doesn't return SPY in the columns:** the function may inner-join on common trading days and drop SPY if there's a date misalignment. Check the function's behavior; if needed, fetch SPY separately via `data_service.get_historical_ohlcv` and align manually with `pd.concat` and `.dropna()`.

**If theme colors aren't accessible from the SectorPanel:** the cleanest pattern is to read them off `self.app.theme_config` (or whatever attribute holds the current theme dict) and pass them down to each `SectorCell` in `update_cell()`. Don't try to use CSS variables for the inline backgrounds — those are evaluated at parse time, not runtime.

**If the 3×4 grid layout fights you:** Session 4 explicitly chose `Horizontal`/`Vertical` over Textual's `Grid` because Grid was finicky. Do the same. Four `Horizontal` rows inside a `Vertical`, each containing three `SectorCell` children at `width: 1fr`.

**If sparklines look wrong:** the RS path values can be tiny (a 20-day RS path might range from -0.02 to +0.03). The existing `Sparkline` widget normalizes its input — verify it handles this small range without producing a flat line. If it does flatten, normalize the values before passing them in, or extend `Sparkline` to handle the small-range case.

**If the first refresh is slow (>10s):** that's expected on first run because `load_aligned_returns` is fetching 12 tickers serially. Caching means subsequent calls within the same day are fast. Don't try to parallelize unless first-load UX is unacceptable — note in the debrief if it is.

**If color interpolation looks ugly:** linear RGB interpolation can produce muddy midtones. If the visual is genuinely bad, consider HSL interpolation. But ship the linear version first and only switch if owner pushback occurs.

**If `set_interval` and `@work` interact strangely:** Session 4 already solved this. Pattern-match exactly: `set_interval(seconds, self.refresh_sectors)` calls the `@work` method, which Textual handles correctly because `@work` returns a worker rather than coroutine. Don't `await` it from `on_mount` or the interval callback.

---

## Verification script

Sonnet must produce a script `scripts/verify_session5.py` that programmatically tests ACs 1-12, 16, 17, 25. Interactive ACs (13, 14, 15, 26) must be verified manually and noted in the debrief with screenshots or descriptions.

The verification script must include:
- A test for the bad-sector case (substituting "XLZZZ" temporarily)
- A test for the bad-benchmark case (substituting "ZZSPY" temporarily)
- A test for the insufficient-data ValueError in `calculate_relative_strength`
- A test that `relative_strength_to_color` produces correct endpoints, midpoints, and None handling
- A test that `Settings.load()` correctly parses `[sectors]` and falls back when missing

---

## Debrief expectations

The Session 5 debrief should follow the same format as Session 4. In addition to the AC checklist, the debrief must address:

- Whether linear RGB interpolation produced acceptable visuals or if HSL was needed
- First-load latency (12 tickers via yfinance) — actual measured seconds
- Whether the no-flash decision feels right or if a subtle indicator of "data refreshed" is needed
- Whether the theme cycle updates colors immediately or requires next refresh
- Any layout issues at the 120×30 minimum terminal size — sector cells will be small at that width
