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
python -m scripts.cockpit
```

### Cache Maintenance

```bash
python -m scripts.clean_data   # remove stale or legacy cache files
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

**Per-ticker failure handling:** If a ticker fails to fetch, it's skipped; `load_aligned_returns()` is called on survivors only.

**Calendar window sizing:** Fetch window is `lookback_days * 1.5 + 5` days (capped at 3×365). Data is truncated to exactly `lookback_days` rows before correlation computation.

### `build_ticker_metrics(ticker, config, data_service=None)`

**Parameters:**
- `ticker`: str — symbol to compute metrics for
- `config`: TickerDetailConfig — SMA windows, RSI config, refresh interval
- `data_service`: DataService — defaults to `get_data_service()`

**Returns:** `TickerMetrics` with:
- `ticker`, `quote` (Quote | None)
- `high_52w`, `low_52w`, `range_position_pct` (0–100, where 100 = at 52W high)
- `sma_20`, `sma_50`, `sma_200` — last SMA values
- `pct_vs_sma_20/50/200` — signed % distance of current price from each SMA
- `rsi_14`, `rsi_regime` ("overbought" | "neutral" | "oversold")
- `rs_spy_1m` — 21-day cumulative RS vs SPY, in percent
- `as_of`, `error`

**Per-field failure tolerance:** Each computation is individually wrapped; a failure on one field leaves it `None` and continues. Only a total data failure sets `error`.

---

## Cockpit Formatting Helpers

Located in `cockpit/format.py`.

### `fmt_price(value) -> str`
Returns price formatted to 2 decimals: `187.42`. None → `—`.

### `fmt_price_display(value) -> str`
Returns price with dollar sign: `$187.42`. None → `—`.

### `fmt_pct(value) -> str`
Returns percentage with sign: `+3.45%` or `-2.10%`. None → `—`.

### `fmt_change(value) -> str`
Returns signed absolute change: `+1.23` or `-2.14`. None → `—`.

### `fmt_volume(value) -> str`
Returns compact volume: `42.1M`, `1.2B`, `987K`. None → `—`.

### `fmt_rs_pct(rs_value) -> str`
Returns relative strength percentage: `+5.00%` or `-3.50%`. Input is a decimal (0.05 → `+5.00%`).

### `make_sparkline(values, width=10) -> str`
Generates 8-level Unicode block sparkline: ▁▂▃▄▅▆▇█

### `relative_strength_to_color(rs_value, intensity_max_pct, gradient_positive, gradient_negative, gradient_neutral) -> str`
Maps RS decimal to a hex color via linear RGB interpolation.

### `correlation_to_color(rho, theme, intensity_max=1.0) -> str`
Maps correlation coefficient in [-1, +1] to a hex color from the theme gradient.

### `_gradient_color(value, intensity_max, gradient_positive, gradient_negative, gradient_neutral) -> str`
Shared linear RGB interpolation helper used by both RS and correlation coloring.

---

## Cockpit Widgets

### `CorrelationPanel`

**Location:** `cockpit/widgets/correlation_panel.py`

Renders lower-triangle + diagonal of a correlation matrix on the home screen.

**Methods:**
- `update_snapshot(snapshot: CorrelationSnapshot | None)` — updates the panel

**Display:** Lower triangle only (upper triangle blank, diagonal shows 1.00). Background color from `correlation_to_color()`.

### `CorrelationTable`

**Location:** `cockpit/widgets/correlation_table.py`

Renders full NxN correlation matrix for the deep-dive screen. Rich-markup table rendering with scrolling.

**Methods:**
- `update_snapshot(snapshot: CorrelationSnapshot | None)` — updates table rows

### `RankedPairList`

**Location:** `cockpit/widgets/ranked_pair_list.py`

Renders ranked pair list (sorted high→low correlation) for the deep-dive screen.

**Methods:**
- `update_snapshot(snapshot: CorrelationSnapshot | None)` — updates list items

### `TickerMetricsPanel`

**Location:** `cockpit/widgets/ticker_metrics_panel.py`

Two-column label/value panel for the ticker drill-down screen. Renders 11 scalar rows:
PRICE, CHANGE, VOLUME, 52W HIGH, 52W LOW, 52W RANGE, SMA 20, SMA 50, SMA 200, RSI(14), RS vs SPY 1M.
Wrapped in a `PanelFrame` with title `<TICKER> — METRICS`.

**Methods:**
- `update_metrics(metrics: TickerMetrics)` — re-renders from a snapshot

**Color rules:** signed values (CHANGE, SMA pct distance, RS) colored `$positive`/`$negative`. RSI regime: overbought=`$negative`, oversold=`$positive`, neutral=`$text-dim`. 52W RANGE is neutral-colored.

---

## Cockpit Screens

### `CorrelationDeepDiveScreen`

**Location:** `cockpit/screens/correlations.py`

Full-screen correlation matrix + ranked pairs, with parameter cycling.

**Bindings:**
- `M` → `action_cycle_method()` — cycles Pearson → Spearman → Kendall
- `[` → `action_shrink_lookback()` — decrease lookback
- `]` → `action_grow_lookback()` — increase lookback
- `P` → `action_cycle_preset()` — cycle ticker preset
- `R` → `action_refresh_now()` — force immediate refresh
- `Esc` → back to home
- `Q` → quit app

**Config loading:** Lazy in `on_mount()` because `self.app` is not available during `__init__`.

### `TickerDetailScreen`

**Location:** `cockpit/screens/ticker_detail.py`

Single-panel scalar metrics screen for a single ticker. Entered via `/` + ticker input.

**Bindings:** `Esc` back, `R` refresh, `/` find another ticker, `T` cycle theme, `?` help, `Q` quit.

**Composition:** `ClockHeader` + `TickerMetricsPanel` + `CommandFooter`.

**Worker:** `@work(exclusive=True, group="ticker_metrics", thread=True)` calls `build_ticker_metrics()`, updates via `call_from_thread`. Polls on `TickerDetailConfig.refresh_interval_seconds`.

---

## Configuration

### `cockpit.toml` structure

**Ticker detail section:**

```toml
[ticker_detail]
sma_windows = [20, 50, 200]
rsi_window = 14
rsi_oversold = 30
rsi_overbought = 70
refresh_interval_seconds = 30
```

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

[correlation_deep_dive.presets]
cross_asset = ["SPY", "QQQ", "IWM", "TLT", "GLD", "^VIX", "DX-Y.NYB", "CL=F"]
sectors = ["XLK", "XLF", "XLV", "XLY", "XLC", "XLI", "XLP", "XLE", "XLU", "XLRE", "XLB"]
mega_cap = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]
```

### `config/settings.py` dataclasses

```python
@dataclass(frozen=True)
class TickerDetailConfig:
    sma_windows: tuple           # default (20, 50, 200)
    rsi_window: int              # default 14
    rsi_oversold: float          # default 30.0
    rsi_overbought: float        # default 70.0
    refresh_interval_seconds: int  # default 30

@dataclass(frozen=True)
class CorrelationConfig:
    tickers: tuple[str, ...]
    lookback_days: int
    method: str  # "pearson" | "spearman" | "kendall"
    refresh_interval_seconds: int

@dataclass(frozen=True)
class CorrelationDeepDiveConfig:
    presets: dict[str, tuple[str, ...]]
    default_preset: str
    default_method: str
    default_lookback_days: int
    lookback_options: tuple[int, ...]
    refresh_interval_seconds: int
```

---

## Data Structures

### `workflows/ticker_metrics_snapshot.py`

```python
@dataclass(frozen=True)
class TickerMetrics:
    ticker: str
    quote: Quote | None
    high_52w: float | None
    low_52w: float | None
    range_position_pct: float | None  # 0-100, 100 = at 52W high
    sma_20: float | None
    sma_50: float | None
    sma_200: float | None
    pct_vs_sma_20: float | None       # signed %, price above SMA
    pct_vs_sma_50: float | None
    pct_vs_sma_200: float | None
    rsi_14: float | None
    rsi_regime: str | None            # "overbought" | "neutral" | "oversold"
    rs_spy_1m: float | None           # 21-day RS vs SPY, in percent
    as_of: datetime
    error: str | None = None
```

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

There is no automated test suite. Verification is done via:
1. CLI commands (see CLI Reference above)
2. Cockpit TUI interactive verification
3. Python REPL imports

Post-cleanup verifier: `python -m scripts.verify_session9` (10 import-tree checks).

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
