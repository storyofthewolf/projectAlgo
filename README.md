# projectAlgo

<img src="assets/logo.png" alt="Project Logo" width="200" title="projectAlgo Logo">

an algorithmic trading suite in python by storyofthewolf

feels the vibes!

---

## About The Project

A Python framework for collecting and managing historical market data, computing technical indicators, backtesting trading strategies, and visualizing results. While other resources exist, I find that one cannot really learn something unless you do it yourself. So here we go.

### Key Features

- Fetch and cache historical OHLCV data from Yahoo Finance
- Technical indicators: SMA, RSI (extensible)
- Event-driven backtesting engine with FIFO position tracking and configurable slippage
- Performance metrics: total return, annualized return, Sharpe ratio, max drawdown, win rate, profit factor
- Static candlestick + indicator plots via mplfinance
- Interactive browser-based stock viewer (Dash)
- Interactive backtest results dashboard (Dash) with equity curve, trade log, and performance summary

---

## Getting Started

### Prerequisites

- Python 3.9+
- Anaconda/Miniconda recommended
- Active internet connection for data downloads

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/storyofthewolf/projectAlgo.git
   cd projectAlgo
   ```

2. **Create and activate a Conda environment:**
   ```bash
   conda create -n algo_env python=3.9
   conda activate algo_env
   ```

3. **Install required packages:**
   ```bash
   pip install pandas numpy yfinance mplfinance dash plotly pandas-ta
   ```

---

## Usage

All commands are run from the project root.

### 1. Download Historical Data

Downloads data for one or more tickers and saves to CSV. Loads from local cache if already downloaded.

```bash
python -m scripts.get_data -t AAPL MSFT -i 1d -s 2023-01-01 -e 2024-12-31 -o data/historical_data
```

| Flag | Description | Default |
|------|-------------|---------|
| `-t` / `--tickers` | One or more ticker symbols | required |
| `-i` / `--interval` | Data interval (`1d`, `1wk`, `1h`, etc.) | `1d` |
| `-s` / `--start` | Start date `YYYY-MM-DD` | `2023-01-01` |
| `-e` / `--end` | End date `YYYY-MM-DD` | today |
| `-o` / `--output_dir` | Directory to save CSVs | `data/historical_data` |

### 2. Run a Backtest

Configure the backtest parameters at the top of `scripts/run_backtest.py` (ticker, dates, interval, capital, slippage, strategy windows), then run:

```bash
python -m scripts.run_backtest
```

Results are pickled to `data/backtest_results/` with a timestamped filename. The script loads local data first and downloads if not found.

**Configurable parameters in `run_backtest.py`:**
- `TICKER_SYMBOL`, `START_DATE`, `END_DATE`, `INTERVAL`
- `INITIAL_CAPITAL`, `SLIPPAGE_BPS`
- `FAST_WINDOW`, `SLOW_WINDOW` (SMA Crossover strategy)

### 3. Static Candlestick Plot

Produces a static mplfinance chart with optional overlaid indicators.

```bash
python -m visualization.plot_static -t ISRG -s 2023-01-01 -e 2024-06-11 -i 1d --indicators "sma:20,50,100;rsi:14,28"
```

Indicators are specified as `name:window1,window2;name:window`. Supported: `sma`, `rsi`.

### 4. Interactive Stock Viewer

Opens a Dash web app in your browser for exploring stock data interactively.

```bash
python -m visualization.view_stock
```

### 5. Backtest Results Dashboard

Opens a Dash dashboard to visualize a saved backtest. Pass the path to a `.pkl` results file:

```bash
python visualization/view_backtest.py data/backtest_results/<results_file>.pkl
```

The dashboard shows the equity curve, OHLC chart with strategy signals, trade log, and a full performance metrics summary.

---

## Architecture

```
data_manager/       — yfinance download + CSV read/write
core/               — Stock and Transaction data model
analysis/           — Stateless indicator and performance metric functions
strategies/         — BaseStrategy ABC + concrete strategy implementations
backtesting/        — Backtester engine (FIFO positions, slippage, equity curve)
visualization/      — Static plots and interactive Dash dashboards
scripts/            — CLI entry points
data/
  historical_data/  — Cached CSV files ({ticker}_{interval}_{start}_{end}.csv)
  backtest_results/ — Pickled backtest result bundles
```

### Adding a New Strategy

1. Create `strategies/your_strategy.py` subclassing `BaseStrategy`
2. Implement `calculate_indicator(self)` — add indicator columns to `self._data`
3. Implement `generate_signals(self)` — add `self._data['signal']` (1=buy, -1=sell, 0=hold)
4. Instantiate in `scripts/run_backtest.py`

---

## Known Issues

1. Downloading data for short timeframes and intraday intervals does not source correctly from yfinance.
2. The backtest dashboard does not support sub-daily (intraday) visualization.
