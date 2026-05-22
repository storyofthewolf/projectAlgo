# projectAlgo — Roadmap

This document is the master plan for the projectAlgo build. It lives in `specs/ROADMAP.md` and travels with the codebase. Update at the end of each planning round.

When starting a new planning conversation in Claude.ai, paste this file along with `ARCHITECTURE.md` and the latest debrief (`notes/session-N-debrief.md`) to bring a fresh Opus instance up to speed.

---

## Project vision

**projectAlgo is a personal market cockpit** — a terminal-resident, keyboard-driven environment for monitoring markets, analyzing trends, and (eventually) supporting trading decisions. It is not a generic trading suite. It is intensely personalized to the owner.

**Primary goals, in priority order:**
1. Make the owner a better-informed market participant
2. Provide a flow-state environment where situational awareness is dense, fast, and pleasant
3. Be a vehicle for learning markets and modern Python craft
4. *(Tentative)* eventually generate trading edge — but learning comes first

**Anti-goals:**
- Reproducing what free tools (Yahoo Finance, Schwab mobile app) already do well
- Building generic quant-trading infrastructure
- High-frequency trading capability
- Polish over substance — owner prefers a useful prototype over a beautiful unfinished one

## Owner context

- Background: scientific computing (FORTRAN climate modeling). FORTRAN analogies welcome and helpful.
- Prefers terminal/CLI over GUI/IDE. Prefers typing to clicking. Strong yes to vim-style text-file configuration over UI menus.
- Has a Claude.ai Pro plan with a hard $5/month overage budget. Sessions must fit in Pro limits.
- **Workflow split:** Opus 4.7 in Claude.ai for architecture/planning conversations. Sonnet 4.6 in Claude Code for actual code execution. Each session is planned in Claude.ai with Opus, then executed in Claude Code with Sonnet via a written handoff spec.
- Background expertise: planetary climate modeling, terrestrial exoplanet habitability. Eric Wolf's voice/style applies to written work in that domain (irrelevant for projectAlgo specifically).

## Architecture summary

See `ARCHITECTURE.md` for the full description. Briefly:

A **layered architecture** with strict downward dependencies:

```
UI / Views (cockpit TUI, Dash deep-dives, CLI scripts)
     ↓
Workflows (orchestration: composes data + analysis into snapshots)
     ↓
Analysis / Strategies (stateless computation)
     ↓
Domain Models (Stock, Quote, Transaction — passive containers)
     ↓
Data Layer (DataService + MarketDataSource implementations)
     ↓
Sources (yfinance, Schwab)
```

The cockpit is a **viewer, not a doer** — read-only, no order placement. Live trading would be a separate project that imports from this one.

## Session plan

A multi-session build, each session bounded to fit comfortably in one Claude Code window. Each session produces a working, testable state.

### Session 1 — Foundation: data layer + config — **✅ DONE**

**Built:**
- `marketdata/` package with `DataService` and `MarketDataSource` ABC
- `YFinanceSource` and `SchwabSource` (Schwab compiles but is deferred end-to-end)
- `LocalCache` for CSV cache
- `core/security.py` (passive `Stock` dataclass), `core/quote.py`, `core/transaction.py`
- `config/settings.py` + `cockpit.toml` for app-wide configuration
- All existing scripts updated to new architecture

### Session 2 — Cockpit skeleton + home screen layout — **✅ DONE**

**Built:**
- `cockpit/` package: Textual app, home screen, help screen
- Five-panel home layout: account placeholder, market pulse, watchlist, sector heatmap, correlation matrix
- Two themes: `claude-warm` (default) and `blue-orange` (colorblind-friendly), cycled with `T`
- Bloomberg-density × Claude-warm-palette aesthetic
- Reusable widgets: `Sparkline`, `PriceCell`, `PctCell`, `PanelFrame`, `ClockHeader`, `CommandFooter`
- Mock data with flash-on-update animation triggered by `R`
- Numeric formatting helpers (`cockpit/format.py`)
- Help screen via `?`, returns via `Esc`

### Session 3 — Watchlist real-data wiring — **✅ DONE**

**Built:**
- `watchlists.yaml` at project root with multi-watchlist support
- `cockpit/watchlists/` package (YAML provider, Schwab provider stub, registry)
- `workflows/watchlist_snapshot.py` — first concrete workflow layer
- Watchlist panel wired to live yfinance quotes
- Auto-refresh polling; hot-reload on `R`; multi-watchlist cycling on `W`

**Pattern established:** workflow → HomeScreen reactive → `@work` worker → `set_interval` timer → pure-renderer panel widget. This is the load-bearing template for all subsequent panels.

### Session 4 — Market pulse real-data wiring — **✅ DONE**

**Built:**
- `workflows/market_pulse_snapshot.py` — `PulseSnapshot`, `PulseTicker`, `build_pulse_snapshot()`
- `cockpit/widgets/market_pulse_panel.py` — 4×2 grid with three display formats (price/index/yield)
- `[pulse]` section in `cockpit.toml` with 8 configurable tickers
- 30-day sparklines from cached historical data; quotes polled live every 30s

### Session 5 — Sector heatmap (home panel) — **✅ DONE**

**Built:**
- `workflows/sector_snapshot.py` — 11 SPDR ETF RS vs SPY
- `cockpit/widgets/sector_panel.py` — single-row strip with continuous-gradient backgrounds
- `analysis/market_analysis.py` extended with `calculate_relative_strength()`
- `cockpit/format.py` extended with `relative_strength_to_color()` (linear RGB interpolation)
- Three-color gradient per theme (`gradient_positive`, `gradient_negative`, `gradient_neutral`)
- 5-min polling cadence; sparklines showing RS path

### Session 6 — Sector deep-dive screen — **✅ DONE**

**Built:**
- `workflows/multi_timeframe_sector_snapshot.py` — `MultiTimeframeSectorSnapshot`, `SectorRow`, `TimeframeRS`
- `cockpit/screens/sectors.py` — `SectorDeepDiveScreen`; `S` key enters, `Esc` exits
- `cockpit/widgets/sector_table.py` — Rich-markup table; column focus, sort arrows, gradient cells
- `[sector_deep_dive]` section in `cockpit.toml` with configurable timeframes (5D/1M/3M/YTD)
- SPY pinned at top row; 60s polling

### Session 7 — Correlation panel real data + deep-dive — **✅ DONE**

**Built:**
- `workflows/correlation_snapshot.py` — `CorrelationSnapshot`, `RankedPair`, `build_correlation_snapshot()`
- `cockpit/widgets/correlation_panel.py` — home screen lower-triangle + diagonal matrix, gradient cells
- `cockpit/widgets/correlation_table.py` — deep-dive full N×N matrix, Rich-markup rendering
- `cockpit/widgets/ranked_pair_list.py` — deep-dive right panel, pairs ranked high→low, text-color gradient
- `cockpit/screens/correlations.py` — `CorrelationDeepDiveScreen`; `C` enters, `Esc` exits
- `[correlations]` and `[correlation_deep_dive]` sections in `cockpit.toml`
- `M` cycles method (Pearson/Spearman/Kendall); `[`/`]` adjusts lookback; `P` cycles preset
- `_refresh_mock_panels` deleted — home screen now fully live

### Session 8 — Ticker drill-down + screener CLI — **✅ DONE**

**Built:**
- `workflows/ticker_detail_snapshot.py` — `TickerDetailSnapshot`, `IndicatorReadout`, `TickerStats`, `build_ticker_detail_snapshot()`, `build_ticker_quote_snapshot()`
- `cockpit/screens/ticker_finder_modal.py` — `TickerFinderModal`; centered `ModalScreen` with `_is_valid_ticker()` validation
- `cockpit/screens/ticker_detail.py` — `TickerDetailScreen`; full-screen drill-down with scroll, two workers (full refresh + quote repoll)
- `cockpit/widgets/ticker_header.py` — three-row header: ticker/name, price/change, day/52w range
- `cockpit/widgets/ohlc_table.py` — Rich-markup OHLC table, newest-first, scroll-offset aware
- `cockpit/widgets/indicator_panel.py` — SMA readouts with vs-price %, RSI + regime label, color-coded
- `cockpit/widgets/price_chart.py` — in-terminal Plotext close-price + SMA overlays; `P` launches `view_stock.py` Dash app as detached subprocess on port 8050
- `analysis/screener.py` — `scan_universe(tickers, ...)` returns `ScanResult(metrics, failed)`; per-ticker failure tolerance; 13 metric columns including `rs_spy_1m`
- `scripts/scan.py` — cross-sectional scan CLI: universe resolution (index txt > watchlist > `-t`), pandas-style `-q` filter, `--rank`, `--columns`, `--limit`, `--list-metrics`
- `universes/sp500.txt` — S&P 500 constituent list, yfinance format
- `[ticker_detail]` section in `cockpit.toml`
- `config/settings.py` extended with `TickerDetailConfig` and `_parse_ticker_detail()`

**30 of 30 automated ACs pass.**

**Technical findings:**
- `yfinance.Ticker(ticker).info` called directly in the workflow for `longName` (documented leak; adding to `MarketDataSource` ABC was disproportionate for a cosmetic field)
- Pop-then-push logic in `CockpitApp.action_open_ticker_finder()` + `TickerDetailScreen.action_find_ticker()` ensures `Esc` always returns to home regardless of how many times `/` was pressed
- `sma_vs_price_pct` recomputed on 30s quote repoll without touching history or indicators
- `day_high`/`day_low` use most recent daily bar as proxy (live intraday range requires Schwab intraday)
- Plotext chart (`price_chart.py`) is coarse by design; `P` spawns the full Dash interactive chart

### Session 9 — Polish pass (planned)

Aesthetic improvements across all panels and screens, now that the monitoring tier is feature-complete.

**Scope (tentative):**
- Immediate theme recolor for gradient cells (currently updates on next refresh, not on `T`)
- `CommandFooter` audit — consistent key labeling across all screens
- `pandas-ta` removal from `requirements.txt`
- Any layout tweaks identified during Sessions 5-8 interactive review
- Per-screen theme assignment (infrastructure ready; activate if desired)

### Session 10 — Schwab integration end-to-end (timing flexible)

When the owner completes Schwab OAuth and `schwab-py` (or alternative) works on Python 3.14:
- Validate the Schwab path end-to-end using the verification checklist in `notes/session-1-debrief.md`
- Account panel: replace placeholder with live balances + positions
- Live intraday high/low for the ticker drill-down header (current proxy is last daily bar)
- Flip `preferred_source = "schwab"` in `cockpit.toml`
- May not need its own full session — could be a config-flip plus a smoke-test pass

### Future rooms (post-monitoring tier, conceptual)

Built when the monitoring tier is mature and the owner wants more:
- Options pricing room (Black-Scholes, Greeks, position P&L scenarios)
- Volatility regime room
- Macro regime room
- Earnings calendar room
- Backtesting integration into cockpit (deep-dive from a signal in the screener into a backtest)
- Strategy development tools
- "Reading list" room (news/research filtered to watchlist tickers)
- Dash/Plotly interactive heatmap from the cockpit (`scripts/correlations.py --plot` is CLI-only today)

Eventually possibly: a *separate* repository for live trading that consumes signals from this one, with a hard airlock between read-only analysis and order placement.

## Workflow conventions

### Opus / Sonnet split

- **Opus 4.7 in Claude.ai (planning):** architectural decisions, spec writing, debrief review, design conversations
- **Sonnet 4.6 in Claude Code (execution):** writes code from specs, runs tests, produces debriefs

Opus tokens are flat-rate Pro; Sonnet tokens cost more per use but execute efficiently when the spec is tight.

### One chat per session

To control token costs and keep context focused, **each planning session is a separate Claude.ai conversation**. The persistent project memory lives in:

- `specs/ROADMAP.md` (this file)
- `specs/ARCHITECTURE.md`
- `specs/session-N-spec.md` (one per session)
- `notes/session-N-debrief.md` (one per session)

When starting a new planning chat, paste in `ROADMAP.md` + `ARCHITECTURE.md` + the latest debrief. Within-Project memory in Claude.ai carries some context automatically, but the documents are the authoritative source.

### Session structure

1. **Planning** (Opus in Claude.ai): pin down scope, decisions, acceptance criteria; produce `specs/session-N-spec.md`
2. **Execution** (Sonnet in Claude Code): read spec, build, verify acceptance criteria, produce `notes/session-N-debrief.md`
3. **Review** (Opus in next chat): read debrief, update `ROADMAP.md`, plan next session

### Spec characteristics

Good handoff specs include: mandatory read list, target file layout, interface signatures, concrete before/after code patterns, explicit acceptance criteria, explicit "what stays as-is" non-goals, and a "what to do if stuck" section.

The goal is for Sonnet to execute without re-deriving architectural decisions. Decisions go in this conversation; execution goes in the spec.

## Status snapshot

**Current state:** Sessions 1-8 complete. The cockpit is **feature-complete for market monitoring**.

- All five home-screen panels are wired to live data
- Two deep-dive screens: sectors (`S`) and correlations (`C`)
- Ticker drill-down (`/`) with quote, OHLC table, SMA/RSI indicators, in-terminal Plotext chart, and `P`-key Dash launch
- Cross-sectional screener CLI (`scripts/scan.py`) with S&P 500 universe support
- `_refresh_mock_panels` is deleted — home screen fully live

**Working features:**
- Existing CLI scripts (`get_data`, `run_backtest`, `correlations`, `plot_static`, `view_stock`, `view_backtest`) — all via `DataService`
- Cockpit TUI launches, navigates, themes cycle
- Market pulse panel: 8 configurable tickers, three display formats, sparklines, 30s polling
- Watchlist panel: live quotes, configurable via `watchlists.yaml`, multi-list cycling on `W`, hot-reload on `R`
- Sector heatmap: 11 SPDR ETFs + SPY RS vs SPY, gradient-colored cells, 5-min polling
- Sector deep-dive (`S`): multi-timeframe RS table (5D/1M/3M/YTD), sortable columns, sparklines, 60s polling
- Correlation panel: gradient-colored lower-triangle matrix, 5-min polling
- Correlation deep-dive (`C`): full N×N matrix + ranked pair list; `M` cycles method, `[`/`]` adjusts lookback, `P` cycles preset, 60s polling
- Ticker drill-down (`/`): quote header, scrollable OHLC table, SMA/RSI indicator panel, Plotext price chart, `P` spawns Dash
- Screener CLI: `python -m scripts.scan <universe> -q "..." --rank ...`; S&P 500 and watchlist universes; 13 metric columns
- yfinance data source fully functional including special symbols (`^VIX`, `^TNX`, `DX-Y.NYB`, `CL=F`, `GC=F`)
- Schwab data source compiles but is unauthenticated (deferred)

**Known deferred items:**
- Schwab OAuth setup (owner will do when ready)
- `schwab-py` on Python 3.14 (may need workaround when relevant)
- `pandas-ta` removal from `requirements.txt` (trivial cleanup)
- Account panel still placeholder — waits on Schwab session
- Immediate theme recolor on sector/correlation/indicator gradient cells (updates on next refresh)
- `CommandFooter` audit for consistent key labeling across screens
- Dash/Plotly interactive heatmap (`visualization/plot_correlation.py`) remains CLI-only
- Live intraday day range in ticker drill-down header (proxy uses last daily bar; live range needs Schwab)
- Dash subprocess not killed when cockpit exits

**Architecture stability:** The workflow→reactive→worker→renderer pattern is proven across 5 home panels + 2 deep-dive screens + 1 drill-down screen. Session 9 (polish) is additive refinement. Session 10 (Schwab) is a config + data-path validation exercise.
