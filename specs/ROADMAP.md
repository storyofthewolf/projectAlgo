The cockpit is a **viewer, not a doer** — read-only, no order placement, ever.

## Session history

### Sessions 1–8 — ✅ DONE

A full monitoring cockpit was built across 8 sessions: data layer, TUI skeleton,
watchlist, market pulse, sector heatmap, sector deep-dive, correlation panel +
deep-dive, and ticker drill-down + screener CLI. The build was fast and largely
vibe-coded. The architecture is sound; some of what was built is now out of scope
given the revised thesis and will be deleted in Session 9.

**Core that survives:**
- `marketdata/` — data layer, cache, yfinance + Schwab sources
- `core/` — Quote, Stock domain models
- `config/` — Settings, cockpit.toml
- `workflows/` — pulse, watchlist, sector, correlation snapshots
- `cockpit/` — TUI, all home panels, sector and correlation deep-dives
- `analysis/market_analysis.py`, `analysis/technical_analysis.py` (the SMA and
  return helpers used by surviving workflows)
- `watchlists.yaml`

**What is being deleted in Session 9:**
- `backtesting/` — backtesting engine
- `strategies/` — SMA crossover and base strategy
- `analysis/screener.py` — cross-sectional screener
- `analysis/performance_metrics.py` — backtest performance metrics
- `visualization/` — Dash apps, mplfinance, Plotly heatmap
- `scripts/run_backtest.py`, `scripts/scan.py`, `scripts/correlations.py`,
  `scripts/inspect_pickle.py` — CLI entry points for deleted features
- `universes/` — S&P 500 constituent list (screener dependency)
- `cockpit/widgets/ohlc_table.py`, `price_chart.py` — OHLC and chart widgets
- `core/transaction.py` — backtest artifact, unused by cockpit
- `data/backtest_results/` — pickled backtest output directory
- `pandas-ta` from `requirements.txt`
- `textual-plotext` from `requirements.txt`
- `mplfinance`, `dash`, `plotly` from `requirements.txt`

**Ticker drill-down survives but is rescoped:** strip OHLC table and Plotext chart;
replace with a compact scalar metrics panel (price, change, 52w range, volume,
RS vs SPY, SMA distance — numbers only). Remove `P`-key Dash launch.

## Upcoming sessions

### Session 9 — Codebase cleanup and deletion — NEXT

**Goal:** Delete all out-of-scope code cleanly. Claude Code performs the deletions
and import cleanup. Owner reviews the diff before committing.

**Acceptance criteria:**
- All listed deletions above complete
- `python3.14 -m scripts.cockpit` still launches cleanly
- No broken imports remaining
- `requirements.txt` trimmed to only what the cockpit actually uses
- Ticker drill-down rescoped to a scalar metrics panel; OHLC table, Plotext chart,
  and `P`-key Dash launch removed
- `CLAUDE.md`, `README.md`, `DEVELOPER_NOTES.md`, `ARCHITECTURE.md` updated to
  reflect the deletions (no references to removed modules or CLI scripts)

### Session 10 — Schwab OAuth

**Goal:** Connect to Schwab API for the first time. Done on personal machine.
Scoped deliberately small — this is authentication and smoke-testing only,
not UI work.

**Steps:**
- Read `schwab-py` docs (not Schwab's raw API docs — the library handles everything)
- Run `scripts/schwab_auth.py`, complete browser OAuth flow, confirm token saved
- Confirm `SchwabSource.is_available()` returns True
- Smoke-test `scripts/quote.py` with a known ticker
- Confirm `scripts/account.py` returns balances and positions
- Note any Python 3.14 compatibility issues with `schwab-py`

### Session 11 — Schwab portfolio panel

Wire the account panel on the home screen with live Schwab data:
- Balances: cash, total portfolio value, day P&L
- Positions table: ticker, shares, cost basis, current value, gain/loss %, day change
- 30s polling cadence
- Positions sorted by current value descending

This is the most important missing feature given the revised project scope.

### Future directions (post-Session 11)

Possibilities only — build what earns its place through actual use:

- **Custom sector watchlists and thematic heatmaps** — user-defined groupings in
  `watchlists.yaml` beyond SPDR ETFs, for tracking thematic arcs (e.g. "space,"
  "AI infrastructure," "energy transition"). Rendered as a sector-style gradient
  strip on the home screen or a new deep-dive screen.

- **Macro regime indicators** — yield curve shape, credit spreads, dollar trend,
  inflation expectations as scalar readouts. Sentiment context for the broader
  market environment. Numbers only, no charts.

- **Novel sentiment metrics** — needs its own dedicated thinking session before
  any build. The interesting version is something derived, not scraped (news
  aggregation is solved by Schwab/Yahoo/etc. and not worth duplicating). Noted
  as a seed for later.

**Explicitly out of scope indefinitely:**
- Backtesting
- TA strategy generation
- Cross-sectional screening
- OHLC/candlestick visualization
- News aggregation or web scraping
- Options pricing
- Any order placement

## Workflow conventions

- **Planning:** Claude.ai, one chat per session. Architecture decisions made here.
  Persistent docs: `ROADMAP.md`, `ARCHITECTURE.md`, latest session debrief.
- **Execution:** Claude Code with Sonnet, driven by a written handoff spec.
- **Budget:** Hard $5/month above Pro. Keep sessions scoped accordingly.
- **Learning:** Prefer understanding code over generating it. When in doubt, read
  the file before asking Claude to rewrite it.

## Status snapshot

**Current state:** Sessions 1–8 complete. Project thesis revised. Cleanup and
Schwab connection are the immediate next steps.

**Immediate next action:** Session 9 — Claude Code performs guided deletion of
out-of-scope code on personal machine. Owner reviews diff.
