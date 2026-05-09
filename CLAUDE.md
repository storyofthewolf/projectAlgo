# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

projectAlgo is a Python algorithmic trading suite for fetching/caching market data, computing technical indicators, backtesting trading strategies, and visualizing results. It integrates with the Charles Schwab API for live account visibility and market data. All scripts are run from the project root using `python -m`.

## Setup

```bash
conda create -n algo_env python=3.9
conda activate algo_env
pip install -r requirements.txt
```

### Schwab API credentials

Copy `config/schwab_config.example.env` to `.env` and fill in your values, then authenticate once:

```bash
cp config/schwab_config.example.env .env
# Edit .env with your SCHWAB_APP_KEY and SCHWAB_APP_SECRET
python -m scripts.schwab_auth   # opens browser for OAuth login; saves token to ~/.schwab_token.json
```

The token file expires every 7 days — re-run `schwab_auth` when it does.

## Common Commands

All commands run from the project root:

```bash
# Download and cache historical data (yfinance by default; --source schwab also available)
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
python -m visualization.view_stock --data-dir /path/to/data/historical_data

# Backtest results dashboard
python visualization/view_backtest.py data/backtest_results/<results_file>.pkl

# Explore a saved backtest pickle
python -m scripts.inspect_pickle data/backtest_results/<results_file>.pkl
```

There is no test suite or linter configured in this project.

## Architecture

Data flows in one direction: **data_manager → core → analysis → strategies → backtesting → visualization**.

The `broker/` package sits alongside this pipeline and provides live data and account access via Schwab, feeding into `data_manager` as an optional source.

### Key Data Structures

- **`Stock`** (`core/financial_objects.py`): Wraps a ticker symbol and its `historical_data` DataFrame. `download_data()` and `load_local_data()` both require an explicit absolute `data_dir` path. `download_data()` accepts a `source` parameter (`'yfinance'` or `'schwab'`).
- **`Transaction`** (`core/financial_objects.py`): Represents a single BUY or SELL with slippage-adjusted price, shares, cost basis, and realized P&L. Created by the backtester; serialized via `to_dict()` for dashboard display.
- **`Backtester`** (`backtesting/engine.py`): Runs a strategy against OHLCV data. Manages FIFO open positions, applies slippage in basis points, produces an equity curve (`pd.Series`) and `trades_df` (`pd.DataFrame`). Only handles simple long-only, one-position-at-a-time trading.
- **`BaseStrategy`** (`strategies/base_strategy.py`): Abstract base class. Concrete strategies must implement `calculate_indicator(self)` (mutates `self._data`) and `generate_signals(self)` (adds `self._data['signal']` with values 1=buy, -1=sell, 0=hold). The `get_strategy_data()` orchestration method is already implemented in the base class — do not override it.

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `data_manager/` | yfinance downloads + Schwab fallback + CSV read/write. Files named `{TICKER}_{interval}_{YYYYMMDD}_{YYYYMMDD}.csv`. `get_historical_data()` accepts `source='yfinance'\|'schwab'`. |
| `broker/schwab_client.py` | OAuth2 auth singleton. Reads credentials from env vars / `.env`. Call `is_authenticated()` before using live data. |
| `broker/market_data.py` | `get_historical_ohlcv()` and `get_live_quotes()` from Schwab. Returns same DataFrame format as yfinance path. |
| `broker/account.py` | `get_account_summary()` returns positions/balances dict; `format_positions_table()` / `format_balances()` format for CLI. |
| `analysis/technical_analysis.py` | Stateless functions: `calculate_sma`, `calculate_rsi`. Accept `pd.Series` or `pd.DataFrame`. |
| `analysis/performance_metrics.py` | Stateless functions for Sharpe, drawdown, win rate, profit factor, etc. Aggregated by `analyze_backtest_results()`. |
| `strategies/` | `BaseStrategy` ABC + concrete implementations (currently `SMACrossoverStrategy`). |
| `backtesting/engine.py` | `Backtester` class — event-driven simulation loop, FIFO position tracking, slippage. |
| `visualization/` | `plot_static.py` (mplfinance), `view_stock.py` (Dash), `view_backtest.py` (Dash dashboard). `indicator_plot_configs.py` maps indicator names → functions + plot panel assignments. |
| `scripts/` | CLI entry points — not importable as library code. |

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

## Known Limitations

- Intraday/sub-daily intervals do not source correctly from yfinance
- The backtest dashboard does not support intraday visualization
- Schwab does not support paper trading — live account commands affect a real account
- Schwab token files expire every 7 days and require re-running `scripts/schwab_auth.py`
- `Stock.calculate_indicator()` is considered for deprecation; prefer calling indicator functions directly in strategy classes
