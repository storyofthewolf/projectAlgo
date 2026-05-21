# Session 6 Spec — Sector Deep-Dive Screen

**Status:** Ready for Claude Code (Sonnet) execution
**Depends on:** Sessions 1-5 complete; `workflows/sector_snapshot.py`, `analysis/market_analysis.py::calculate_relative_strength`, `cockpit/format.py::relative_strength_to_color`, and `[sectors]` config already in place.

---

## Mandatory read list

Before writing any code, read these in order:

1. `specs/ROADMAP.md` — Session 6 goal and architectural position
2. `specs/ARCHITECTURE.md` — layered architecture, workflow pattern, anti-patterns
3. `notes/session-5-debrief.md` — what was built, what's known, open questions for Session 6
4. `workflows/sector_snapshot.py` — the workflow this session extends/complements
5. `analysis/market_analysis.py` — `calculate_relative_strength` and `load_aligned_returns`
6. `cockpit/format.py` — `relative_strength_to_color`, `fmt_rs_pct`, `make_sparkline`
7. `cockpit/screens/home.py` — current screen pattern, reactive + worker + watch_*
8. `cockpit/widgets/sector_panel.py` — Session 5's panel; reference for cell rendering
9. `config/settings.py` — `SectorConfig` dataclass pattern (you'll add a sibling)
10. `cockpit.toml` — config layout
11. `cockpit/styles.tcss` — existing CSS variable conventions
12. `cockpit/themes.py` — gradient color keys

If any file's contents differ materially from what this spec assumes, STOP and ask before proceeding.

---

## What this session builds

The first substantive non-home screen: a sector deep-dive accessed via `s` from home. It presents the 11 SPDR sector ETFs in a sortable table showing relative strength versus SPY at multiple user-configurable timeframes, plus a sparkline of the currently-sorted timeframe's RS path.

This is Session 6's load-bearing contribution to the architecture:

- **First screen transition with real data.** Push-screen / pop-screen with workers on both screens.
- **First multi-timeframe analysis.** Same kernel (`calculate_relative_strength`) called at multiple windows from one data fetch.
- **First user-configurable analytic dimension.** Timeframes are a `[sector_deep_dive]` config list, not hardcoded.
- **First sortable interactive table.** Sort state lives on the screen as a reactive; sparkline is driven by it.

---

## Scope summary (decisions already made)

These are locked in from the planning conversation. Do not re-derive.

| Decision | Choice |
|---|---|
| Sparkline column | Follows the currently-sorted timeframe |
| Sort key bindings | Arrow keys move column focus; Enter cycles asc/desc |
| Entry behavior | Always opens at default sort (no per-visit memory) |
| Auto-refresh cadence | 60s on deep-dive; home continues 5-min in background |
| SPY row | Pinned at top, RS=0 across all columns |
| Timeframes | User-configurable in `cockpit.toml`; defaults 5D / 1M / 3M / YTD |
| Default sort | `default_sort_column = "1M"`, `default_sort_direction = "desc"` |
| Data fetch | One fetch covers all timeframes (slice the returns DataFrame) |
| Cell background | Continuous-gradient via existing `relative_strength_to_color` |

**Out of scope (do not build):**

- Click-through to individual ticker detail (Session 8)
- "Open in Dash" for sector charts (Session 8+)
- Per-sector deep-dive (constituents, top movers within a sector)
- Correlation deep-dive (Session 7)
- Replacing or refactoring the home `SectorPanel` from Session 5
- Theme-change immediate re-render (the Session 5 deferred item — still deferred)

---

## File layout

### Files to create

```
workflows/multi_timeframe_sector_snapshot.py    NEW
cockpit/screens/sectors.py                      NEW
cockpit/widgets/sector_table.py                 NEW
scripts/verify_session6.py                      NEW (automated AC checker, follows Session 5 template)
```

### Files to modify

```
config/settings.py                              add Timeframe + SectorDeepDiveConfig + parsing
cockpit.toml                                    add [sector_deep_dive] section
cockpit/screens/home.py                         add 's' binding → push SectorDeepDiveScreen
cockpit/screens/help.py                         document the new bindings
cockpit/styles.tcss                             add screen + table CSS rules
```

### Files NOT to touch

```
workflows/sector_snapshot.py                    leave alone — home panel still uses it
cockpit/widgets/sector_panel.py                 leave alone — home panel still uses it
analysis/market_analysis.py                     calculate_relative_strength is reused as-is
cockpit/format.py                               relative_strength_to_color is reused as-is
cockpit/themes.py                               gradient keys already exist
```

If you find yourself needing to change `workflows/sector_snapshot.py` or `cockpit/widgets/sector_panel.py`, STOP — that means the design has drifted. Ask before proceeding.

---

## Configuration

### `cockpit.toml` — new section

Append this section. Comments are part of the deliverable.

```toml
[sector_deep_dive]
# Sector deep-dive screen (entered via 's' from home, exit via Esc).
# Refresh cadence is faster than the home sector panel because this screen
# is sized for the eventual addition of intraday breadth/indicator data;
# the current RS-only content will simply re-fetch identical daily bars.
refresh_interval_seconds = 60

# Sort column at screen entry. Must match one of the timeframe labels below.
default_sort_column = "1M"
# "asc" or "desc"
default_sort_direction = "desc"

# Timeframes shown as columns in the deep-dive table, left to right.
# Each entry needs `label` plus exactly ONE of: trading_days, calendar.
#
#   trading_days = N    fixed lookback of N trading days (NOT calendar days)
#   calendar     = "ytd" calendar-anchored: from Jan 1 of current year to today
#
# Allowed: 2 to 6 entries.
timeframes = [
    { label = "5D",  trading_days = 5 },
    { label = "1M",  trading_days = 21 },
    { label = "3M",  trading_days = 63 },
    { label = "YTD", calendar = "ytd" },
]
```

### `config/settings.py` — new types

Add two dataclasses and parse them in `Settings.load()`.

```python
@dataclass(frozen=True)
class Timeframe:
    label: str                  # display name e.g. "1M"
    trading_days: int | None    # fixed lookback, mutually exclusive with calendar
    calendar: str | None        # currently only "ytd" supported; otherwise None

@dataclass(frozen=True)
class SectorDeepDiveConfig:
    refresh_interval_seconds: int
    default_sort_column: str
    default_sort_direction: str  # "asc" or "desc"
    timeframes: tuple[Timeframe, ...]
```

Add `sector_deep_dive_config: SectorDeepDiveConfig` as a field on `Settings`.

**Defaults if `[sector_deep_dive]` is absent:**

- `refresh_interval_seconds = 60`
- `default_sort_column = "1M"`
- `default_sort_direction = "desc"`
- timeframes: 5D / 1M / 3M / YTD as in the TOML example above

**Validation at parse time. Raise `ValueError` with clear message for any of:**

1. `timeframes` is empty, fewer than 2 entries, or more than 6 entries
2. A timeframe entry is missing `label`
3. A timeframe entry has BOTH `trading_days` and `calendar` set, or NEITHER
4. `trading_days` is not a positive integer
5. `calendar` is set to anything other than `"ytd"` (case-insensitive — normalize to lowercase)
6. Duplicate `label` values within the timeframes list
7. `default_sort_column` is not one of the timeframe labels
8. `default_sort_direction` is not `"asc"` or `"desc"` (case-insensitive — normalize to lowercase)

Validation must run inside `Settings.load()`, not deferred to the screen. Bad config = startup error, not runtime surprise.

---

## Workflow: `workflows/multi_timeframe_sector_snapshot.py`

### Data carriers

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class TimeframeRS:
    """Relative strength result for one (sector, timeframe) pair."""
    label: str                  # matches Timeframe.label
    rs_value: float | None      # None if computation failed for this timeframe
    rs_path: tuple[float, ...]  # full RS path, used by sparkline when this column is sorted

@dataclass(frozen=True)
class SectorRow:
    """One row of the sector deep-dive table."""
    symbol: str                 # e.g. "XLK"
    name: str                   # e.g. "Technology"
    is_benchmark: bool          # True for the SPY pin-row
    timeframes: tuple[TimeframeRS, ...]  # one per configured timeframe, in same order
    error: str | None           # set if this sector failed entirely (e.g. fetch error)

@dataclass(frozen=True)
class MultiTimeframeSectorSnapshot:
    """The full sector deep-dive view."""
    rows: tuple[SectorRow, ...]  # SPY first, then 11 sectors in SPDR_SECTORS order
    timeframe_labels: tuple[str, ...]  # column header labels in display order
    timestamp: datetime          # when this snapshot was built (for staleness display)
    error: str | None            # set ONLY for catastrophic failure (benchmark fetch fails entirely)
```

### Builder function

```python
def build_multi_timeframe_sector_snapshot(
    timeframes: Sequence[Timeframe],
    sector_config: SectorConfig,
    data_service: DataService | None = None,
    now: datetime | None = None,
) -> MultiTimeframeSectorSnapshot:
    ...
```

**Behavior:**

1. Resolve `data_service` via `get_data_service()` if `None`. Resolve `now` to `datetime.now()` if `None`.
2. Compute the **longest required window** across all configured timeframes:
   - For `trading_days = N` entries: that's `N` trading days back
   - For `calendar = "ytd"` entries: from Jan 1 of `now.year` to today (in trading days, this is variable)
   - Take the max
   - Add a small buffer (e.g. +5 trading days) to ensure enough data after alignment
3. Compute a calendar start date that comfortably covers the longest trading-day window. **Conservative rule:** multiply trading days by 1.6 to get calendar days (~252/365 → 1.45, plus buffer). For YTD, the start is unambiguous.
4. Fetch aligned returns once via `load_aligned_returns(tickers, start, end, ..., data_service=data_service)` for SPY + the 11 SPDR sectors.
5. If the benchmark (`sector_config.comparison_ticker`, which is "SPY") is absent or has insufficient data → return a snapshot with `rows=()`, `error="Benchmark SPY unavailable: <reason>"`, `timeframe_labels` populated.
6. For each sector ticker that successfully loaded:
   - For each configured timeframe:
     - Slice the returns DataFrame to the timeframe's window
     - YTD: filter to rows with index date >= Jan 1 of `now.year`
     - trading_days = N: take the last `N` rows of the aligned DataFrame
     - If slice has fewer than 2 rows → `TimeframeRS(label=tf.label, rs_value=None, rs_path=())`
     - Otherwise call `calculate_relative_strength(sliced_returns, sector_ticker, benchmark)` → `(rs_value, rs_path)` → wrap in `TimeframeRS`
   - Build `SectorRow(symbol, name, is_benchmark=False, timeframes=(...), error=None)`
   - If the sector ticker is missing from the aligned returns entirely → `SectorRow(symbol, name, is_benchmark=False, timeframes=(empty TimeframeRS list), error="No data")`
7. Prepend the SPY benchmark row: every timeframe has `rs_value=0.0` and `rs_path=(0.0,) * max(2, slice_length)`.
8. Return `MultiTimeframeSectorSnapshot(rows=..., timeframe_labels=tuple(tf.label for tf in timeframes), timestamp=now, error=None)`.

**Error model:**

- One bad sector → that row has `error` set, others render
- Benchmark missing → snapshot-level `error`, `rows=()`
- One bad timeframe within an otherwise-good sector → that `TimeframeRS` has `rs_value=None`, others render

**Architectural rules (from `ARCHITECTURE.md`):**

- No `Textual`, no `asyncio` imports (the docstring may mention them; an actual `import asyncio` is forbidden)
- No `yfinance`, no `schwab` imports — go through `DataService`
- Workflow returns data, never rendered output
- Sector list comes from `workflows/sector_snapshot.SPDR_SECTORS` — import and reuse, don't redefine

---

## Widget: `cockpit/widgets/sector_table.py`

A `SectorTable(Widget)` that renders a `MultiTimeframeSectorSnapshot` as a sortable, focusable table.

### Reactives on the widget

```python
snapshot: reactive[MultiTimeframeSectorSnapshot | None] = reactive(None)
sort_column: reactive[str] = reactive("1M")          # timeframe label currently sorted
sort_direction: reactive[str] = reactive("desc")     # "asc" or "desc"
focused_column: reactive[str] = reactive("1M")       # column the user is navigating with arrows
```

`focused_column` and `sort_column` are intentionally separate. Arrow keys move `focused_column`; Enter promotes it to `sort_column` and/or toggles direction (see "Interaction model" below).

### Layout

Columns, left to right:

```
SYMBOL  NAME             <tf1>  <tf2>  ... <tfN>   SPARKLINE
```

- `SYMBOL`: 6 chars, all caps, left-aligned, padded
- `NAME`: 14 chars, left-aligned, truncated with ellipsis if longer
- Each `<tf>` column: 8 chars, right-aligned, formatted via `fmt_rs_pct` (signed, 2 decimals, `%` suffix); em dash `—` if `rs_value is None`
- `SPARKLINE`: minimum 12 chars wide; uses `make_sparkline` against the `rs_path` of the **currently-sorted timeframe** for that row

Header row: column labels in the same widths. Above the focused column, the label is **bold** and **underlined**; the sort-direction arrow (`▲` desc — biggest at top — or `▼` asc — smallest at top) appears next to the sort_column label.

Wait — convention check: `▲` typically means "ascending sort, smallest at top." We're using **▼ for descending (biggest at top)** and **▲ for ascending (smallest at top)** because that's what every trading terminal does (Bloomberg, TradingView). State this explicitly in the header rendering code so a future reader doesn't flip it.

The SPY pin-row renders with a thin horizontal rule below it (a row of `─` characters across the table width), separating it from the 11 sector rows. SPY's RS cells render as `+0.00%` with **neutral** background (use `gradient_neutral` directly — do not pass 0.0 through the gradient interpolator, since 0 maps near neutral but we want it pinned exactly).

### Cell coloring

RS cells in non-SPY rows get a background color from `relative_strength_to_color(rs_value, intensity_max_pct, theme_colors)`, reusing the existing function. Pull `intensity_max_pct` from `sector_config.intensity_max_pct` (the same setting the home panel uses — do not introduce a new one).

Cells with `rs_value is None` render with neutral background.

### Bindings (on the widget OR the screen — see "Interaction model")

```python
BINDINGS = [
    Binding("left",  "focus_prev_column", "Prev column", show=False),
    Binding("right", "focus_next_column", "Next column", show=False),
    Binding("enter", "apply_sort",        "Sort/toggle"),
]
```

Where the bindings live: put them on the **screen**, not the widget, and have the screen call methods on the table. This keeps the widget a passive renderer (matches the Session 3-5 pattern: widgets render, screens orchestrate).

### Interaction model

- On mount: `focused_column = sort_column = default_sort_column` (from config); `sort_direction = default_sort_direction`.
- Left/Right: rotate `focused_column` through the timeframe labels in display order. Wraps at the ends.
- Enter:
  - If `focused_column == sort_column`: toggle `sort_direction` between `"asc"` and `"desc"`.
  - Else: set `sort_column = focused_column`; reset `sort_direction = "desc"` (the more useful default — biggest movers at top).
- Sorting: the SPY benchmark row stays pinned at the top regardless of sort. Below it, the 11 sector rows are sorted by `rs_value` of `sort_column`; rows with `rs_value is None` go to the bottom in alphabetical-by-symbol order, regardless of sort direction.
- After sort or direction change: the sparkline column re-renders using each row's `TimeframeRS.rs_path` for the new `sort_column`.

### Refresh handling

The widget is a passive renderer. Setting `snapshot` (via `watch_snapshot`) triggers a re-render. There is no flash animation (matches Session 5 sector decision — the gradient is the visual).

---

## Screen: `cockpit/screens/sectors.py`

```python
class SectorDeepDiveScreen(Screen):
    BINDINGS = [
        Binding("escape",  "app.pop_screen", "Back",       show=True),
        Binding("r",       "refresh",        "Refresh",    show=True),
        Binding("left",    "focus_prev",     "Prev col",   show=True),
        Binding("right",   "focus_next",     "Next col",   show=True),
        Binding("enter",   "apply_sort",     "Sort",       show=True),
        Binding("?",       "app.push_screen('help')", "Help", show=True),
        Binding("t",       "app.action_cycle_theme",  "Theme", show=True),
        Binding("q",       "app.quit",        "Quit",      show=True),
    ]

    snapshot: reactive[MultiTimeframeSectorSnapshot | None] = reactive(None)
```

### Composition

```
Header: title "SECTOR DEEP-DIVE" + last-refresh wall-clock time + timeframe count
SectorTable widget (fills the screen body)
Footer: CommandFooter showing the bindings above
```

Reuse `ClockHeader` if it cleanly fits; otherwise a simpler header is fine. Reuse `CommandFooter`.

### Worker pattern (mirrors Session 5 home screen)

```python
@work(group="sector_deep_dive", thread=True, exclusive=True)
def refresh_sectors_deep(self) -> None:
    snapshot = build_multi_timeframe_sector_snapshot(
        timeframes=self.app.settings.sector_deep_dive_config.timeframes,
        sector_config=self.app.settings.sector_config,
        data_service=get_data_service(),
    )
    self.snapshot = snapshot
```

- `on_mount`: kick off `refresh_sectors_deep()` immediately, then `self.set_interval(config.refresh_interval_seconds, self.refresh_sectors_deep)`.
- `action_refresh` calls `self.refresh_sectors_deep()` directly.
- `watch_snapshot` pushes the new snapshot into the `SectorTable` widget and updates the header's "last refresh" wall-clock.

### Action delegation

The screen's `action_focus_prev`, `action_focus_next`, `action_apply_sort` call methods on the `SectorTable` instance (the widget mutates its own reactives; the screen is just routing keystrokes). The widget then re-renders.

### Entry from home

In `cockpit/screens/home.py`:

1. Add an `Action` for `s`:
   ```python
   Binding("s", "open_sector_deep_dive", "Sectors", show=True)
   ```
2. Implement `action_open_sector_deep_dive`:
   ```python
   def action_open_sector_deep_dive(self) -> None:
       self.app.push_screen(SectorDeepDiveScreen())
   ```
3. The home screen's existing sector worker is **not** stopped or paused — it continues to run in the background per Textual's default `push_screen` behavior. This is intentional (re-derived from planning conversation: 5-min cadence is cheap).

### Exit back to home

`Esc` pops the screen via standard Textual `app.pop_screen` action. The deep-dive's timer and worker are torn down by Textual on pop. The home screen resumes visibility with whatever state it had; its own polling is unaffected.

---

## Styling

Add to `cockpit/styles.tcss`. Keep the aesthetic consistent with the home screen — same border conventions, same use of CSS variables.

```tcss
SectorDeepDiveScreen {
    layout: vertical;
}

SectorDeepDiveScreen > #deep-dive-header {
    height: 1;
    color: $text;
    background: $surface;
    padding: 0 1;
}

SectorTable {
    height: 1fr;
    border: solid $border;
}

SectorTable > .sector-table--header {
    text-style: bold;
    color: $text-dim;
}

SectorTable > .sector-table--header-focused {
    text-style: bold underline;
    color: $text;
}

SectorTable > .sector-table--spy-row {
    color: $text-dim;
    text-style: italic;
}

SectorTable > .sector-table--separator {
    color: $border;
}
```

Adjust class names to match whatever Textual idiom the implementation uses; the goal is themable styling, not these exact selectors.

---

## Help screen update

In `cockpit/screens/help.py`, add a row for `s` under the "Navigation" or equivalent section:

```
s    Sector deep-dive
```

And inside the deep-dive screen's contribution to the help text (if help is screen-scoped), document:

```
← →    Move column focus
Enter  Sort by focused column (toggles direction if already sorted)
r      Refresh
Esc    Back to home
```

If help is currently a single static screen, just add the deep-dive bindings under a new sub-heading. Don't refactor the help screen architecture.

---

## Acceptance criteria

Each AC must have a check in `scripts/verify_session6.py` where automation is possible. Manual-verify ACs are marked.

### Configuration & defaults

1. With no `[sector_deep_dive]` in `cockpit.toml`, `Settings.load()` returns a `SectorDeepDiveConfig` with: 60s refresh, sort=`"1M"` desc, 4 timeframes (5D / 1M / 3M / YTD).
2. With a full `[sector_deep_dive]` section, all four config values parse correctly.
3. `timeframes = []` raises `ValueError` at load time.
4. A timeframe entry with both `trading_days = 21` and `calendar = "ytd"` raises `ValueError`.
5. A timeframe entry with neither field raises `ValueError`.
6. `calendar = "qtd"` raises `ValueError` (only `"ytd"` is supported in Session 6).
7. Duplicate labels (e.g. two `"1M"` entries) raise `ValueError`.
8. `default_sort_column = "5Y"` when no such timeframe exists raises `ValueError`.
9. `default_sort_direction = "sideways"` raises `ValueError`.
10. 7 configured timeframes raises `ValueError`.

### Workflow correctness

11. `build_multi_timeframe_sector_snapshot()` with default timeframes returns a snapshot whose `rows` has length 12 (SPY + 11 sectors).
12. The first row is SPY with `is_benchmark=True` and every `TimeframeRS.rs_value == 0.0`.
13. Sector rows have `is_benchmark=False` and at least one `TimeframeRS` with non-None `rs_value` (assuming live data fetch succeeds).
14. `timeframe_labels` matches the labels passed in, in order.
15. When a bad sector ticker is injected (monkeypatch `SPDR_SECTORS` to include `"XLZZZ": "Bogus"` temporarily, OR pass through `SectorConfig`), that row has `error` set; other rows render normally.
16. When the benchmark is unavailable (monkeypatch `sector_config.comparison_ticker = "ZZSPY"`), the snapshot has `error` set and `rows == ()`.
17. YTD timeframe slices correctly: in May 2026, a YTD slice has roughly ~95 trading days; in early January it has 1-5 trading days; in late December ~250.
18. trading_days timeframe slices correctly: `trading_days = 21` produces an RS path of length 21 (or fewer if data is short — but normally 21).
19. A timeframe with insufficient data within its window has `rs_value=None` and `rs_path=()`, while other timeframes for the same sector still produce values.

### Architectural compliance

20. `workflows/multi_timeframe_sector_snapshot.py` does not contain `import asyncio` or any `textual` import.
21. `workflows/multi_timeframe_sector_snapshot.py` does not contain `import yfinance` or `import schwab`.
22. `cockpit/screens/sectors.py` does not import from `marketdata/` directly (must go through workflow).
23. `cockpit/widgets/sector_table.py` does not import from `workflows/` or `marketdata/`.
24. `workflows/multi_timeframe_sector_snapshot.py` imports `SPDR_SECTORS` from `workflows/sector_snapshot.py` (reuse, no redefinition).

### Screen wiring

25. `s` is bound on `HomeScreen` and pushes `SectorDeepDiveScreen`. Verify via inspecting the screen's `BINDINGS`.
26. `Esc` is bound on `SectorDeepDiveScreen` to pop back to home.
27. The home screen's sector worker keeps its 5-minute timer (do not modify Session 5's `set_interval` call).
28. The deep-dive screen's `set_interval` uses `sector_deep_dive_config.refresh_interval_seconds` (60s by default).

### Interaction (MANUAL VERIFY — list in debrief)

29. Pressing `s` on home transitions to the deep-dive screen within ~1 second.
30. The deep-dive screen displays 12 rows (SPY first, then 11 sectors) within ~10 seconds of entry.
31. Arrow keys move the focused-column highlight without changing the sort.
32. Enter on a non-sorted focused column sets it as the sort column (default to desc) and re-orders the rows.
33. Enter on the already-sorted column toggles direction; the sort arrow on the header flips between ▼ and ▲.
34. The sparkline column updates to show the rs_path of whatever column is currently sorted.
35. The SPY row stays pinned at the top regardless of sort.
36. Cell backgrounds shift along the gradient by magnitude.
37. After 60 seconds (or after pressing `r`), the timestamp in the header updates and any RS value changes are reflected.
38. `Esc` returns to home; the home screen is visible with its previous state intact.
39. Theme cycle (`t`) on the deep-dive screen updates gradient colors on the **next** refresh (acceptable per Session 5 precedent — do not attempt to fix this now).

### Regression checks

40. The home screen's `SectorPanel` from Session 5 still renders identically. The home `[sectors]` config section is untouched.
41. Existing scripts (`get_data`, `run_backtest`, `correlations`) still work without modification.

---

## Verification script

Create `scripts/verify_session6.py` following the structure of `scripts/verify_session5.py`. It must:

- Run each automated AC as a function returning `(passed: bool, message: str)`
- Print a single-line PASS/FAIL per AC
- Exit code 0 if all pass; 1 if any fail
- For workflow ACs, build a real snapshot against live yfinance (same as Session 5)
- For config ACs, write temporary TOML files to a tmpdir and load them

Interactive ACs (29–39) are out of scope for the verifier — they are checked manually and listed in the debrief.

---

## Patterns to follow (from Sessions 3-5)

### Worker + reactive + watch_* template (from `home.py`)

```python
class SectorDeepDiveScreen(Screen):
    snapshot: reactive[MultiTimeframeSectorSnapshot | None] = reactive(None)

    def on_mount(self) -> None:
        self.refresh_sectors_deep()
        config = self.app.settings.sector_deep_dive_config
        self.set_interval(config.refresh_interval_seconds, self.refresh_sectors_deep)

    @work(group="sector_deep_dive", thread=True, exclusive=True)
    def refresh_sectors_deep(self) -> None:
        snapshot = build_multi_timeframe_sector_snapshot(
            timeframes=self.app.settings.sector_deep_dive_config.timeframes,
            sector_config=self.app.settings.sector_config,
            data_service=get_data_service(),
        )
        self.snapshot = snapshot

    def watch_snapshot(self, snapshot: MultiTimeframeSectorSnapshot | None) -> None:
        if snapshot is None:
            return
        self.query_one(SectorTable).snapshot = snapshot
        # update header timestamp here
```

### Settings.load() validation pattern

Match the style already in `Settings.load()` for `SectorConfig`. Raise `ValueError` with a message naming the offending field and what was expected.

---

## What to do if stuck

- **Schwab token issues:** ignore. yfinance is the working source; `DataService` routes around Schwab when unavailable.
- **YTD slice empty in tests (e.g. running on Jan 1):** that's expected behavior — `rs_value=None`. Not a bug.
- **`pandas-ta` in requirements still:** ignore; it's a Roadmap cleanup item, not relevant here.
- **CSS variables not resolving:** check `cockpit/app.py::get_css_variables()` — Session 5 added the gradient keys; do not modify that method.
- **Textual screen transition glitches:** if `push_screen` causes the home screen's panels to lose state, that's a Textual issue, not a workflow issue — flag it in the debrief, don't try to fix in this session.
- **Sort stability:** if Python's `sorted()` produces unstable ordering for equal-value rows, use a stable tiebreaker (alphabetical symbol). Document this in the code.
- **Spec ambiguity:** STOP and ask before guessing. Quality of spec adherence matters more than speed.

---

## Debrief expectations

At the end of execution, produce `notes/session-6-debrief.md` covering:

1. AC table (automated: pass/fail with detail; manual: listed for human verification)
2. Files created / modified
3. Key findings (surprises, bugs encountered, design choices that came up during execution)
4. Live-data observations (analogous to Session 5's "as of 2026-05-20" section — what does the deep-dive actually show right now?)
5. Open questions for Session 7

The debrief is the bridge to the next planning chat. Be specific about what wasn't obvious from the spec.
