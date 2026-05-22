# DEVELOPER_NOTES.md

Implementation details for developers maintaining or extending projectAlgo.

---

## CLI Reference

### Data Management

```bash
python -m scripts.get_data -t AAPL MSFT -i 1d -s 2023-01-01 -e 2024-12-31
python -m scripts.get_data -t AAPL -i 1d -s 2023-01-01 -e 2024-12-31 --source schwab
```

**Flags:**
- `-t` / `--tickers`: Ticker symbols (required)
- `-i` / `--interval`: `1d`, `1wk`, `1mo` (default: `1d`)
- `-s` / `--start`: Start date `YYYY-MM-DD` (default: `2023-01-01`)
- `-e` / `--end`: End date `YYYY-MM-DD` (default: today)
- `--source`: `yfinance` or `schwab` (default: from `cockpit.toml`)

### Backtesting

```bash
python -m scripts.run_backtest
python -m scripts.run_backtest -t AAPL -s 2023-01-01 -e 2025-01-01 -i 1d --fast-window 20 --slow-window 100
python -m scripts.run_backtest -t NVDA --source schwab
```

See `--help` for full option list. Results pickle to `data/backtest_results/` with timestamped filename.

### Market Analysis

```bash
# Terminal correlation matrix
python -m scripts.correlations -t AAPL MSFT NVDA GOOGL SPY

# Interactive Plotly heatmap in browser
python -m scripts.correlations -t AAPL MSFT SPY --plot

# Customize period, interval, correlation method
python -m scripts.correlations -t AAPL MSFT SPY -s 2022-01-01 -e 2025-01-01 --interval 1wk --method spearman

# Include ranked pair list alongside matrix
python -m scripts.correlations -t AAPL MSFT NVDA --pairs
```

### Visualization

```bash
# Static candlestick + indicators
python -m visualization.plot_static -t ISRG -s 2023-01-01 -e 2024-06-11 -i 1d --indicators "sma:20,50;rsi:14"

# Interactive stock viewer (Dash)
python -m visualization.view_stock

# Backtest results dashboard (Dash)
python visualization/view_backtest.py data/backtest_results/<results_file>.pkl

# Inspect pickled backtest bundle
python -m scripts.inspect_pickle data/backtest_results/<results_file>.pkl
```

### Schwab Integration

```bash
# Initial OAuth setup
python -m scripts.schwab_auth   # opens browser; saves token to ~/.schwab_token.json

# Live account data
python -m scripts.account                  # balances + positions
python -m scripts.account --balances-only
python -m scripts.account --positions-only

# Live quotes
python -m scripts.quote AAPL MSFT ISRG
```

### Cockpit TUI

```bash
# Python 3.14 required (or Python 3.11+ with textual installed)
python3.14 -m scripts.cockpit
# or if using standard python with textual:
python -m scripts.cockpit
```

---

## Workflows

Located in `workflows/`. All are pure functions: no Textual imports, no asyncio.

### `build_watchlist_snapshot(watchlist_name, data_service=None)`

**Parameters:**
- `watchlist_name`: str — name from `watchlists.yaml`
- `data_service`: DataService — defaults to `get_data_service()`

**Returns:** `WatchlistSnapshot` with `name`, `tickers`, `quotes` (dict[ticker, Quote]), `failed_tickers`, `error`

**Example:**
```python
from workflows.watchlist_snapshot import build_watchlist_snapshot
snapshot = build_watchlist_snapshot("tech", data_service=service)
for ticker, quote in snapshot.quotes.items():
    print(f"{ticker}: ${quote.price:.2f} ({quote.change_pct:+.2f}%)")
```

### `build_pulse_snapshot(config, data_service=None)`

**Parameters:**
- `config`: PulseConfig dataclass with `tickers` list
- `data_service`: DataService — defaults to `get_data_service()`

**Returns:** `PulseSnapshot` with 8 `PulseTicker` objects (symbol, label, quote, sparkline, error)

**Config structure** (from `cockpit.toml` `[pulse]`):
```python
@dataclass
class PulseTicker:
    symbol: str
    label: str
    format: str  # "price" | "index" | "yield"
    refresh_interval_seconds: int
```

### `build_sector_snapshot(config, data_service=None)`

**Parameters:**
- `config`: SectorConfig with `lookback_days`, `comparison_ticker`, `intensity_max_pct`
- `data_service`: DataService — defaults to `get_data_service()`

**Returns:** `SectorSnapshot` with 12 `SectorCell` objects (11 SPDR ETFs + comparison ticker). Each cell has `ticker`, `rs_value`, `rs_path` (list of RS values over time), `error`.

**Constant:** `SPDR_SECTORS = ["XLK", "XLF", "XLV", "XLY", "XLC", "XLI", "XLP", "XLE", "XLU", "XLRE", "XLB"]`

### `build_multi_timeframe_sector_snapshot(config, data_service=None)`

**Parameters:**
- `config`: SectorDeepDiveConfig with timeframes, default sort column/direction
- `data_service`: DataService — defaults to `get_data_service()`

**Returns:** `MultiTimeframeSectorSnapshot` with 12 `SectorRow` objects, each containing `TimeframeRS` entries for each configured timeframe.

### `build_correlation_snapshot(tickers, lookback_days, method="pearson", data_service=None, now=None)`

**Parameters:**
- `tickers`: list[str] — ticker symbols
- `lookback_days`: int — lookback window
- `method`: str — "pearson", "spearman", or "kendall"
- `data_service`: DataService — defaults to `get_data_service()`
- `now`: datetime — for testing; defaults to today

**Returns:** `CorrelationSnapshot` with:
- `tickers`: requested tickers
- `requested_tickers`: input list
- `failed_tickers`: tickers that failed to fetch
- `method`: correlation method used
- `lookback_days`: effective lookback
- `matrix`: pandas DataFrame (NxN correlation matrix)
- `ranked_pairs`: list[RankedPair] sorted high→low
- `as_of`: datetime of snapshot
- `error`: string if overall failure

**Per-ticker failure handling:** If a ticker fails to fetch, it's skipped; `load_aligned_returns()` is called on survivors only. Gracefully handles special symbols like `^VIX`, `^TNX`, `DX-Y.NYB`.

**Calendar window sizing:** To handle sparse data (e.g., commodities), the fetch window is `lookback_days * 1.5 + 5` days (capped at 3×365). Data is truncated to exactly `lookback_days` rows before correlation computation.

---

## Cockpit Formatting Helpers

Located in `cockpit/format.py`.

### `fmt_price(price, symbol="") -> str`
Returns price formatted as `$XX.XX` or `X.XX` (no $) depending on symbol context.

### `fmt_pct(pct) -> str`
Returns percentage with sign: `+3.45%` or `-2.10%`.

### `fmt_rs_pct(rs_value) -> str`
Returns relative strength percentage: `+5.00%` or `-3.50%`.

### `make_sparkline(values, width=7) -> str`
Generates 8-level Unicode block sparkline: ▁▂▃▄▅▆▇█

### `relative_strength_to_color(rs_pct, theme) -> str`
Maps RS percentage to a Textual color code using theme gradient.

**Parameters:**
- `rs_pct`: float — relative strength as percentage (e.g., 5.0 for +5%)
- `theme`: dict — color dict from `cockpit/themes.py` with `gradient_positive`, `gradient_negative`, `gradient_neutral`

**Returns:** Textual color code string (e.g., `"#ff8c00"`)

### `correlation_to_color(rho, theme, intensity_max=1.0) -> str`
Maps correlation coefficient to a Textual color code using theme gradient.

**Parameters:**
- `rho`: float — correlation in range [-1, +1]
- `theme`: dict — color dict
- `intensity_max`: float — max intensity (default 1.0)

**Returns:** Textual color code string

### `_gradient_color(value, intensity_max, gradient_positive, gradient_negative, gradient_neutral) -> str`
Shared linear RGB interpolation helper. Maps a value (0 to ±intensity_max) to a smooth color gradient.

**Parameters:**
- `value`: float — the value to map
- `intensity_max`: float — the scale (values > intensity_max are clamped)
- `gradient_positive`: str — Textual color for positive values
- `gradient_negative`: str — Textual color for negative values
- `gradient_neutral`: str — Textual color for zero

**Returns:** Textual color code string

---

## Cockpit Widgets

### `CorrelationPanel`

**Location:** `cockpit/widgets/correlation_panel.py`

Renders lower-triangle + diagonal of a correlation matrix on the home screen.

**Methods:**
- `update_snapshot(snapshot: CorrelationSnapshot | None)` — updates the panel with new snapshot data
- `snapshot` property — getter/setter for the snapshot

**Display:**
- Cells show correlation value to 2 decimals
- Background color from `correlation_to_color()`
- Lower triangle only (upper triangle blank, diagonal shows 1.00)

**Example:**
```python
panel = CorrelationPanel(id="corr-panel")
snapshot = build_correlation_snapshot(["SPY", "QQQ"], 60)
panel.update_snapshot(snapshot)
```

### `CorrelationTable`

**Location:** `cockpit/widgets/correlation_table.py`

Renders full NxN correlation matrix for deep-dive screen. Rich-markup table rendering with scrolling.

**Methods:**
- `update_snapshot(snapshot: CorrelationSnapshot | None)` — updates table rows

### `RankedPairList`

**Location:** `cockpit/widgets/ranked_pair_list.py`

Renders ranked pair list (sorted high→low correlation) for deep-dive screen.

**Methods:**
- `update_snapshot(snapshot: CorrelationSnapshot | None)` — updates list items

**Display:**
- Pair label and correlation value
- Text color gradient from `correlation_to_color()`
- Sorted highest→lowest by correlation

---

## Cockpit Screens

### `CorrelationDeepDiveScreen`

**Location:** `cockpit/screens/correlations.py`

Full-screen correlation matrix + ranked pairs, with parameter cycling.

**Bindings:**
- `M` → `action_cycle_method()` — cycles Pearson → Spearman → Kendall
- `[` → `action_shrink_lookback()` — decrease lookback (min: `lookback_options[0]`)
- `]` → `action_grow_lookback()` — increase lookback (max: `lookback_options[-1]`)
- `P` → `action_cycle_preset()` — cycle ticker preset (cross_asset → sectors → mega_cap → ...)
- `R` → `action_refresh_now()` — force immediate refresh
- `Esc` → `action_app_pop_screen()` — back to home
- `Q` → `action_quit()` — quit app
- `T` → `action_cycle_theme()` — cycle theme

**Initialization:**
```python
screen = CorrelationDeepDiveScreen()
self.app.push_screen(screen)
```

**Config loading:** Config is loaded lazily in `on_mount()` because `self.app` is not available during `__init__`. A `_load_cfg()` method is called from both `on_mount` and the worker (with a `_cfg_loaded` guard).

---

## Configuration

### `cockpit.toml` structure

**Correlation sections:**

```toml
[correlations]
tickers = ["SPY", "QQQ", "IWM", "TLT", "GLD", "^VIX"]
lookback_days = 60
method = "pearson"  # "pearson" | "spearman" | "kendall"
refresh_interval_seconds = 300

[correlation_deep_dive]
default_preset = "cross_asset"  # "cross_asset" | "sectors" | "mega_cap"
default_method = "pearson"
default_lookback_days = 60
lookback_options = [10, 20, 60, 120, 252]
refresh_interval_seconds = 60

[correlation_deep_dive.presets.cross_asset]
tickers = ["SPY", "QQQ", "IWM", "TLT", "GLD", "^VIX"]

[correlation_deep_dive.presets.sectors]
tickers = ["XLK", "XLF", "XLV", "XLY", "XLC", "XLI", "XLP", "XLE", "XLU", "XLRE", "XLB"]

[correlation_deep_dive.presets.mega_cap]
tickers = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "TSLA", "META", "BERKB"]
```

### `config/settings.py` dataclasses

```python
@dataclass
class CorrelationConfig:
    tickers: list[str]
    lookback_days: int
    method: str  # "pearson" | "spearman" | "kendall"
    refresh_interval_seconds: int

@dataclass
class CorrelationDeepDiveConfig:
    presets: dict[str, list[str]]  # preset_name → tickers
    default_preset: str
    default_method: str
    default_lookback_days: int
    lookback_options: tuple[int, ...]
    refresh_interval_seconds: int
```

---

## Data Structures

### `workflows/correlation_snapshot.py`

```python
@dataclass(frozen=True)
class RankedPair:
    ticker_a: str
    ticker_b: str
    correlation: float

@dataclass(frozen=True)
class CorrelationSnapshot:
    tickers: list[str]
    requested_tickers: list[str]
    failed_tickers: list[str]
    method: str
    lookback_days: int
    matrix: pd.DataFrame  # NxN, indexed by ticker
    ranked_pairs: list[RankedPair]  # sorted high→low
    as_of: datetime
    error: str | None
```

---

## Themes

### Color palette structure

Each theme in `cockpit/themes.py` must define:

```python
THEME_COLORS = {
    "background": "#...",
    "surface": "#...",
    "primary": "#...",
    "secondary": "#...",
    "text-primary": "#...",
    "text-secondary": "#...",
    "text-dim": "#...",
    "border": "#...",
    "positive": "#...",  # up/green
    "negative": "#...",  # down/red
    "flash-up-bg": "#...",
    "flash-down-bg": "#...",
    "flash-text": "#...",
    "gradient_positive": "#...",  # for RS/correlation gradients (positive)
    "gradient_negative": "#...",  # for RS/correlation gradients (negative)
    "gradient_neutral": "#...",   # for RS/correlation gradients (zero)
}
```

---

## Key Constants

### `analysis/market_analysis.py`

No constants; helper functions only.

### `workflows/sector_snapshot.py`

```python
SPDR_SECTORS = [
    "XLK", "XLF", "XLV", "XLY", "XLC",
    "XLI", "XLP", "XLE", "XLU", "XLRE", "XLB"
]
```

---

## Testing

There is no automated test suite. Verification is done manually via:
1. CLI commands (see CLI Reference above)
2. Cockpit TUI interactive verification
3. Python REPL imports (e.g., `from workflows.correlation_snapshot import build_correlation_snapshot`)

For Session 7, verification script: `scripts/verify_session7.py` (31 automated acceptance criteria).

---

## Session 7 Changes Summary

**New files:**
- `workflows/correlation_snapshot.py` — pure data workflow
- `cockpit/widgets/correlation_panel.py` — home screen correlation panel
- `cockpit/widgets/correlation_table.py` — deep-dive correlation matrix
- `cockpit/widgets/ranked_pair_list.py` — deep-dive ranked pairs
- `cockpit/screens/correlations.py` — deep-dive screen with m/[/]/p bindings

**Modified files:**
- `config/settings.py` — added `CorrelationConfig`, `CorrelationDeepDiveConfig`, validation functions
- `cockpit.toml` — added `[correlations]` and `[correlation_deep_dive]` sections with 3 presets
- `cockpit/format.py` — added `_gradient_color()` shared helper, `correlation_to_color()` semantic wrapper
- `cockpit/screens/home.py` — wired `CorrelationPanel`, deleted `_refresh_mock_panels` entirely
- `cockpit/screens/help.py` — added `C` key binding documentation
- `cockpit/styles.tcss` — added CSS for correlation widgets and screen

**Deleted:**
- `_refresh_mock_panels()` method and all mock data infrastructure from home.py
