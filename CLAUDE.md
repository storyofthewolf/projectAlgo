# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

projectAlgo is a Python market monitoring toolkit for fetching/caching market data, computing technical indicators, and running a terminal-resident dashboard. It integrates with the Charles Schwab API for live account visibility and market data. All scripts are run from the project root using `python -m`.

A terminal-resident market monitoring dashboard (`cockpit/`) is built with [Textual](https://textual.textualize.io/). The cockpit is a **viewer, not a doer** — read-only, no order placement.

## Setup

```bash
conda create -n algo_env python=3.11
conda activate algo_env
pip install -r requirements.txt
```

### Configuration

Project-wide settings live in `cockpit.toml` at the project root:

```toml
[data]
preferred_source = "yfinance"   # flip to "schwab" after completing OAuth
data_dir = "data/historical_data"

[refresh]
interval_seconds = 30

[theme]
default = "claude-warm"   # or "blue-orange"

[logging]
level = "INFO"

[sector_deep_dive]
refresh_interval_seconds = 60
default_sort_column = "1M"
default_sort_direction = "desc"
timeframes = [
    { label = "5D",  trading_days = 5 },
    { label = "1M",  trading_days = 21 },
    { label = "3M",  trading_days = 63 },
    { label = "YTD", calendar = "ytd" },
]

[sectors]
lookback_days = 20
comparison_ticker = "SPY"
intensity_max_pct = 5.0
refresh_interval_seconds = 300

[ticker_detail]
sma_windows = [20, 50, 200]
rsi_window = 14
rsi_oversold = 30
rsi_overbought = 70
refresh_interval_seconds = 30

[pulse]
tickers = [
    { symbol = "SPY",      label = "S&P 500",   format = "price" },
    { symbol = "QQQ",      label = "NASDAQ",     format = "price" },
    { symbol = "IWM",      label = "Russell 2K", format = "price" },
    { symbol = "^VIX",     label = "VIX",        format = "index" },
    { symbol = "^TNX",     label = "10Y Yield",  format = "yield" },
    { symbol = "DX-Y.NYB", label = "Dollar",     format = "index" },
    { symbol = "CL=F",     label = "Oil",        format = "price" },
    { symbol = "GC=F",     label = "Gold",       format = "price" },
]
```

`config/settings.py` (`Settings.load()`) reads this file. The default `DataService` instance is lazy-initialized via `marketdata.service.get_data_service()`.

Watchlists for the cockpit TUI are defined in `watchlists.yaml` at the project root. Each named list contains ticker symbols and optional display labels.

### Schwab API credentials

Copy `config/schwab_config.example.env` to `.env` and fill in your values, then authenticate once:

```bash
cp config/schwab_config.example.env .env
# Edit .env with your SCHWAB_APP_KEY and SCHWAB_APP_SECRET
python -m scripts.schwab_auth   # opens browser for OAuth login; saves token to ~/.schwab_token.json
```

The token file expires every 7 days — re-run `schwab_auth` when it does.
After OAuth is set up, flip `preferred_source = "schwab"` in `cockpit.toml`.

## Common Commands

All commands run from the project root:

```bash
# Download and cache historical data (uses preferred_source from cockpit.toml)
python -m scripts.get_data -t AAPL MSFT -i 1d -s 2023-01-01 -e 2024-12-31
python -m scripts.get_data -t AAPL -i 1d -s 2023-01-01 -e 2024-12-31 --source schwab

# Live account and market data (requires Schwab auth)
python -m scripts.account                  # balances + positions
python -m scripts.account --balances-only
python -m scripts.account --positions-only
python -m scripts.quote AAPL MSFT ISRG    # live quotes

# Cockpit TUI — live terminal market dashboard
python -m scripts.cockpit
```

There is no test suite or linter configured in this project.

## Architecture

Data flows in one direction: **marketdata → core → analysis → workflows → UI**.

```
UI / Views  (cockpit TUI, CLI scripts)
     ↓
Workflows   (pure data orchestration — no Textual, no asyncio)
     ↓
Analysis    (stateless computation)
     ↓
Domain Models  (Stock, Quote — passive containers)
     ↓
Data Layer  (DataService + MarketDataSource implementations)
     ↓
Sources  (yfinance, Schwab)
```

`broker/` sits alongside and provides Schwab account ops and auth — it does NOT feed data directly; `marketdata/` owns all data fetching.

### Key Data Structures

- **`Stock`** (`core/security.py`): Passive data container — holds `ticker` and `historical_data`. Does NOT fetch data. Populate via `DataService.get_historical_ohlcv()`, then construct `Stock(ticker=..., historical_data=df)`.
- **`Quote`** (`core/quote.py`): Frozen dataclass for a live/delayed market quote. Has `price`, `bid`, `ask`, `volume`, `previous_close`, and computed `change`/`change_pct` properties.
- **`TickerMetrics`** (`workflows/ticker_metrics_snapshot.py`): Frozen dataclass with scalar metrics for a single ticker: quote, 52W range, SMA values and % distance, RSI, RS vs SPY. Returned by `build_ticker_metrics()`.

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `marketdata/service.py` | **`DataService`** — unified entry point for all data needs. Handles cache lookup, source selection, and fallback. Use `get_data_service()` for the default instance. |
| `marketdata/cache.py` | **`LocalCache`** — CSV cache, one canonical file per ticker+interval (`{TICKER}_{interval}.csv`). `get()` serves any sub-window the stored file covers; `put()` merges new data, widening the stored range. |
| `marketdata/sources/yfinance_source.py` | **`YFinanceSource`** — yfinance integration; supports `1d`, `1wk`, `1mo`. |
| `marketdata/sources/schwab_source.py` | **`SchwabSource`** — Schwab integration; supports daily + intraday. `is_available()` returns False when unauthenticated. |
| `marketdata/sources/base.py` | **`MarketDataSource`** ABC — defines the interface all sources must implement. |
| `marketdata/exceptions.py` | `DataSourceError`, `SourceUnavailableError`, `UnsupportedIntervalError`. |
| `config/settings.py` | **`Settings`** — reads `cockpit.toml`. Exposes `sector_config`, `sector_deep_dive_config`, `pulse_tickers`, `correlation_config`, `correlation_deep_dive_config`, `ticker_detail_config`. All path resolution is relative to project root. |
| `broker/schwab_client.py` | OAuth2 auth singleton. Reads credentials from env vars / `.env`. Call `is_authenticated()` before using live data. |
| `broker/account.py` | `get_account_summary()` returns positions/balances dict; `format_positions_table()` / `format_balances()` format for CLI. |
| `core/security.py` | Passive `Stock` dataclass. |
| `core/quote.py` | Frozen `Quote` dataclass. |
| `analysis/technical_analysis.py` | Stateless functions: `calculate_sma`, `calculate_rsi`. Accept `pd.Series` or `pd.DataFrame`. |
| `analysis/market_analysis.py` | `load_aligned_returns()`, `calculate_relative_strength()`, `calculate_correlation_matrix()`, `summarize_correlations()`. |
| `scripts/` | CLI entry points — not importable as library code. |
| `workflows/watchlist_snapshot.py` | `WatchlistSnapshot`, `build_watchlist_snapshot()` — live quotes for a named watchlist. |
| `workflows/market_pulse_snapshot.py` | `PulseSnapshot`, `PulseTicker`, `build_pulse_snapshot()` — quotes + sparklines for the 8 pulse tickers. |
| `workflows/sector_snapshot.py` | `SectorSnapshot`, `SectorCell`, `build_sector_snapshot()`, `SPDR_SECTORS` — RS vs SPY for 11 SPDR ETFs. |
| `workflows/multi_timeframe_sector_snapshot.py` | `MultiTimeframeSectorSnapshot`, `SectorRow`, `TimeframeRS`, `build_multi_timeframe_sector_snapshot()` — RS across configurable timeframes. |
| `workflows/correlation_snapshot.py` | `CorrelationSnapshot`, `RankedPair`, `build_correlation_snapshot()` — pairwise correlation matrix with per-ticker failure tolerance. |
| `workflows/ticker_metrics_snapshot.py` | `TickerMetrics`, `build_ticker_metrics()` — scalar metrics for the ticker drill-down screen. |
| `cockpit/app.py` | `CockpitApp` — root Textual App; theme registration + CSS var injection. |
| `cockpit/screens/home.py` | `HomeScreen` — 5-panel layout (account, pulse, watchlist, sectors, correlations). |
| `cockpit/screens/sectors.py` | `SectorDeepDiveScreen` — multi-timeframe RS table; entered via `S`, exits via Esc. |
| `cockpit/screens/correlations.py` | `CorrelationDeepDiveScreen` — full NxN correlation matrix + ranked pairs; entered via `C`, exits via Esc. |
| `cockpit/screens/ticker_detail.py` | `TickerDetailScreen` — scalar metrics panel for a single ticker; entered via `/`, exits via Esc. |
| `cockpit/screens/help.py` | `HelpScreen` — keyboard reference; Esc to return. |
| `cockpit/widgets/watchlist_panel.py` | `WatchlistPanel`, `WatchlistRow` — live quotes with PriceCell flash. |
| `cockpit/widgets/market_pulse_panel.py` | `MarketPulsePanel`, `PulseCell` — 4×2 grid; three display formats (price/$, index, yield/3dp%). |
| `cockpit/widgets/sector_panel.py` | `SectorPanel`, `SectorCell` — single-row strip of 12 cells; continuous-gradient backgrounds by RS value. |
| `cockpit/widgets/sector_table.py` | `SectorTable` — Rich-markup table; column focus, sort arrows, gradient cells. |
| `cockpit/widgets/correlation_panel.py` | `CorrelationPanel` — home screen lower-triangle + diagonal matrix, gradient cells. |
| `cockpit/widgets/correlation_table.py` | `CorrelationTable` — deep-dive full NxN matrix, Rich-markup rendering. |
| `cockpit/widgets/ranked_pair_list.py` | `RankedPairList` — deep-dive right panel, pairs ranked high→low, text-color gradient. |
| `cockpit/widgets/ticker_metrics_panel.py` | `TickerMetricsPanel` — two-column scalar metrics panel for the ticker drill-down. |
| `cockpit/widgets/panel_frame.py` | `PanelFrame(Container)` — border + title wrapper. |
| `cockpit/widgets/price_cell.py` | `PriceCell` — flashes on price change, settles to directional color. |
| `cockpit/widgets/pct_cell.py` | `PctCell` — same flash pattern as PriceCell. |
| `cockpit/widgets/sparkline.py` | `Sparkline` — 8-level unicode block sparklines. |
| `cockpit/watchlists/` | YAML and Schwab watchlist providers (`yaml_provider.py`, `schwab_provider.py`). |

### Canonical data fetch pattern

```python
from datetime import date
from marketdata.service import get_data_service
from core.security import Stock

service = get_data_service()
df = service.get_historical_ohlcv("AAPL", date(2023,1,1), date(2024,12,31), interval="1d")
stock = Stock(ticker="AAPL", historical_data=df)
```

### DataService fallback logic

When no `source` is explicitly requested, `DataService._select_source()`:
1. Tries `settings.preferred_source` (from `cockpit.toml`).
2. If the preferred source doesn't support the interval → falls back to the other.
3. If the preferred source is unavailable (e.g. Schwab token expired) → logs a warning and falls back to the other.

## Market Analysis

`analysis/market_analysis.py` exposes composable library functions (no CLI — the CLI was removed in Session 9):
- `load_aligned_returns(tickers, start, end, interval, data_service=None)` — loads each ticker via `DataService`, aligns on common trading days (forward-fill then inner-join), returns a returns DataFrame. Accepts `str` or `date` objects for `start`/`end`.
- `calculate_relative_strength(sector_returns, benchmark_returns, lookback_days)` — returns `(float, list[float])`: terminal RS value and the RS path. Raises `ValueError` if insufficient data.
- `calculate_correlation_matrix(returns, method)` — wraps `DataFrame.corr()`; methods: `pearson`, `spearman`, `kendall`
- `summarize_correlations(corr)` — flattens the matrix to a sorted pair list (highest → lowest correlation)

## Cockpit TUI

The cockpit is a Textual-based terminal dashboard (`cockpit/`) that monitors markets live using yfinance data.

### Cockpit workflow pattern

All five home-screen panels follow the same template established in Sessions 3-4:

```
workflow function (pure data, no Textual)
    → HomeScreen reactive variable
    → @work(exclusive=True, group="group_name", thread=True) worker calls workflow, then call_from_thread(_set_var)
    → watch_<var>() reactive handler
    → panel widget .update_snapshot() / .update_metrics()
    → independent set_interval() timer for polling cadence
```

Workflows in `workflows/` are pure functions: no Textual imports, no asyncio. They take a config object and an optional `data_service` parameter (defaults to `get_data_service()` internally). Each panel has its own polling timer and exclusive worker group — timers run independently. Screens and widgets never import from `marketdata/` directly.

### Package layout

```
cockpit/
  app.py              CockpitApp — root Textual App; theme registration + CSS var injection
  themes.py           THEMES_CONFIG dict + Theme objects for claude-warm and blue-orange
  format.py           Pure formatting helpers: fmt_price, fmt_pct, fmt_volume, fmt_change,
                      make_sparkline, relative_strength_to_color, correlation_to_color, _gradient_color
  styles.tcss         Textual stylesheet; uses CSS variables wired to the active theme
  screens/
    home.py           HomeScreen — 5-panel layout (account, pulse, watchlist, sectors, corr)
    sectors.py        SectorDeepDiveScreen — multi-timeframe RS table; S → enter, Esc → back
    correlations.py   CorrelationDeepDiveScreen — full NxN matrix + ranked pairs; C → enter, Esc → back
    ticker_finder_modal.py  TickerFinderModal — "/" input modal
    ticker_detail.py  TickerDetailScreen — scalar metrics panel; / + ticker → enter, Esc → back
    help.py           HelpScreen — keyboard reference; Esc to return
  widgets/
    panel_frame.py    PanelFrame(Container) — border + title wrapper
    clock_header.py   ClockHeader — ET time, ticks every second, shows market state
    command_footer.py CommandFooter — renders [KEY]LABEL pairs in the footer bar
    price_cell.py     PriceCell — flashes on price change, settles to directional color
    pct_cell.py       PctCell — same flash pattern as PriceCell
    sparkline.py      Sparkline — 8-level unicode block sparklines
    watchlist_panel.py  WatchlistPanel, WatchlistRow — live quotes, hot-reload from watchlists.yaml
    market_pulse_panel.py  MarketPulsePanel, PulseCell — 4×2 grid; price/index/yield formats
    sector_panel.py   SectorPanel, SectorCell — single-row strip; gradient backgrounds by RS
    sector_table.py   SectorTable — Rich-markup table; column focus, sort, gradient cells
    correlation_panel.py  CorrelationPanel — home screen lower-triangle + diagonal matrix, gradient cells
    correlation_table.py  CorrelationTable — deep-dive full NxN matrix, Rich-markup rendering
    ranked_pair_list.py  RankedPairList — deep-dive right panel, pairs ranked high→low, text-color gradient
    ticker_metrics_panel.py  TickerMetricsPanel — two-column scalar metrics: price, change, volume,
                              52W range, SMA 20/50/200, RSI(14), RS vs SPY 1M
  watchlists/
    yaml_provider.py  Loads watchlists.yaml; hot-reloaded on R
    schwab_provider.py  Schwab watchlist provider (deferred until OAuth)
```

### Live panels and their refresh cadences

| Panel | Data | Cadence |
|-------|------|---------|
| Market pulse (4×2 grid) | 8 tickers: SPY, QQQ, IWM, VIX, 10Y, DXY, Oil, Gold | 30s |
| Watchlist | Configurable via `watchlists.yaml`; cycle with `W` | 30s |
| Sector strip | 11 SPDR ETFs RS vs SPY; single-row gradient cells | 5 min |
| Sector deep-dive (on `S`) | 12 rows × N timeframes; SPY pinned at top | 60s |
| Correlations (home + deep-dive on `C`) | Configurable ticker list, method (Pearson/Spearman/Kendall), lookback | 5 min (home); 60s (deep-dive) |
| Ticker drill-down (on `/`) | Single ticker scalar metrics panel | 30s |

### Themes

Two themes are registered: `claude-warm` (dark amber/orange) and `blue-orange`. Set the active theme in `cockpit.toml`:

```toml
[theme]
default = "claude-warm"   # or "blue-orange"
```

The `T` key cycles themes at runtime. `CockpitApp.get_css_variables()` is overridden to inject custom CSS variables (`$text-dim`, `$positive`, `$negative`, `$border`, `$gradient-positive`, `$gradient-negative`, `$gradient-neutral`, etc.) before every stylesheet parse — required because Textual resolves CSS vars from the default theme during first parse, which doesn't include our custom vars.

### Keyboard bindings

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `R` | Refresh data + reload config and watchlists |
| `?` | Help screen |
| `T` | Cycle theme |
| `W` | Cycle watchlist |
| `/` | Open ticker finder (drill-down to scalar metrics panel) |
| `S` | Open sector deep-dive screen |
| `C` | Open correlation deep-dive screen |
| `Esc` | Back to previous screen |
| `Tab` / `Shift+Tab` | Focus next / previous panel |

In sector deep-dive screen:

| Key | Action |
|-----|--------|
| `← →` | Move column focus |
| `Enter` | Sort by focused column (toggle asc/desc) |
| `R` | Refresh data |
| `Esc` | Back to home |

In correlation deep-dive screen:

| Key | Action |
|-----|--------|
| `M` | Cycle method (Pearson → Spearman → Kendall) |
| `[` / `]` | Decrease / increase lookback window |
| `P` | Cycle ticker preset |
| `R` | Refresh data |
| `Esc` | Back to home |

In ticker drill-down screen:

| Key | Action |
|-----|--------|
| `R` | Refresh data |
| `/` | Find another ticker |
| `T` | Cycle theme |
| `?` | Help |
| `Esc` | Back to home |

### Adding a new theme

1. Add an entry to `THEMES_CONFIG` in `cockpit/themes.py` with all required color keys (including `gradient_positive`, `gradient_negative`, `gradient_neutral`)
2. The `_make_theme()` helper and `THEMES` dict will pick it up automatically
3. `THEME_NAMES` drives the `T`-key cycle order

### Adding a new live panel

Follow the established workflow pattern:
1. Create `workflows/your_snapshot.py` — pure function, no Textual/asyncio, accepts `data_service=None`
2. Add a `your_snapshot: reactive[YourSnapshot | None] = reactive(None)` to `HomeScreen`
3. Add a `@work(exclusive=True, group="your_group", thread=True) def refresh_your()` that calls the workflow and uses `call_from_thread` to set the reactive
4. Call `self.refresh_your()` in `on_mount` and wire a `set_interval` for the polling cadence
5. Add `watch_your_snapshot()` that calls a render method on the panel widget
6. The panel widget receives a typed snapshot object — it never imports from `marketdata/`

## Known Limitations

- Intraday/sub-daily intervals do not source correctly from yfinance
- Schwab does not support paper trading — live account commands affect a real account
- Schwab token files expire every 7 days and require re-running `scripts/schwab_auth.py`
- `preferred_source = "yfinance"` in `cockpit.toml` until Schwab OAuth is configured
- Sector and correlation cell gradient colors update on the next polling refresh after a theme change, not immediately
