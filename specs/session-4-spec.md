# Session 4 Spec — Market Pulse Real-Data Wiring

**Goal:** Wire the market pulse panel to real data via DataService, following the exact pattern proven in Session 3 (watchlist). Eight configurable tickers in a 4×2 grid showing price/index/yield, change, and sparkline.

---

## Mandatory reads before coding

Read these files in full before writing any code:

1. `specs/ARCHITECTURE.md` — especially "Workflows orchestrate; UI renders" and the anti-patterns section
2. `specs/ROADMAP.md` — Session 4 description and owner context
3. `notes/session-3-debrief.md` — polling pattern, threading model, sparkline fix, flash bug
4. `cockpit/widgets/watchlist_panel.py` — the reference implementation for real-data panel wiring
5. `workflows/watchlist_snapshot.py` — the reference implementation for a workflow
6. `cockpit/format.py` — existing formatting helpers
7. `config/settings.py` — current Settings dataclass
8. `cockpit.toml` — current config file
9. `cockpit/screens/home.py` — current HomeScreen layout
10. `cockpit/app.py` — current app wiring

---

## Design decisions (already made — do not re-derive)

1. **Polling model:** Separate `@work(exclusive=True, thread=True)` worker for the pulse panel, independent from the watchlist worker. Each panel owns its own data lifecycle.
2. **Snapshot pattern:** `workflows/market_pulse_snapshot.py` returns a typed `PulseSnapshot` dataclass. The cockpit never calls DataService directly.
3. **Grid layout:** 4×2 grid. Top row: SPY, QQQ, IWM, VIX. Bottom row: 10Y, DXY, Oil, Gold.
4. **Three format types:** `price` (with `$`), `index` (no `$`), `yield` (value shown as `X.XXX%`, change in absolute terms).
5. **Configuration:** `[pulse]` section in `cockpit.toml` with explicit label + format per ticker.
6. **Sparkline:** 30-day daily bars, percentile normalization via `make_sparkline_percentile`. Cached within a calendar day (same as watchlist).
7. **First-flash fix:** Applied to `PriceCell` and `PctCell` as a prerequisite before building the pulse panel.

---

## cockpit.toml additions

Add this section to `cockpit.toml`. The `Settings` dataclass must parse it.

```toml
[pulse]
tickers = [
    { symbol = "SPY",       label = "S&P 500",    format = "price" },
    { symbol = "QQQ",       label = "NASDAQ",      format = "price" },
    { symbol = "IWM",       label = "Russell 2K",  format = "price" },
    { symbol = "^VIX",      label = "VIX",         format = "index" },
    { symbol = "^TNX",      label = "10Y Yield",   format = "yield" },
    { symbol = "DX-Y.NYB",  label = "Dollar",      format = "index" },
    { symbol = "CL=F",      label = "Oil",         format = "price" },
    { symbol = "GC=F",      label = "Gold",        format = "price" },
]
```

### Settings update

Add a `PulseTicker` dataclass and a `pulse_tickers: list[PulseTicker]` field to `Settings`:

```python
@dataclass(frozen=True)
class PulseTicker:
    symbol: str
    label: str
    format: str   # "price", "index", or "yield"
```

If the `[pulse]` section is missing from `cockpit.toml`, use the 8 defaults above as a hardcoded fallback in `Settings.load()`.

---

## File layout

### New files

| File | Responsibility |
|------|---------------|
| `workflows/market_pulse_snapshot.py` | `build_pulse_snapshot()` — fetches quotes + history for pulse tickers, returns `PulseSnapshot` |
| `cockpit/widgets/market_pulse_panel.py` | `MarketPulsePanel` widget — 4×2 grid of `PulseCell` widgets |

### Modified files

| File | What changes |
|------|-------------|
| `cockpit.toml` | Add `[pulse]` section |
| `config/settings.py` | Add `PulseTicker` dataclass, parse `[pulse]` section |
| `cockpit/format.py` | Add `fmt_yield()` helper |
| `cockpit/widgets/price_cell.py` | Fix first-flash bug |
| `cockpit/widgets/pct_cell.py` | Fix first-flash bug |
| `cockpit/screens/home.py` | Replace mock pulse Static with `MarketPulsePanel`; add pulse `@work` method and reactive |
| `cockpit/styles.tcss` | Add pulse panel CSS |
| `cockpit/screens/help.py` | No new bindings needed; verify pulse section in help if applicable |

### Files that stay as-is

- `workflows/watchlist_snapshot.py` — do not touch
- `cockpit/widgets/watchlist_panel.py` — do not touch
- `cockpit/watchlists/` — do not touch
- `marketdata/` — do not touch
- `core/` — do not touch
- `analysis/` — do not touch
- `strategies/`, `backtesting/`, `broker/`, `visualization/`, `scripts/` — do not touch

---

## Interface signatures

### PulseSnapshot (workflows/market_pulse_snapshot.py)

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class PulseTicker:
    """One ticker's data for the pulse panel."""
    symbol: str
    label: str
    format_type: str              # "price", "index", "yield"
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    previous_close: Optional[float] = None
    sparkline_values: list[float] = field(default_factory=list)
    error: Optional[str] = None

@dataclass
class PulseSnapshot:
    """Complete pulse panel state."""
    tickers: list[PulseTicker]
    quote_source: str             # e.g. "yfinance"
    timestamp: str                # ISO format
```

### build_pulse_snapshot()

```python
def build_pulse_snapshot(
    pulse_config: list,           # list of PulseTicker from Settings
    data_service,                 # DataService instance
    lookback_days: int = 30,
) -> PulseSnapshot:
```

**Behavior:**
- For each configured ticker: fetch a live quote via `data_service.get_live_quote()` and 30-day historical OHLCV via `data_service.get_historical_ohlcv()`.
- If a ticker fails (bad symbol, network error), populate `error` field instead of crashing. Other tickers still process.
- Historical close prices become `sparkline_values`.
- `quote_source` derived from the data service (same pattern as watchlist snapshot).
- **No Textual imports. No asyncio. Pure Python + pandas.**

### fmt_yield() (cockpit/format.py)

```python
def fmt_yield(value: Optional[float]) -> str:
    """Format a yield value as 'X.XXX%'. Returns em-dash for None."""
```

`^TNX` from yfinance returns values like `4.482` (meaning 4.482%). Display as `4.482%` with 3 decimal places.

### fmt_yield_change() (cockpit/format.py)

```python
def fmt_yield_change(change: Optional[float]) -> str:
    """Format yield change as signed absolute value: '+0.031' or '-0.042'. Returns em-dash for None."""
```

Yield changes are shown in absolute terms (basis-point scale), not as percent-of-percent.

---

## MarketPulsePanel widget design

### Layout

4×2 grid using Textual's `Grid` or `Horizontal`+`Vertical` containers. Each cell is a `PulseCell` composite widget containing:

```
┌─ S&P 500 ────────────┐
│ $548.23   +1.42       │
│ +0.26%    ▁▂▃▅▆▇▅▃   │
└───────────────────────┘
```

- Line 1: label (top-left), price (left-aligned), change (right-aligned)
- Line 2: change percent (left-aligned), sparkline (right-aligned)

For `yield` format, the cell looks like:

```
┌─ 10Y Yield ──────────┐
│ 4.482%    +0.031      │
│           ▁▂▃▅▆▇▅▃   │
└───────────────────────┘
```

- Line 1: label, yield value, absolute change
- Line 2: sparkline only (no percent-of-percent line)

For `index` format (VIX, DXY):

```
┌─ VIX ────────────────┐
│ 16.42     -0.83       │
│ -4.81%    ▁▂▃▅▆▇▅▃   │
└───────────────────────┘
```

Same as `price` but no `$` prefix.

### Color rules

- Price/value: neutral text color
- Change positive: `$positive` CSS variable (theme-aware)
- Change negative: `$negative` CSS variable (theme-aware)
- Change zero: `$text-dim`
- Error state: `$text-dim` with label + "—" for all values
- Sparkline: `$text-dim`

### Flash behavior

`PulseCell` uses `PriceCell` and `PctCell` internally for the price and change values, inheriting flash-on-change behavior. The first-flash fix ensures first load does not flash.

### Refresh

`MarketPulsePanel` exposes a method (e.g., `update_snapshot(snapshot: PulseSnapshot)`) called by `HomeScreen` when a new snapshot arrives. The panel iterates over its `PulseCell` children and updates each one.

### Status line

The panel's `PanelFrame` title or a status widget shows `PULSE · quotes: yfinance · HH:MM:SS ET` with a 1-second clock tick, same pattern as watchlist.

---

## HomeScreen wiring

### Reactive + worker pattern

Follow the exact Session 3 pattern:

```python
# In HomeScreen
pulse_snapshot: reactive[Optional[PulseSnapshot]] = reactive(None)

def on_mount(self):
    # ... existing watchlist setup ...
    self.set_interval(30, self.refresh_pulse)
    self.refresh_pulse()

@work(exclusive=True, thread=True)
def refresh_pulse(self):
    snapshot = build_pulse_snapshot(
        pulse_config=self.app.settings.pulse_tickers,
        data_service=get_data_service(),
    )
    self.app.call_from_thread(self._set_pulse_snapshot, snapshot)

def _set_pulse_snapshot(self, snapshot):
    self.pulse_snapshot = snapshot

def watch_pulse_snapshot(self, snapshot):
    if snapshot is not None:
        self.query_one(MarketPulsePanel).update_snapshot(snapshot)
```

The pulse worker and watchlist worker run on independent timers and do not block each other.

---

## First-flash bug fix

### PriceCell.update_price (cockpit/widgets/price_cell.py)

Current behavior: flashes on every update, including first load.

Fix: if `self._previous is None`, set `self._previous = new_value` and skip the flash. The first render shows the value with neutral formatting (no directional color). Directional color and flash activate on the second update when there is an actual previous value to compare against.

### PctCell.update_pct (cockpit/widgets/pct_cell.py)

Same fix as PriceCell.

---

## Acceptance criteria

### Data + workflow

1. `build_pulse_snapshot()` returns a `PulseSnapshot` with 8 `PulseTicker` entries when called with default config.
2. Each `PulseTicker` has `price`, `change`, `change_pct`, and `sparkline_values` populated from real yfinance data.
3. A bad ticker (e.g., `XXXXX`) in the pulse config produces a `PulseTicker` with `error` set and other tickers unaffected.
4. `workflows/market_pulse_snapshot.py` has zero Textual or asyncio imports (verify by AST inspection).
5. No direct yfinance or schwab imports in `workflows/` or `cockpit/` (data goes through DataService).

### Configuration

6. `cockpit.toml` has a `[pulse]` section with the 8 default tickers.
7. `Settings.load()` parses the pulse config into `settings.pulse_tickers` (list of `PulseTicker`).
8. Missing `[pulse]` section in `cockpit.toml` falls back to hardcoded defaults without error.

### Display

9. Pulse panel renders as a 4×2 grid on launch with real data visible within ~5 seconds.
10. SPY/QQQ/IWM show `$` prefix; VIX/DXY do not; 10Y shows `X.XXX%` format.
11. Change values are color-coded: green/positive color for up, red/negative color for down, dim for zero.
12. Each cell shows a sparkline from 30-day historical data.
13. Error tickers show label + em-dash placeholders, no crash.

### Polling + refresh

14. Auto-refresh fires every 30 seconds (from `cockpit.toml` `refresh.interval_seconds`).
15. `r` key triggers immediate pulse refresh (alongside watchlist refresh).
16. Pulse polling is independent of watchlist polling (separate `@work` methods).

### Flash behavior

17. First load does NOT flash any cells (first-flash fix verified).
18. Subsequent refreshes flash only cells whose values changed (within `1e-6` tolerance).

### Architecture compliance

19. HomeScreen does not import DataService or any `marketdata` module.
20. MarketPulsePanel does not import any workflow or data module.
21. `cockpit/widgets/market_pulse_panel.py` does not import `mock_data`.

---

## What to do if stuck

- **yfinance symbol doesn't work for ^VIX, ^TNX, CL=F, or GC=F:** Try `yf.download("^VIX", period="5d")` in a quick test script. If the caret or special chars cause issues, check if yfinance needs the symbol URL-encoded or if there's an alternate ticker. Do not change the cockpit.toml schema to work around it — fix the symbol mapping.
- **Grid layout doesn't fit at 120 columns:** Each cell needs ~28-30 chars. At 120 columns with borders and padding, 4 columns should work. If it's too tight, reduce sparkline length from the default to 12-15 characters. Do not switch to a different layout — make the grid work.
- **Textual Grid widget doesn't behave:** Textual's `Grid` container works but can be finicky with responsive sizing. Alternative: nest `Horizontal` inside `Vertical` (2 rows of 4 `Horizontal` containers). Pick whichever approach works cleanly.
- **`get_live_quote` returns None for futures/index symbols:** Fall back to using the last close price from historical data, same as the volume workaround in Session 3. Set `error` field to None (it's not really an error, just a data availability issue).
- **Flash fix breaks existing watchlist behavior:** The fix should be additive (guard clause at the top of the update method). If watchlist flash regresses, the guard condition is wrong — check that `_previous` is being set correctly on first call.

---

## Verification script

After implementation, run a quick script to verify the workflow independently of the TUI:

```python
"""Quick verification of pulse snapshot workflow."""
from config.settings import Settings
from marketdata.service import get_data_service
from workflows.market_pulse_snapshot import build_pulse_snapshot

settings = Settings.load()
service = get_data_service()
snapshot = build_pulse_snapshot(settings.pulse_tickers, service)

for t in snapshot.tickers:
    status = "OK" if t.error is None else f"ERROR: {t.error}"
    price_str = f"{t.price:.2f}" if t.price else "—"
    spark_len = len(t.sparkline_values)
    print(f"  {t.label:12s}  {t.symbol:10s}  {price_str:>10s}  sparkline_pts={spark_len}  {status}")

print(f"\nSource: {snapshot.quote_source}")
print(f"Timestamp: {snapshot.timestamp}")
```

All 8 tickers should show OK with non-empty sparkline data.
