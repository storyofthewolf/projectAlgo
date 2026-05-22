# Session 8 Spec — Ticker Drill-Down Screen

**Target executor:** Claude Sonnet 4.6 in Claude Code
**Estimated scope:** one new modal screen, one new full-screen drill-down, one new workflow with two builders, one new config section, layout for 120×30 minimum
**Status when starting:** Sessions 1–7 complete. All five home-screen panels wired to live data. No mock data remains in production paths.

---

## 0. Mandatory read list

Before writing any code, read these in order:

1. `specs/ARCHITECTURE.md` — load-bearing design principles (especially §3 data layer, §6 workflows orchestrate / UI renders, §9 information density)
2. `specs/ROADMAP.md` — context on what's done and what's next
3. `notes/session-7-debrief.md` — current state of the codebase as of last session
4. `specs/session-3-spec.md` — canonical workflow + reactive + worker template (this is the template you will follow)
5. `specs/session-7-spec.md` — most recent screen-addition spec, includes the modal/deep-dive pattern with config-loaded-in-`on_mount`
6. `cockpit/screens/sectors.py` and `cockpit/screens/correlations.py` — concrete examples of the deep-dive screen pattern
7. `cockpit/widgets/sector_table.py` — concrete example of a Rich-markup-based table widget
8. `analysis/technical_analysis.py` — `calculate_sma` and `calculate_rsi` exist and work; do not reimplement

You do not need to read the polish-related debrief items from earlier sessions — polish is explicitly out of scope for this session.

---

## 1. Goal

Add an interactive ticker drill-down to the cockpit:

- Global `/` binding opens a modal that accepts a ticker symbol
- On Enter, push a full-screen drill-down for that ticker showing:
  - Header strip: ticker, name, live price/change/change %, volume, day range, 52-week range with percentile
  - OHLC table: most recent 30 trading days, newest first, scrollable
  - Indicators column: SMA(20), SMA(50), SMA(200) with % distance from price; RSI(14) with regime label
- Live quote repolls every 30s
- History and derived indicators do **not** repoll on the timer (they are intraday-stable). They re-fetch only on explicit `r`.
- `/` from within the drill-down replaces the current ticker (Bloomberg-style)

This is the last yfinance-only session before the cockpit is feature-complete for monitoring. Schwab integration and any polish pass are subsequent, independent sessions.

---

## 2. What stays as-is (non-goals — do not touch)

- `visualization/view_stock.py` — no CLI arg added, no subprocess spawn. "Open in Dash" is deferred to the polish session.
- `cockpit/mock_data.py` — leave it alone even if nothing imports it.
- `pandas-ta` removal from `requirements.txt` — leave for polish session.
- Sparkline visual resolution — leave for polish session.
- Theme change → immediate recolor — leave for polish session.
- `CommandFooter` audit — leave for polish session.
- Account panel — still placeholder; not touched in this session.
- All existing screens (`HomeScreen`, `SectorDeepDiveScreen`, `CorrelationDeepDiveScreen`, `HelpScreen`) — only the bindings and help entries need updates, no structural changes.
- All existing workflows — untouched.
- All existing widgets — untouched except where reused.

If a polish-style improvement is tempting while working on drill-down, write it down for the polish session debrief and move on.

---

## 3. File layout

### New files

| File | Purpose |
|------|---------|
| `workflows/ticker_detail_snapshot.py` | `TickerDetailSnapshot`, `IndicatorReadout`, `TickerStats`, `build_ticker_detail_snapshot()`, `build_ticker_quote_snapshot()` |
| `cockpit/screens/ticker_finder_modal.py` | `TickerFinderModal` — Textual `ModalScreen` with single `Input` |
| `cockpit/screens/ticker_detail.py` | `TickerDetailScreen` — full-screen drill-down |
| `cockpit/widgets/ticker_header.py` | `TickerHeader` — header strip widget |
| `cockpit/widgets/ohlc_table.py` | `OHLCTable` — Rich-markup OHLC table with scroll |
| `cockpit/widgets/indicator_panel.py` | `IndicatorPanel` — right-side indicators readout |
| `scripts/verify_session8.py` | Automated acceptance-criteria checker (model on `scripts/verify_session7.py`) |

### Modified files

| File | Changes |
|------|---------|
| `config/settings.py` | Add `TickerDetailConfig` dataclass, `_parse_ticker_detail()`, `ticker_detail_config` field on `Settings` |
| `cockpit.toml` | Add `[ticker_detail]` section |
| `cockpit/app.py` | Add global `/` binding on `CockpitApp`; add `action_open_ticker_finder` |
| `cockpit/screens/help.py` | Document `/` under global section; add new "TICKER DRILL-DOWN SCREEN" section |
| `cockpit/styles.tcss` | Add CSS for `TickerFinderModal`, `TickerDetailScreen`, `TickerHeader`, `OHLCTable`, `IndicatorPanel` |

Do **not** modify `home.py` or any existing screen beyond what is necessary to wire the `/` binding. The `/` binding lives on `CockpitApp` (global), not on `HomeScreen`, so home does not need to change.

---

## 4. Configuration

Add to `cockpit.toml`:

```toml
[ticker_detail]
history_display_days = 30          # OHLC rows shown in the table
history_lookback_days = 252        # bars fetched for SMA-200 computation (~1 trading year)
quote_refresh_seconds = 30
sma_windows = [20, 50, 200]
rsi_window = 14
rsi_oversold = 30                  # below this → "oversold" regime label
rsi_overbought = 70                # above this → "overbought" regime label
```

`history_display_days` and `history_lookback_days` are intentionally distinct. The table displays 30 days; the indicators require 252 days of history to compute SMA-200. The workflow fetches `history_lookback_days` worth of bars and the table slices the most recent `history_display_days`.

### `TickerDetailConfig` dataclass

In `config/settings.py`, frozen dataclass:

```python
@dataclass(frozen=True)
class TickerDetailConfig:
    history_display_days: int
    history_lookback_days: int
    quote_refresh_seconds: int
    sma_windows: tuple[int, ...]
    rsi_window: int
    rsi_oversold: float
    rsi_overbought: float
```

Add `_parse_ticker_detail(raw: dict) -> TickerDetailConfig` following the existing `_parse_correlations` / `_parse_correlation_deep_dive` pattern. Defensive defaults if section missing. Add `ticker_detail_config` field on `Settings`.

---

## 5. Workflow layer

`workflows/ticker_detail_snapshot.py` is the **single source of truth** for ticker-detail data. The screen never calls `DataService` or `analysis/*` functions directly.

### Dataclasses (all frozen, all module-level)

```python
from dataclasses import dataclass
from datetime import datetime
import pandas as pd
from core.quote import Quote


@dataclass(frozen=True)
class IndicatorReadout:
    """SMA + RSI values plus % distance from current price."""
    sma_values: dict[int, float | None]      # {20: 185.21, 50: 181.84, 200: 175.32}
    sma_vs_price_pct: dict[int, float | None]  # {20: +1.19, 50: +3.07, 200: +6.90}
    rsi: float | None
    rsi_regime: str  # "oversold" | "neutral" | "overbought" | "unknown"


@dataclass(frozen=True)
class TickerStats:
    """Derived stats from history + quote."""
    week_52_high: float | None
    week_52_low: float | None
    week_52_percentile: float | None  # 0-100; where current price sits in 52w range
    day_high: float | None
    day_low: float | None
    avg_volume_30d: float | None


@dataclass(frozen=True)
class TickerDetailSnapshot:
    ticker: str
    name: str | None             # may come from yfinance .info; None if unavailable
    quote: Quote | None
    history: pd.DataFrame | None # OHLCV; index is DatetimeIndex; full lookback length
    indicators: IndicatorReadout | None
    stats: TickerStats | None
    error: str | None            # only set on catastrophic failure (ticker not found)
    quote_stale: bool            # True if quote repoll failed and we kept the old one
    timestamp: datetime          # when this snapshot was constructed
```

### Builder functions

```python
def build_ticker_detail_snapshot(
    ticker: str,
    config: TickerDetailConfig,
    data_service: DataService | None = None,
    now: datetime | None = None,
) -> TickerDetailSnapshot:
    """Full build — quote + history + derived. Used on screen open and on `r`."""

def build_ticker_quote_snapshot(
    ticker: str,
    data_service: DataService | None = None,
    now: datetime | None = None,
) -> Quote | None:
    """Quote only — used by the 30s repoll. Returns None on failure."""
```

### `build_ticker_detail_snapshot` algorithm

1. Resolve `data_service = data_service or get_data_service()`, `now = now or datetime.now()`
2. Normalize ticker to upper case
3. Fetch live quote via `data_service.get_live_quote(ticker)`. On failure, log warning; quote is None.
4. Fetch history: `end = now.date()`, `start = end - timedelta(days=int(config.history_lookback_days * 1.5))` (overshoot to ensure enough trading days; trim later).
   - Call `data_service.get_historical_ohlcv(ticker, start, end, interval="1d")`.
   - On failure or empty result with quote also None → return snapshot with `error="Ticker not found: {ticker}"` and all other fields None.
   - On failure but quote OK → log warning, history is None, derived fields are None.
5. If history is not None, trim to most recent `config.history_lookback_days` bars (`history.tail(config.history_lookback_days)`).
6. Compute indicators from history (see §5.1).
7. Compute stats from history + quote (see §5.2).
8. Optionally fetch `name` from yfinance `.info["longName"]` — wrap in try/except; on failure, set `name = None`. **Do not block on this.** This is the only piece of source-specific code in the workflow; if it's structurally awkward to do source-agnostically, just call yfinance's `Ticker(...).info` directly and accept the data-layer leak as a documented exception for cosmetic metadata. Mark this clearly in a comment.
9. Return snapshot with `error=None`, `quote_stale=False`, `timestamp=now`.

### 5.1 Indicator computation

For each window `w` in `config.sma_windows`:
- If `len(history) < w` → `sma_values[w] = None`, `sma_vs_price_pct[w] = None`
- Else → `sma = calculate_sma(history["Close"], window=w).iloc[-1]`
  - `sma_values[w] = float(sma)`
  - If quote is not None: `sma_vs_price_pct[w] = (quote.price - sma) / sma * 100`
  - Else: `sma_vs_price_pct[w] = None`

For RSI:
- Need at least `rsi_window + 1` rows; check before calling
- `rsi_series = calculate_rsi(history["Close"], window=config.rsi_window)`
- `rsi = float(rsi_series.iloc[-1])` if not NaN, else None
- Regime:
  - `rsi is None` → `"unknown"`
  - `rsi < rsi_oversold` → `"oversold"`
  - `rsi > rsi_overbought` → `"overbought"`
  - else → `"neutral"`

### 5.2 Stats computation

- `week_52_high = float(history["High"].tail(252).max())` if `len(history) >= 20` else None (use whatever is available even if < 252)
- `week_52_low = float(history["Low"].tail(252).min())` analogously
- If quote and both 52w values: `week_52_percentile = (quote.price - low) / (high - low) * 100` (clipped to [0, 100])
- `day_high = quote.day_high` if available on `Quote`, else None — **note:** `Quote` does not currently have day_high/day_low. Use the most recent bar's High/Low from history as a proxy, since yfinance `fast_info` provides them on `Ticker` but not via `get_live_quote`. Document this in a workflow comment.
- `avg_volume_30d = float(history["Volume"].tail(30).mean())` if `len(history) >= 5`, else None

### 5.3 `build_ticker_quote_snapshot`

Just `return data_service.get_live_quote(ticker)` wrapped in try/except returning None on failure. Three lines. The screen handles `quote_stale` flagging.

---

## 6. Modal screen

`cockpit/screens/ticker_finder_modal.py`

### Class

```python
from textual.screen import ModalScreen
from textual.widgets import Input
from textual.containers import Container


class TickerFinderModal(ModalScreen[str | None]):
    """Centered modal accepting a ticker symbol. Returns the validated ticker (upper-cased) or None on Esc."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def compose(self):
        with Container(id="finder-box"):
            yield Static("FIND TICKER", id="finder-title")
            yield Input(placeholder="ticker symbol…", id="finder-input")

    def on_mount(self):
        self.query_one("#finder-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted):
        raw = event.value.strip().upper()
        if not raw:
            return  # no-op; modal stays open
        if not _is_valid_ticker(raw):
            return  # no-op; could add a status line later
        self.dismiss(raw)

    def action_cancel(self):
        self.dismiss(None)
```

### Ticker validation

```python
import re
_TICKER_RE = re.compile(r"^[A-Z0-9.\-=^]{1,12}$")

def _is_valid_ticker(s: str) -> bool:
    return bool(_TICKER_RE.match(s))
```

Allowed chars: A-Z, 0-9, `.`, `-`, `=`, `^`. Length 1-12. This covers normal tickers (`AAPL`), special yfinance symbols (`^VIX`, `^TNX`, `DX-Y.NYB`, `CL=F`, `GC=F`, `BRK.B`).

### Global `/` binding

In `cockpit/app.py`, add to `CockpitApp.BINDINGS`:

```python
("slash", "open_ticker_finder", "Find"),
```

Action method:

```python
def action_open_ticker_finder(self) -> None:
    def _on_dismissed(ticker: str | None) -> None:
        if ticker is None:
            return
        self.push_screen(TickerDetailScreen(ticker))
    self.push_screen(TickerFinderModal(), _on_dismissed)
```

The binding works from any screen because it's on the app. From the drill-down, pressing `/` opens the modal; on submit, **pop the current drill-down and push the new one** so the back stack stays sane:

```python
# inside TickerDetailScreen.action_find or via callback
def _on_dismissed(ticker: str | None) -> None:
    if ticker is None:
        return
    self.app.pop_screen()  # pop current drill-down
    self.app.push_screen(TickerDetailScreen(ticker))
```

Decide cleanly: the global action on `CockpitApp` handles the from-home case (just push); the drill-down screen overrides locally with its own `/` binding that pops-then-pushes. Both end in a drill-down for the new ticker.

---

## 7. Drill-down screen

`cockpit/screens/ticker_detail.py`

### Skeleton

```python
class TickerDetailScreen(Screen):
    BINDINGS = [
        ("escape", "back", "Back"),
        ("r", "refresh", "Refresh"),
        ("slash", "find_ticker", "Find"),
        ("j", "scroll_down", "Scroll ↓"),
        ("k", "scroll_up", "Scroll ↑"),
        ("down", "scroll_down", ""),
        ("up", "scroll_up", ""),
        ("question_mark", "show_help", "Help"),
        ("t", "cycle_theme", "Theme"),
    ]

    snapshot: reactive[TickerDetailSnapshot | None] = reactive(None)

    def __init__(self, ticker: str):
        super().__init__()
        self._ticker = ticker
        self._cfg: TickerDetailConfig | None = None
        self._scroll_offset = 0  # OHLC table scroll position
```

Load `self._cfg` lazily in `on_mount` via `self.app.settings.ticker_detail_config`, following the Session 6/7 pattern.

### Compose

Two-column body under the header:

```python
def compose(self) -> ComposeResult:
    yield ClockHeader()
    yield TickerHeader(id="ticker-header")
    with Horizontal(id="detail-body"):
        yield OHLCTable(id="ohlc-table")
        yield IndicatorPanel(id="indicator-panel")
    yield CommandFooter()
```

### Workers

```python
@work(exclusive=True, group="ticker_full", thread=True)
def refresh_full(self) -> None:
    snap = build_ticker_detail_snapshot(self._ticker, self._cfg)
    self.app.call_from_thread(self._set_snapshot, snap)

@work(exclusive=True, group="ticker_quote", thread=True)
def refresh_quote(self) -> None:
    if self.snapshot is None or self.snapshot.error is not None:
        return
    quote = build_ticker_quote_snapshot(self._ticker)
    self.app.call_from_thread(self._apply_quote, quote)

def _set_snapshot(self, snap: TickerDetailSnapshot) -> None:
    self.snapshot = snap

def _apply_quote(self, quote: Quote | None) -> None:
    if self.snapshot is None:
        return
    if quote is None:
        self.snapshot = dataclasses.replace(self.snapshot, quote_stale=True, timestamp=datetime.now())
    else:
        # recompute sma_vs_price_pct since price changed
        new_indicators = self._recompute_vs_price(self.snapshot.indicators, quote.price) if self.snapshot.indicators else None
        self.snapshot = dataclasses.replace(
            self.snapshot,
            quote=quote,
            quote_stale=False,
            indicators=new_indicators,
            timestamp=datetime.now(),
        )
```

`_recompute_vs_price` is a small helper that updates only the `sma_vs_price_pct` dict using the new price (the SMA values themselves don't change on a 30s repoll since they're computed from daily bars).

### On mount

```python
def on_mount(self) -> None:
    self._cfg = self.app.settings.ticker_detail_config
    self.refresh_full()
    self.set_interval(self._cfg.quote_refresh_seconds, self.refresh_quote)
```

### Watch handler

```python
def watch_snapshot(self, _old, new: TickerDetailSnapshot | None) -> None:
    if new is None:
        return
    self.query_one("#ticker-header", TickerHeader).update_snapshot(new)
    self.query_one("#ohlc-table", OHLCTable).update_snapshot(new, self._scroll_offset)
    self.query_one("#indicator-panel", IndicatorPanel).update_snapshot(new)
```

### Actions

```python
def action_back(self) -> None:
    self.app.pop_screen()

def action_refresh(self) -> None:
    self.refresh_full()

def action_find_ticker(self) -> None:
    def _on_dismissed(ticker: str | None) -> None:
        if ticker is None:
            return
        self.app.pop_screen()
        self.app.push_screen(TickerDetailScreen(ticker))
    self.app.push_screen(TickerFinderModal(), _on_dismissed)

def action_scroll_down(self) -> None:
    if self.snapshot is None or self.snapshot.history is None:
        return
    max_offset = max(0, len(self.snapshot.history) - self._cfg.history_display_days)
    self._scroll_offset = min(self._scroll_offset + 1, max_offset)
    self.query_one("#ohlc-table", OHLCTable).update_snapshot(self.snapshot, self._scroll_offset)

def action_scroll_up(self) -> None:
    self._scroll_offset = max(0, self._scroll_offset - 1)
    if self.snapshot is not None:
        self.query_one("#ohlc-table", OHLCTable).update_snapshot(self.snapshot, self._scroll_offset)
```

Arrow keys are bound separately from `j`/`k` and both call the same actions.

---

## 8. Widgets

### `TickerHeader`

Three rows of content, single `PanelFrame`. Uses Rich markup via `Static.update()`.

```
┌─ AAPL ─ Apple Inc. ──────────────────────────── 14:32:05 ET [updated 14:31:58] ─┐
│  $187.42  ▲ +$1.24  +0.66%   Vol 42.1M                                          │
│  Day  186.18 – 188.91     52W  164.08 – 199.62  (68% of range)                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

If `quote_stale=True`, append ` [STALE]` next to the timestamp in dimmed text.
If `quote is None` and `error is None`, show price/change as `—`.
If `error is not None`, show "TICKER NOT FOUND" centered in the panel; suppress all numeric rows.
If `name is None`, just omit it from the title (border reads `┌─ AAPL ─`).

Use `fmt_price`, `fmt_pct`, `fmt_change`, `fmt_arrow`, `fmt_volume` from `cockpit/format.py`. The color of the change row follows the standard positive/negative theme variables.

### `OHLCTable`

A `Static` widget rendered as a Rich-markup table. Columns: DATE, OPEN, HIGH, LOW, CLOSE. Right-aligned decimals (2 places), left-aligned date.

The widget receives `(snapshot, scroll_offset)`. It slices `snapshot.history.iloc[-(scroll_offset + history_display_days):-scroll_offset if scroll_offset > 0 else None]` and reverses for newest-first display. Display exactly `history_display_days` rows when possible; fewer if scrolled near the end.

Border title: `RECENT OHLC (last 30 days)`. If `history is None`, show "data unavailable" centered.

Scroll indicator in the border-bottom: `↑↓ j/k or arrows` when scrollable. If user has scrolled, indicate `[+N earlier bars]` in bottom-right.

### `IndicatorPanel`

A `Static` rendered as Rich markup, right column. Width hint via CSS.

```
┌─ INDICATORS ──────┐
│  SMA(20)   185.21 │
│   vs px:   +1.19% │
│                   │
│  SMA(50)   181.84 │
│   vs px:   +3.07% │
│                   │
│  SMA(200)  175.32 │
│   vs px:   +6.90% │
│                   │
│                   │
│  RSI(14)    58.3  │
│   regime:  neutral│
└───────────────────┘
```

- SMA values: 2 decimals
- `vs px` rows: signed percentage with 2 decimals, colored by sign using `$positive`/`$negative` theme vars
- RSI value: 1 decimal
- Regime label: lowercase; color the regime word — `oversold` (positive/green), `overbought` (negative/red), `neutral` (dim text), `unknown` (dim text, em dash)
- Any None value → em dash `—`

Use the existing `PanelFrame` wrapper.

---

## 9. CSS (`cockpit/styles.tcss`)

Add (don't modify existing rules):

```css
TickerFinderModal {
    align: center middle;
    background: $surface 70%;
}

TickerFinderModal #finder-box {
    width: 40;
    height: 7;
    border: thick $border;
    background: $surface;
    padding: 1 2;
}

TickerFinderModal #finder-title {
    color: $accent;
    text-style: bold;
    width: 100%;
    text-align: center;
    margin-bottom: 1;
}

TickerFinderModal Input {
    background: $surface;
    border: tall $border;
}

TickerDetailScreen #ticker-header {
    height: 5;
    border: round $border;
}

TickerDetailScreen #detail-body {
    height: 1fr;
}

TickerDetailScreen #ohlc-table {
    width: 70%;
    border: round $border;
}

TickerDetailScreen #indicator-panel {
    width: 30%;
    border: round $border;
}
```

Adjust heights/widths after testing in your actual terminal — these are starting values.

---

## 10. Help screen updates

In `cockpit/screens/help.py`:

1. Under the global bindings section, add a row for `/` — `Find ticker (drill-down)`
2. Add a new section "TICKER DRILL-DOWN SCREEN":
   - `R` — Refresh (full re-fetch)
   - `/` — Find different ticker
   - `J` / `↓` — Scroll OHLC down
   - `K` / `↑` — Scroll OHLC up
   - `Esc` — Back to previous screen
   - `T` — Cycle theme
   - `?` — This screen

Match the formatting of existing sections in `help.py`.

---

## 11. Acceptance criteria

`scripts/verify_session8.py` automates checks 1–30. Checks 31+ are interactive and require launching the cockpit.

### Automated (verify_session8.py must pass all)

1. `from workflows.ticker_detail_snapshot import TickerDetailSnapshot, IndicatorReadout, TickerStats, build_ticker_detail_snapshot, build_ticker_quote_snapshot` succeeds
2. `from config.settings import TickerDetailConfig` succeeds; `Settings.load().ticker_detail_config` returns a `TickerDetailConfig` instance
3. `ticker_detail_config.history_display_days == 30`
4. `ticker_detail_config.history_lookback_days == 252`
5. `ticker_detail_config.quote_refresh_seconds == 30`
6. `ticker_detail_config.sma_windows == (20, 50, 200)`
7. `ticker_detail_config.rsi_window == 14`
8. `build_ticker_detail_snapshot("AAPL", cfg)` returns a `TickerDetailSnapshot` with `error is None` (assumes network available; document caveat in script)
9. The returned snapshot's `history` is a non-empty DataFrame with columns `["Open", "High", "Low", "Close", "Volume"]`
10. The returned snapshot's `quote` is a `Quote` instance with a non-None `price`
11. The returned snapshot's `indicators.sma_values` has keys `{20, 50, 200}`
12. All `sma_values` are floats (assuming ≥200 trading days available; if not, skip with note)
13. `indicators.rsi` is a float between 0 and 100
14. `indicators.rsi_regime` is one of `{"oversold", "neutral", "overbought", "unknown"}`
15. `stats.week_52_high >= stats.week_52_low` (both non-None)
16. `0 <= stats.week_52_percentile <= 100`
17. `build_ticker_detail_snapshot("ZZZZNOTREAL", cfg)` returns snapshot with `error is not None` and `quote is None` and `history is None` (no exception raised)
18. `build_ticker_quote_snapshot("AAPL")` returns a `Quote` instance
19. `build_ticker_quote_snapshot("ZZZZNOTREAL")` returns `None` (no exception)
20. `TickerFinderModal` class importable from `cockpit.screens.ticker_finder_modal`
21. `TickerDetailScreen` class importable from `cockpit.screens.ticker_detail`
22. `_is_valid_ticker("AAPL")` → True; `_is_valid_ticker("^VIX")` → True; `_is_valid_ticker("BRK.B")` → True; `_is_valid_ticker("CL=F")` → True; `_is_valid_ticker("")` → False; `_is_valid_ticker("aapl space")` → False
23. `CockpitApp.BINDINGS` contains a binding for `slash`
24. `TickerDetailScreen.BINDINGS` contains bindings for `escape`, `r`, `slash`, `j`, `k`, `down`, `up`
25. `IndicatorReadout.sma_vs_price_pct` correctly reflects `(price - sma) / sma * 100` for a synthetic snapshot
26. RSI regime mapping: 25 → "oversold", 50 → "neutral", 75 → "overbought" (using default thresholds)
27. With `history` of length 100 (< 200) and SMA window of 200, `sma_values[200]` is None and `sma_vs_price_pct[200]` is None
28. `cockpit/screens/help.py` source contains the strings `"TICKER DRILL-DOWN SCREEN"` and `"Find ticker"`
29. No file in `cockpit/screens/ticker_detail.py` imports from `marketdata.*` (the screen must go through the workflow)
30. No file in `cockpit/widgets/ticker_header.py`, `cockpit/widgets/ohlc_table.py`, or `cockpit/widgets/indicator_panel.py` imports from `marketdata.*`

### Interactive (manual, document in debrief)

31. `python3.14 -m scripts.cockpit` launches; home screen renders normally; no regressions on watchlist, pulse, sectors, correlations
32. Pressing `/` opens centered modal with input field auto-focused
33. Typing `aapl` and Enter opens drill-down for AAPL; ticker shown upper-cased in header
34. Header strip shows price, change, change %, volume, day range, 52-week range with percentile
35. OHLC table shows 30 rows, newest at top, properly aligned columns
36. `j` and `↓` both scroll down; `k` and `↑` both scroll up
37. Scrolling past end is a no-op (does not crash)
38. Indicators column shows SMA(20)/(50)/(200) values with `vs px` percentages; RSI(14) with regime label
39. RSI regime label is colored appropriately (oversold/overbought/neutral)
40. After 30s, the live price updates; SMA values stay constant but `vs px` percentages update to reflect new price
41. If quote repoll fails (simulate by disconnecting network briefly), header shows `[STALE]` indicator
42. Pressing `/` from drill-down opens modal; submitting new ticker replaces drill-down (back stack does not accumulate — Esc from new drill-down returns to home, not to old drill-down)
43. `Esc` returns to home screen
44. `?` shows updated help with new section
45. `t` cycles theme; drill-down recolors on next refresh
46. Entering nonexistent ticker `ZZZZNOTREAL`: drill-down shows "TICKER NOT FOUND" without crashing; quote polling is suppressed
47. Special tickers work: `/^VIX`, `/CL=F`, `/BRK.B` all produce valid drill-downs
48. All Session 3–7 features still work: watchlist polls, pulse polls, sector heatmap renders with gradient, sector deep-dive (`s`), correlation deep-dive (`c`)

### Regression (manual)

49. `python -m scripts.get_data -t AAPL -i 1d -s 2024-01-01 -e 2024-12-31` still works
50. `python -m scripts.run_backtest` still works
51. `python -m scripts.correlations -t AAPL MSFT NVDA` still works
52. `python visualization/view_backtest.py <existing_pickle>` still works

---

## 12. Architectural notes for execution

### Naming the field "name"

`TickerDetailSnapshot.name` is the friendly company name. Be careful not to collide with `dataclass`'s own machinery — `name` is fine as a field but worth noting if you write any introspection code.

### Why two builders, not one with a flag

`build_ticker_detail_snapshot(ticker, cfg, quote_only=True)` would be tempting but is wrong. The screen needs *different return shapes* for the two refresh paths (one returns a full snapshot, one returns just a Quote). Separate functions with distinct signatures keep the calling code clean and the intent explicit. This matches the workflow-as-source-of-truth principle.

### Why `_scroll_offset` lives on the screen, not the widget

The OHLC table widget is a pure renderer per the architecture. State (where we've scrolled to) belongs on the screen. The widget receives `(snapshot, offset)` and renders.

### Pop-then-push for `/` from within drill-down

Without pop-then-push, repeated `/` would build up a stack of drill-down screens, and `Esc` would walk back through all of them before reaching home. That's confusing. The Bloomberg model is: `/` always replaces the current drill-down. Implement it that way.

### Handling the name-from-yfinance leak cleanly

The architecture forbids source-specific code outside `marketdata/sources/`. The "longName" lookup is the one annoying exception. Two options:

- (a) Add a `get_ticker_name(ticker)` method to `MarketDataSource` and implement it on both sources. yfinance has it via `.info`; Schwab has it via instrument lookup. Clean but more surface area.
- (b) Just call `yfinance.Ticker(ticker).info.get("longName")` inside the workflow with a comment marking it as a known data-layer leak, justified by the cosmetic nature of the field.

**Prefer (a)** if it's quick (the new method can return `None` from Schwab's `is_available()`-guarded path). Fall back to (b) with a clear comment if (a) gets messy. Document whichever choice you made in the debrief.

### What "stuck" looks like in this session

- Textual modal screen lifecycle issue (e.g., focus not landing on input) → consult Textual docs; this is a well-trodden pattern
- yfinance returning unexpected shapes for special symbols → log the raw return and adjust; do not bypass the data layer to fix a one-off symbol
- Indicator math producing NaN where you didn't expect → check `min_periods` behavior in pandas rolling functions; the existing `calculate_sma`/`calculate_rsi` handle this correctly so use them, don't reimplement
- Layout breaking at 120×30 → adjust CSS heights/widths; do not block on aesthetic perfection. Log the issue for the polish session.

If you get stuck on anything else for more than 15 minutes, stop and write what you tried in the debrief — Eric will review at session 9 planning.

---

## 13. Debrief expectations

Produce `notes/session-8-debrief.md` with:

- New files created
- Modified files and what changed
- AC pass/fail table
- Decisions made on ambiguous points (especially: name-lookup approach a/b, any CSS adjustments)
- Anything that surprised you
- Anything you punted to the polish session (which is fine — write it down)
- Live-data snapshot from a real run: e.g., AAPL drill-down values at the moment of the test
- Known issues / open questions for next session

Match the structure of `notes/session-7-debrief.md`.

---

## 14. Definition of done

This session is done when:

- All 30 automated ACs pass via `python scripts/verify_session8.py`
- Eric can launch the cockpit, press `/`, type a ticker, see a full drill-down, scroll the OHLC table, and return to home
- Special symbols (`^VIX`, `CL=F`, `BRK.B`) all work
- No regression in Sessions 3–7 features
- The debrief is written
- Polish items observed during the session are noted but not addressed

The cockpit is now feature-complete for monitoring. The next session is a polish pass; the session after that is Schwab integration when authentication is ready.
