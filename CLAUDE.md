# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

projectAlgo is a Python algorithmic trading suite for fetching/caching market data, computing technical indicators, backtesting trading strategies, and visualizing results. It integrates with the Charles Schwab API for live account visibility and market data. All scripts are run from the project root using `python -m`.

A terminal-resident market monitoring dashboard (`cockpit/`) is built with [Textual](https://textual.textualize.io/) and runs on Python 3.14.

## Setup

```bash
conda create -n algo_env python=3.9
conda activate algo_env
pip install -r requirements.txt
```

> **Cockpit TUI** requires Python 3.14 (installed separately via Homebrew). Run `python3.14 -m scripts.cockpit` or ensure `python` resolves to 3.14 in your shell.

### Configuration

Project-wide settings live in `cockpit.toml` at the project root:

```toml
[data]
preferred_source = "yfinance"   # flip to "schwab" after completing OAuth
data_dir = "data/historical_data"
backtest_results_dir = "data/backtest_results"

[refresh]
interval_seconds = 30

[theme]
default = "claude-warm"   # or "blue-orange"

[logging]
level = "INFO"
```

`config/settings.py` (`Settings.load()`) reads this file. The default `DataService` instance is lazy-initialized via `marketdata.service.get_data_service()`.

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

# Run a backtest (all params have defaults; run --help for full list)
python -m scripts.run_backtest
python -m scripts.run_backtest -t AAPL -s 2023-01-01 -e 2025-01-01 -i 1d --fast-window 20 --slow-window 100
python -m scripts.run_backtest -t NVDA --source schwab

# Live account and market data (requires Schwab auth)
python -m scripts.account                  # balances + positions
python -m scripts.account --balances-only
python -m scripts.account --positions-only
python -m scripts.quote AAPL MSFT ISRG    # live quotes

# Static candlestick chart with indicators
python -m visualization.plot_static -t ISRG -s 2023-01-01 -e 2024-06-11 -i 1d --indicators "sma:20,50;rsi:14"

# Interactive stock viewer (Dash app)
python -m visualization.view_stock

# Backtest results dashboard
python visualization/view_backtest.py data/backtest_results/<results_file>.pkl

# Explore a saved backtest pickle
python -m scripts.inspect_pickle data/backtest_results/<results_file>.pkl

# Cockpit TUI — terminal market dashboard (mock data; Python 3.14 required)
python3.14 -m scripts.cockpit
```

There is no test suite or linter configured in this project.

## Architecture

Data flows in one direction: **marketdata → core → analysis/strategies → backtesting → visualization**.

`broker/` sits alongside and provides Schwab account ops and auth — it does NOT feed data directly; `marketdata/` owns all data fetching.

### Key Data Structures

- **`Stock`** (`core/security.py`): Passive data container — holds `ticker` and `historical_data`. Does NOT fetch data. Populate via `DataService.get_historical_ohlcv()`, then construct `Stock(ticker=..., historical_data=df)`.
- **`Quote`** (`core/quote.py`): Frozen dataclass for a live/delayed market quote. Has `price`, `bid`, `ask`, `volume`, `previous_close`, and computed `change`/`change_pct` properties.
- **`Transaction`** (`core/transaction.py`): Represents a single BUY or SELL with slippage-adjusted price, shares, cost basis, and realized P&L. Created by the backtester; serialized via `to_dict()` for dashboard display.
- **`Backtester`** (`backtesting/engine.py`): Runs a strategy against OHLCV data. Manages FIFO open positions, applies slippage in basis points, produces an equity curve (`pd.Series`) and `trades_df` (`pd.DataFrame`). Only handles simple long-only, one-position-at-a-time trading.
- **`BaseStrategy`** (`strategies/base_strategy.py`): Abstract base class. Concrete strategies must implement `calculate_indicator(self)` (mutates `self._data`) and `generate_signals(self)` (adds `self._data['signal']` with values 1=buy, -1=sell, 0=hold). The `get_strategy_data()` orchestration method is already implemented in the base class — do not override it.

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `marketdata/service.py` | **`DataService`** — unified entry point for all data needs. Handles cache lookup, source selection, and fallback. Use `get_data_service()` for the default instance. |
| `marketdata/cache.py` | **`LocalCache`** — CSV cache. Files named `{TICKER}_{interval}_{YYYYMMDD}_{YYYYMMDD}.csv`. |
| `marketdata/sources/yfinance_source.py` | **`YFinanceSource`** — yfinance integration; supports `1d`, `1wk`, `1mo`. |
| `marketdata/sources/schwab_source.py` | **`SchwabSource`** — Schwab integration; supports daily + intraday. `is_available()` returns False when unauthenticated. |
| `marketdata/sources/base.py` | **`MarketDataSource`** ABC — defines the interface all sources must implement. |
| `marketdata/exceptions.py` | `DataSourceError`, `SourceUnavailableError`, `UnsupportedIntervalError`. |
| `config/settings.py` | **`Settings`** — reads `cockpit.toml`. All path resolution is relative to project root. |
| `broker/schwab_client.py` | OAuth2 auth singleton. Reads credentials from env vars / `.env`. Call `is_authenticated()` before using live data. |
| `broker/account.py` | `get_account_summary()` returns positions/balances dict; `format_positions_table()` / `format_balances()` format for CLI. |
| `core/security.py` | Passive `Stock` dataclass. |
| `core/quote.py` | Frozen `Quote` dataclass. |
| `core/transaction.py` | `Transaction` class with `to_dict()`. |
| `analysis/technical_analysis.py` | Stateless functions: `calculate_sma`, `calculate_rsi`. Accept `pd.Series` or `pd.DataFrame`. |
| `analysis/performance_metrics.py` | Stateless functions for Sharpe, drawdown, win rate, profit factor, etc. Aggregated by `analyze_backtest_results()`. |
| `strategies/` | `BaseStrategy` ABC + concrete implementations (currently `SMACrossoverStrategy`). |
| `backtesting/engine.py` | `Backtester` class — event-driven simulation loop, FIFO position tracking, slippage. |
| `visualization/` | `plot_static.py` (mplfinance), `view_stock.py` (Dash), `view_backtest.py` (Dash dashboard). `indicator_plot_configs.py` maps indicator names → functions + plot panel assignments. |
| `scripts/` | CLI entry points — not importable as library code. |
| `cockpit/` | Textual TUI dashboard. `app.py` is the root `App`; `screens/` holds `HomeScreen` and `HelpScreen`; `widgets/` has reusable widgets; `mock_data.py` provides stubbed market data. |

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

### Backtest Results Bundle

`run_backtest.py` pickles a dict to `data/backtest_results/` with keys: `equity_curve`, `trades_df`, `processed_data` (OHLC + indicator + signal columns), `performance_metrics`, `strategy_name`, `initial_capital`, `slippage_bps`, `fast_window`, `slow_window`, `ticker_symbol`, `start_date`, `end_date`, `interval`.

## Adding a New Strategy

1. Create `strategies/your_strategy.py` subclassing `BaseStrategy`
2. Implement `calculate_indicator(self)` — compute and add indicator columns to `self._data`
3. Implement `generate_signals(self)` — set `self._data['signal']` (1, -1, 0)
4. Add an entry to `STRATEGY_REGISTRY` in `scripts/run_backtest.py`

## Adding a New Indicator

1. Add `calculate_<name>(data, window, column='Close')` to `analysis/technical_analysis.py`
2. Register it in `visualization/indicator_plot_configs.py` under `INDICATOR_PROPERTIES` with `func`, `plot_params` (panel, type), `ylabel_prefix`, and `column_name_format`
3. The backtest dashboard (`view_backtest.py`) detects indicator columns generically: columns starting with `RSI` go to an oscillator subplot; all others overlay on the price panel

## Market Analysis

```bash
# Pairwise return correlation matrix (terminal table)
python -m scripts.correlations -t AAPL MSFT NVDA GOOGL SPY

# With interactive heatmap in browser
python -m scripts.correlations -t AAPL MSFT SPY --plot

# Customise period, interval, and correlation method
python -m scripts.correlations -t AAPL MSFT SPY -s 2022-01-01 -e 2025-01-01 --interval 1wk --method spearman

# Print ranked pair list alongside the matrix
python -m scripts.correlations -t AAPL MSFT NVDA --pairs
```

`analysis/market_analysis.py` exposes three composable functions:
- `load_aligned_returns(tickers, start, end, ...)` — loads each ticker via `DataService`, aligns on common trading days (forward-fill then inner-join), returns a returns DataFrame
- `calculate_correlation_matrix(returns, method)` — wraps `DataFrame.corr()`; methods: `pearson`, `spearman`, `kendall`
- `summarize_correlations(corr)` — flattens the matrix to a sorted pair list (highest → lowest correlation)

`visualization/plot_correlation.py` — `plot_correlation_heatmap(corr)` renders an annotated Plotly heatmap (red → white → green, −1 to +1).

## Cockpit TUI

The cockpit is a Textual-based terminal dashboard (`cockpit/`) that monitors markets in real time (currently mock data only, live data in a future session).

### Package layout

```
cockpit/
  app.py            CockpitApp — root Textual App; theme registration + CSS var injection
  themes.py         THEMES_CONFIG dict + Theme objects for claude-warm and blue-orange
  mock_data.py      Hardcoded stub data; regenerate_mock() adds ±0.5% perturbations
  format.py         Pure formatting helpers: fmt_price, fmt_pct, make_sparkline, …
  styles.tcss       Textual stylesheet; uses CSS variables wired to the active theme
  screens/
    home.py         HomeScreen — 5-panel layout (account, pulse, watchlist, sectors, corr)
    help.py         HelpScreen — keyboard reference; Esc to return
  widgets/
    panel_frame.py  PanelFrame(Container) — border + title wrapper
    clock_header.py ClockHeader — ET time, ticks every second, shows market state
    command_footer.py CommandFooter — renders [KEY]LABEL pairs in the footer bar
    price_cell.py   PriceCell — flashes on price change, settles to directional color
    pct_cell.py     PctCell — same flash pattern as PriceCell
    sparkline.py    Sparkline — 8-level unicode block sparklines
```

### Themes

Two themes are registered: `claude-warm` (dark amber/orange) and `blue-orange`. Set the active theme in `cockpit.toml`:

```toml
[theme]
default = "claude-warm"   # or "blue-orange"
```

The `T` key cycles themes at runtime. `CockpitApp.get_css_variables()` is overridden to inject custom CSS variables (`$text-dim`, `$positive`, `$negative`, `$border`, etc.) before every stylesheet parse — this is required because Textual resolves CSS vars from the default theme during first parse, which doesn't include our custom vars.

### Keyboard bindings

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `R` | Refresh mock data |
| `?` | Help screen |
| `T` | Cycle theme |
| `Esc` | Back to previous screen |
| `Tab` / `Shift+Tab` | Focus next / previous panel |

### Adding a new theme

1. Add an entry to `THEMES_CONFIG` in `cockpit/themes.py` with all required color keys
2. The `_make_theme()` helper and `THEMES` dict will pick it up automatically
3. `THEME_NAMES` drives the `T`-key cycle order

## Known Limitations

- Intraday/sub-daily intervals do not source correctly from yfinance
- The backtest dashboard does not support intraday visualization
- Schwab does not support paper trading — live account commands affect a real account
- Schwab token files expire every 7 days and require re-running `scripts/schwab_auth.py`
- `preferred_source = "yfinance"` in `cockpit.toml` until Schwab OAuth is configured
