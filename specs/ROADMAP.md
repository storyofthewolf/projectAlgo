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
Analysis / Strategies / Options (stateless computation)
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
- `LocalCache` for CSV cache (same filename format as before)
- `core/security.py` (passive `Stock` dataclass), `core/quote.py`, `core/transaction.py`
- `config/settings.py` + `cockpit.toml` for app-wide configuration
- All existing scripts updated to new architecture
- `data_manager/`, `broker/market_data.py`, `core/financial_objects.py` deleted

**Verified:** 13 of 13 non-deferred acceptance criteria pass. Schwab end-to-end deferred until OAuth setup.

**Side findings:**
- Pre-existing Python 3.9 union-type bug in `analysis/technical_analysis.py` (later removed in Session 2)
- Pre-existing silently-broken `calculate_indicator()` in `plot_static.py` (fixed)

### Session 2 — Cockpit skeleton + home screen layout — **✅ DONE**

**Built:**
- `cockpit/` package: Textual app, home screen, help screen
- Five-panel home layout: account placeholder, market pulse, watchlist, sector heatmap, correlation matrix
- Two themes: `claude-warm` (default) and `blue-orange` (colorblind-friendly), cycled with `t`
- Bloomberg-density × Claude-warm-palette aesthetic
- Reusable widgets: `Sparkline`, `PriceCell`, `PctCell`, `PanelFrame`, `ClockHeader`, `CommandFooter`
- Mock data with flash-on-update animation triggered by `r`
- Numeric formatting helpers (`cockpit/format.py`) — 2-decimal prices, signed percentages, compact volume, em-dash for missing
- Help screen via `?`, returns via `Esc`
- Adaptive layout: 120×30 minimum, 160×50 ideal, friendly resize message below minimum

**Verified:** 19 of 19 acceptance criteria pass.

**Cleanup carried over from Session 1:**
- `from __future__ import annotations` removed from `technical_analysis.py` (project is now on Python 3.14)
- `--data-dir` flag removed from `scripts/get_data.py`
- Unused `data_dir` param removed from `load_aligned_returns()`

**Technical findings:**
- Textual 8.x theme API differs from the spec; Sonnet adapted using `App.register_theme()` and `get_css_variables()` override
- CSS variable resolution race resolved by injecting custom variables before stylesheet parse
- `::after` pseudo-elements unsupported in Textual CSS — used overlay widget for resize warning instead

**Python 3.14 compatibility notes:**
- `yfinance`, `textual`, `tomllib` (stdlib): work fine
- `pandas-ta`: no 3.14 wheel yet; not actually used in codebase, safe to remove from `requirements.txt` in a future cleanup
- `schwab-py`: no 3.14 wheel yet; relevant for when Schwab wiring happens — re-check at that time, or consider using `httpx` directly

### Session 3 — Watchlist real-data wiring — **NEXT**

**Goal:** Wire the watchlist panel to real data via DataService. This proves the end-to-end data pattern that all later panels will replicate.

**Scope:**
- `watchlists.yaml` at project root — hand-edited, defines named watchlist groups
- `cockpit/watchlists.py` — loads + validates YAML
- `workflows/watchlist_snapshot.py` — first concrete Workflow layer code; fetches quotes for tickers, returns typed `WatchlistSnapshot`
- Wire `HomeScreen` watchlist panel to call the workflow
- Auto-refresh polling loop (every `refresh.interval_seconds` from `cockpit.toml`)
- Hot-reload of `watchlists.yaml` when `r` is pressed
- Multi-watchlist support: cycle between named lists with `w`

**Out of scope:**
- Account panel (still placeholder)
- Market pulse / sectors / correlations real data (Sessions 4+)
- Drill-down screens

**Pre-Session-3 questions for the owner (collect in Session 3 planning chat):**
- Aesthetic reactions to the cockpit (density, colors, flash timing)
- Layout reactions (panel sizes, account placeholder, watchlist row count)
- Ergonomics reactions (keyboard bindings, help screen, theme cycling)
- Watchlist YAML schema acceptance
- Actual watchlists to ship in the spec, or generic examples

### Session 4 — Market pulse real data (planned)

Same pattern as Session 3 but for SPY/QQQ/IWM/VIX/10Y/DXY. Configurable pulse tickers in `cockpit.toml`. Reuses polling infrastructure from Session 3.

### Session 5 — Sector heatmap real data + sector deep-dive screen (planned)

11 SPDR sector ETFs with relative strength vs SPY. Full sector screen on `s` key. Multi-timeframe view.

### Session 6 — Correlation panel real data + deep-dive (planned)

Mini correlation matrix on home with real data. Full correlation screen on `c` with adjustable lookback, method, ticker set. Dash subprocess for interactive heatmap.

### Session 7 — Ticker drill-down + polish (planned)

Press `/` then type ticker → drill-down screen with key stats, recent OHLC, basic indicators. "Open in Dash" key spawns chart subprocess. Aesthetic polish pass.

### Session 8 — Schwab integration end-to-end (timing flexible)

When the owner completes Schwab OAuth and `schwab-py` (or alternative) works on Python 3.14, validate the Schwab path end-to-end using the verification checklist Sonnet provided in `session-1-debrief.md`. May not need its own session — could be a config-flip plus a smoke-test pass.

### Future rooms (post-monitoring tier, conceptual)

Built when the monitoring tier is mature and the owner wants more:
- Options pricing room (Black-Scholes, Greeks, position P&L scenarios)
- Volatility regime room
- Macro regime room
- Earnings calendar room
- Backtesting integration into cockpit
- Strategy development tools
- "Reading list" room (news/research filtered to watchlist tickers)

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

**Current state:** Cockpit TUI shell complete with mock data. Real data wiring begins in Session 3.

**Working features:**
- Existing CLI scripts (`get_data`, `run_backtest`, `correlations`, `plot_static`, `view_stock`, `view_backtest`) — all via `DataService`
- Cockpit TUI launches, navigates, themes cycle, mock data flashes on refresh
- yfinance data source is fully functional
- Schwab data source compiles but is unauthenticated (deferred)

**Known deferred items:**
- Schwab OAuth setup (owner will do when ready)
- `schwab-py` on Python 3.14 (may need workaround when relevant)
- `pandas-ta` removal from `requirements.txt` (trivial cleanup)
- Per-room theme assignment (infrastructure ready, not used yet)
- Auto-refresh polling (Session 3)
- Watchlist YAML config (Session 3)

**Architecture stability:** No expected refactors. Sessions 3-7 are additive on top of the foundation from Sessions 1-2.
