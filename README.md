# projectAlgo

<img src="assets/logo.png" alt="Project Logo" width="200" title="projectAlgo Logo">

an algorithmic trading suite in python by storyofthewolf

feels the vibes!

---

## About The Project

A Python framework for collecting and managing historical market data, computing technical indicators, backtesting trading strategies, and visualizing results. Integrates with the Charles Schwab API for live account data and quotes. Includes a terminal-resident market monitoring dashboard built with Textual.

### Key Features

- Fetch and cache historical OHLCV data from Yahoo Finance or Charles Schwab
- Live account balances, positions, and quotes via Schwab API
- Technical indicators: SMA, RSI (extensible)
- Event-driven backtesting engine with FIFO position tracking and configurable slippage
- Performance metrics: total return, annualized return, Sharpe ratio, max drawdown, win rate, profit factor
- Pairwise correlation analysis with terminal table and interactive Plotly heatmap
- Static candlestick + indicator plots via mplfinance
- Interactive browser-based stock viewer (Dash)
- Interactive backtest results dashboard (Dash) with equity curve, trade log, and performance summary
- **Cockpit TUI** — terminal market dashboard with real-time-style market pulse, watchlist, sector heatmap, and correlation matrix

---

## Getting Started

### Prerequisites

- Python 3.9+ (analysis, backtesting, visualization)
- Python 3.14 (cockpit TUI — install separately via Homebrew)
- Anaconda/Miniconda recommended for the 3.9 environment
- Active internet connection for data downloads

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/storyofthewolf/projectAlgo.git
   cd projectAlgo
   ```

2. **Create and activate a Conda environment (Python 3.9):**
   ```bash
   conda create -n algo_env python=3.9
   conda activate algo_env
   pip install -r requirements.txt
   ```

3. **Install Python 3.14 for the cockpit TUI (macOS):**
   ```bash
   brew install python@3.14
   pip3.14 install textual tomli --break-system-packages
   ```

4. **Configure settings** in `cockpit.toml` at the project root (created automatically with defaults).

---

## Configuration

Project-wide settings live in `cockpit.toml`:

```toml
[data]
preferred_source = "yfinance"   # flip to "schwab" after completing OAuth
data_dir = "data/historical_data"
backtest_results_dir = "data/backtest_results"

[theme]
default = "claude-warm"   # or "blue-orange"
```

### Schwab API (optional)

Copy the example env file, fill in your app credentials, then authenticate:

```bash
cp config/schwab_config.example.env .env
# Edit .env with SCHWAB_APP_KEY and SCHWAB_APP_SECRET
python -m scripts.schwab_auth   # opens browser; saves token to ~/.schwab_token.json
```

After OAuth completes, flip `preferred_source = "schwab"` in `cockpit.toml`. The token expires every 7 days — re-run `schwab_auth` when it does.

---

## Usage

All commands run from the project root.

### 1. Download Historical Data

```bash
python -m scripts.get_data -t AAPL MSFT -i 1d -s 2023-01-01 -e 2024-12-31
python -m scripts.get_data -t AAPL -i 1d -s 2023-01-01 -e 2024-12-31 --source schwab
```

| Flag | Description | Default |
|------|-------------|---------|
| `-t` / `--tickers` | One or more ticker symbols | required |
| `-i` / `--interval` | Data interval (`1d`, `1wk`, `1mo`) | `1d` |
| `-s` / `--start` | Start date `YYYY-MM-DD` | `2023-01-01` |
| `-e` / `--end` | End date `YYYY-MM-DD` | today |
| `--source` | Data source (`yfinance`, `schwab`) | from `cockpit.toml` |

Data is cached as CSV in `data/historical_data/` and reused on subsequent runs.

### 2. Run a Backtest

```bash
python -m scripts.run_backtest
python -m scripts.run_backtest -t AAPL -s 2023-01-01 -e 2025-01-01 -i 1d --fast-window 20 --slow-window 100
```

Results are pickled to `data/backtest_results/` with a timestamped filename.

Run `python -m scripts.run_backtest --help` for all options.

### 3. Live Account & Quotes (requires Schwab auth)

```bash
python -m scripts.account                  # balances + positions
python -m scripts.account --balances-only
python -m scripts.account --positions-only
python -m scripts.quote AAPL MSFT ISRG    # live quotes
```

### 4. Correlation Analysis

```bash
# Terminal correlation matrix
python -m scripts.correlations -t AAPL MSFT NVDA GOOGL SPY

# With interactive heatmap in browser
python -m scripts.correlations -t AAPL MSFT SPY --plot

# Customize period, interval, and method
python -m scripts.correlations -t AAPL MSFT SPY -s 2022-01-01 -e 2025-01-01 --interval 1wk --method spearman

# Include ranked pair list
python -m scripts.correlations -t AAPL MSFT NVDA --pairs
```

### 5. Static Candlestick Plot

```bash
python -m visualization.plot_static -t ISRG -s 2023-01-01 -e 2024-06-11 -i 1d --indicators "sma:20,50;rsi:14"
```

Indicators: `sma`, `rsi`. Specify as `name:window1,window2;name:window`.

### 6. Interactive Stock Viewer

```bash
python -m visualization.view_stock
```

### 7. Backtest Results Dashboard

```bash
python visualization/view_backtest.py data/backtest_results/<results_file>.pkl
```

Shows equity curve, OHLC chart with signals, trade log, and full performance metrics.

### 8. Cockpit TUI

Terminal market dashboard. Requires Python 3.14.

```bash
python3.14 -m scripts.cockpit
```

Minimum terminal size: 120×30. Keyboard shortcuts:

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `R` | Refresh data |
| `?` | Help |
| `T` | Cycle theme |
| `Esc` | Back |
| `Tab` / `Shift+Tab` | Navigate panels |

---

## Architecture

```
marketdata/         — DataService: unified data fetch, cache, and source fallback
  sources/          — YFinanceSource, SchwabSource (MarketDataSource ABC)
  cache.py          — LocalCache: CSV read/write ({ticker}_{interval}_{start}_{end}.csv)
broker/             — Schwab OAuth client, account summary, live quote wrappers
core/               — Stock (passive dataclass), Quote, Transaction data models
analysis/           — Stateless indicator and performance metric functions
  market_analysis.py — load_aligned_returns, correlation matrix, pair summaries
strategies/         — BaseStrategy ABC + SMACrossoverStrategy
backtesting/        — Backtester engine (FIFO positions, slippage, equity curve)
visualization/      — plot_static (mplfinance), view_stock (Dash), view_backtest (Dash),
                      plot_correlation (Plotly heatmap)
cockpit/            — Textual TUI dashboard
  screens/          — HomeScreen (5 panels), HelpScreen
  widgets/          — ClockHeader, CommandFooter, PanelFrame, PriceCell, PctCell, Sparkline
config/             — Settings dataclass reading cockpit.toml
scripts/            — CLI entry points (not importable as library code)
data/
  historical_data/  — Cached CSV files
  backtest_results/ — Pickled backtest result bundles
```

Data flows in one direction: **marketdata → core → analysis/strategies → backtesting → visualization**. `broker/` provides Schwab account ops but does not feed the data pipeline.

### Adding a New Strategy

1. Create `strategies/your_strategy.py` subclassing `BaseStrategy`
2. Implement `calculate_indicator(self)` — add indicator columns to `self._data`
3. Implement `generate_signals(self)` — add `self._data['signal']` (1=buy, -1=sell, 0=hold)
4. Add an entry to `STRATEGY_REGISTRY` in `scripts/run_backtest.py`

---

## Known Issues

- Intraday/sub-daily intervals do not source correctly from yfinance
- The backtest dashboard does not support intraday visualization
- Schwab does not support paper trading — live account commands affect a real account
- Schwab token files expire every 7 days and require re-running `scripts/schwab_auth.py`
- Cockpit currently displays mock data; live data wiring is planned for a future session
