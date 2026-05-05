# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

projectAlgo is a Python algorithmic trading suite for fetching/caching market data, computing technical indicators, backtesting trading strategies, and visualizing results. All scripts are run from the project root using `python -m`.

## Setup

```bash
conda create -n algo_env python=3.9
conda activate algo_env
pip install pandas numpy yfinance mplfinance dash plotly pandas-ta
```

## Common Commands

All commands run from the project root:

```bash
# Download and cache historical data
python -m scripts.get_data -t AAPL MSFT -i 1d -s 2023-01-01 -e 2024-12-31 -o data/historical_data

# Run a backtest (configure parameters at top of scripts/run_backtest.py first)
python -m scripts.run_backtest

# Static candlestick chart with indicators
python -m visualization.plot_static -t ISRG -s 2023-01-01 -e 2024-06-11 -i 1d --indicators "sma:20,50;rsi:14"

# Interactive stock viewer (Dash app)
python -m visualization.view_stock

# Backtest results dashboard
python visualization/view_backtest.py data/backtest_results/<results_file>.pkl

# Explore a saved backtest pickle
python -m scripts.inspect_pickle data/backtest_results/<results_file>.pkl

# Run analysis example
python -m scripts.run_analysis
```

There is no test suite or linter configured in this project.

## Architecture

Data flows in one direction: **data_manager → core → analysis → strategies → backtesting → visualization**.

### Key Data Structures

- **`Stock`** (`core/financial_objects.py`): Wraps a ticker symbol and its `historical_data` DataFrame. Provides `download_data()` and `load_local_data()` — both require an explicit absolute `data_dir` path. Also has a `calculate_indicator()` convenience method (may be deprecated).
- **`Transaction`** (`core/financial_objects.py`): Represents a single BUY or SELL with slippage-adjusted price, shares, cost basis, and realized P&L. Created by the backtester and serialized via `to_dict()` for dashboard display.
- **`Backtester`** (`backtesting/engine.py`): Runs a strategy against OHLCV data. Manages FIFO open positions, applies slippage in basis points, and produces an equity curve (`pd.Series`) and a `trades_df` (`pd.DataFrame`). Only handles simple long-only, one-position-at-a-time trading.
- **`BaseStrategy`** (`strategies/base_strategy.py`): Abstract base class. Concrete strategies must implement `calculate_indicator(self)` (mutates `self._data`) and `generate_signals(self)` (adds `self._data['signal']` column with values 1=buy, -1=sell, 0=hold).

### Module Responsibilities

| Module | Responsibility |
|---|---|
| `data_manager/` | yfinance downloads + CSV read/write. Files named `{TICKER}_{interval}_{YYYYMMDD}_{YYYYMMDD}.csv` |
| `analysis/technical_analysis.py` | Stateless functions: `calculate_sma`, `calculate_rsi`. Accept `pd.Series` or `pd.DataFrame`. |
| `analysis/performance_metrics.py` | Stateless functions for Sharpe, drawdown, win rate, profit factor, etc. Aggregated by `analyze_backtest_results()`. |
| `strategies/` | `BaseStrategy` ABC + concrete implementations (currently `SMACrossoverStrategy`) |
| `backtesting/engine.py` | `Backtester` class — event-driven simulation loop, FIFO position tracking, slippage |
| `visualization/` | `plot_static.py` (mplfinance), `view_stock.py` (Dash), `view_backtest.py` (Dash dashboard); `indicator_plot_configs.py` maps indicator names to functions and plot panel assignments |
| `scripts/` | CLI entry points — not importable as library code |

### Backtest Results Bundle

`run_backtest.py` pickles a dict to `data/backtest_results/` with keys: `equity_curve`, `trades_df`, `processed_data` (OHLC + indicator + signal columns), `performance_metrics`, `strategy_name`, `initial_capital`, `slippage_bps`, `fast_window`, `slow_window`, `ticker_symbol`, `start_date`, `end_date`, `interval`.

## Adding a New Strategy

1. Create `strategies/your_strategy.py` subclassing `BaseStrategy`
2. Implement `calculate_indicator(self)` — compute and add indicator columns to `self._data`
3. Implement `generate_signals(self)` — set `self._data['signal']` (1, -1, 0)
4. Instantiate and configure in `scripts/run_backtest.py`

## Adding a New Indicator

1. Add `calculate_<name>(data, window, column='Close')` to `analysis/technical_analysis.py`
2. Register it in `visualization/indicator_plot_configs.py` under `INDICATOR_PROPERTIES` with `func`, `plot_params` (panel, type), `ylabel_prefix`, and `column_name_format`

## Known Limitations

- Intraday/sub-daily intervals do not source correctly from yfinance
- The backtest dashboard does not support intraday visualization
- `Stock.calculate_indicator()` is considered for deprecation; prefer calling indicator functions directly in strategy classes
