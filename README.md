# projectAlgo

<img src="assets/logo.png" alt="Project Logo" width="200" title="projectAlgo Logo">

an algorithmic trading suite in python by storyofthewolf

feels the vibes!

---

## About The Project

A Python toolkit for collecting and managing historical market data, computing technical indicators, and monitoring markets live. Integrates with the Charles Schwab API for live account data and quotes. Includes a terminal-resident market monitoring dashboard built with Textual.

### Key Features

- Fetch and cache historical OHLCV data from Yahoo Finance or Charles Schwab
- Live account balances, positions, and quotes via Schwab API
- Technical indicators: SMA, RSI (extensible)
- Pairwise correlation analysis (library functions in `analysis/market_analysis.py`)
- **Cockpit TUI** — live terminal market dashboard with market pulse, watchlist, sector heatmap, sector deep-dive, correlation matrix deep-dive, and per-ticker scalar metrics drill-down

---

## Getting Started

### Prerequisites

- Python 3.9+ (recommended; Python 3.11 works equally well)
- Active internet connection for data downloads

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/storyofthewolf/projectAlgo.git
   cd projectAlgo
   ```

2. **Create and activate a Conda environment:**
   ```bash
   conda create -n algo_env python=3.11
   conda activate algo_env
   pip install -r requirements.txt
   ```

3. **Configure settings** in `cockpit.toml` at the project root.

---

## Configuration

Project-wide settings live in `cockpit.toml`:

```toml
[data]
preferred_source = "yfinance"   # flip to "schwab" after completing OAuth
data_dir = "data/historical_data"

[theme]
default = "claude-warm"   # or "blue-orange"

[sectors]
lookback_days = 20
comparison_ticker = "SPY"
intensity_max_pct = 5.0
refresh_interval_seconds = 300

[pulse]
tickers = [
    { symbol = "SPY", label = "S&P 500", format = "price" },
    # ...
]
```

See `cockpit.toml` for the full reference including `[sector_deep_dive]`, `[correlations]`, `[ticker_detail]`, and `[pulse]` sections.

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

### 2. Live Account & Quotes (requires Schwab auth)

```bash
python -m scripts.account                  # balances + positions
python -m scripts.account --balances-only
python -m scripts.account --positions-only
python -m scripts.quote AAPL MSFT ISRG    # live quotes
```

### 3. Cockpit TUI

Live terminal market dashboard.

```bash
python -m scripts.cockpit
```

Minimum terminal size: 120×30. Keyboard shortcuts:

| Key | Action |
|-----|--------|
| `Q` | Quit |
| `R` | Refresh data + reload config |
| `?` | Help |
| `T` | Cycle theme |
| `W` | Cycle watchlist |
| `/` | Ticker drill-down (scalar metrics panel) |
| `S` | Sector deep-dive screen (multi-timeframe RS table, sortable) |
| `C` | Correlation deep-dive screen (full matrix, cycle method/lookback/preset) |
| `Esc` | Back to previous screen |
| `Tab` / `Shift+Tab` | Navigate panels |

Watchlists are configured in `watchlists.yaml` at the project root.

---

## Architecture

```
UI / Views  (cockpit TUI, CLI scripts)
     ↓
Workflows   (orchestration: composes data + analysis into snapshots)
     ↓
Analysis    (stateless computation)
     ↓
Domain Models  (Stock, Quote — passive containers)
     ↓
Data Layer  (DataService + MarketDataSource implementations)
     ↓
Sources  (yfinance, Schwab)
```

```
marketdata/         — DataService: unified data fetch, cache, and source fallback
  sources/          — YFinanceSource, SchwabSource (MarketDataSource ABC)
  cache.py          — LocalCache: CSV read/write ({ticker}_{interval}.csv)
broker/             — Schwab OAuth client, account summary, live quote wrappers
core/               — Stock (passive dataclass), Quote data models
analysis/           — Stateless indicator functions
  market_analysis.py — load_aligned_returns, calculate_relative_strength, correlation matrix
workflows/          — Pure data orchestration (no Textual/asyncio)
  watchlist_snapshot.py              — WatchlistSnapshot, build_watchlist_snapshot()
  market_pulse_snapshot.py           — PulseSnapshot, build_pulse_snapshot()
  sector_snapshot.py                 — SectorSnapshot, build_sector_snapshot(); SPDR_SECTORS list
  multi_timeframe_sector_snapshot.py — MultiTimeframeSectorSnapshot, build_multi_timeframe_sector_snapshot()
  correlation_snapshot.py            — CorrelationSnapshot, build_correlation_snapshot()
  ticker_metrics_snapshot.py         — TickerMetrics, build_ticker_metrics()
cockpit/            — Textual TUI dashboard
  screens/          — HomeScreen, HelpScreen, SectorDeepDiveScreen, CorrelationDeepDiveScreen,
                      TickerFinderModal, TickerDetailScreen
  widgets/          — ClockHeader, CommandFooter, PanelFrame, PriceCell, PctCell, Sparkline,
                      WatchlistPanel, MarketPulsePanel, SectorPanel, SectorTable,
                      CorrelationPanel, CorrelationTable, RankedPairList, TickerMetricsPanel
  watchlists/       — YAML and Schwab watchlist providers
config/             — Settings dataclass reading cockpit.toml
scripts/            — CLI entry points (not importable as library code)
data/
  historical_data/  — Cached CSV files
watchlists.yaml     — Named watchlists for the cockpit TUI
```

The cockpit is read-only — no order placement.

---

## Known Issues

- Intraday/sub-daily intervals do not source correctly from yfinance
- Schwab does not support paper trading — live account commands affect a real account
- Schwab token files expire every 7 days and require re-running `scripts/schwab_auth.py`
- Sector and correlation gradient colors update on the next polling refresh after a theme change, not immediately
- `preferred_source = "yfinance"` until Schwab OAuth is configured
