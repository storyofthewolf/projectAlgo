# Session 2 Debrief — Cockpit TUI Skeleton

**Date:** 2026-05-16  
**Spec:** `specs/session-2-spec.md`  
**Status:** All 19 acceptance criteria verified.

---

## What was built

A Textual TUI cockpit (`cockpit/`) with:
- **HomeScreen** — 5-panel layout: account placeholder, market pulse, watchlist, sector heatmap, correlation matrix
- **HelpScreen** — keyboard reference, opened with `?`, closed with `Esc`
- **ClockHeader** — ET time, ticks every second, detects market state (PRE-MKT / MKT OPEN / AFTER-HRS / MKT CLOSED)
- **CommandFooter** — `[Q]UIT [R]EFRESH [?]HELP [T]HEME [TAB]NAV`
- **PanelFrame** — thin Container wrapper that sets `border_title` for Textual's native title-in-border
- **PriceCell / PctCell** — flash on update, settle to directional color (3 s window, 300 ms flash)
- **Sparkline** — 8-level unicode block sparklines (`▁▂▃▄▅▆▇█`)
- **Two themes** — `claude-warm` (dark amber) and `blue-orange`; cycle with `T`; persisted in `cockpit.toml`
- **Mock data** — `cockpit/mock_data.py`; `R` key triggers ±0.5% perturbation
- **Color-coded sector bars** — Rich markup with per-theme `positive`/`negative` hex colors
- **Color-coded correlation matrix** — `primary` (>0.7), `secondary` (0.3–0.7), `text_dim` (near zero), `negative` (<−0.3)

## Existing codebase changes (non-cockpit)

Three changes carried over from loose ends after the session-1 refactor:

1. **`analysis/technical_analysis.py`** — removed `from __future__ import annotations` (Python 3.14 supports native union syntax natively)
2. **`scripts/correlations.py`** — removed `--data-dir` CLI arg and the `data_dir` kwarg from `load_aligned_returns()` call (DataService manages paths)
3. **`analysis/market_analysis.py`** — `load_aligned_returns()` no longer accepts `data_dir`

---

## Key technical findings

### Textual 8.x theme system

The spec was written against an older Textual API (plain dict themes). Textual 8.2.6 uses a `Theme` dataclass with `name`, `primary`, `secondary`, `background`, `surface`, `dark`, and a `variables: dict[str, str]` slot for extras.

- `App.register_theme(theme)` — registers by name
- `App.theme` — reactive string (set by name, not object)
- `App.get_css_variables()` — override to inject custom vars before stylesheet parse

### CSS variable resolution race

`styles.tcss` references `$text-dim`, `$positive`, `$negative`, etc., which are not in Textual's built-in themes. On first parse (before `on_mount`), Textual resolved against the default theme (`textual-dark`) and threw `UnresolvedVariableError`.

**Fix:** Override `get_css_variables()` in `CockpitApp` to unconditionally inject all custom variables from `THEMES_CONFIG`. Also moved `register_theme()` calls from `on_mount()` to `__init__()` so themes are available at the earliest possible moment.

### `::after` pseudo-elements not supported in Textual CSS

The spec's resize-warning approach (`Screen.too-small::after { content: ... }`) fails with a parse error. **Fix:** Added a `#resize-warning` Static widget to `HomeScreen`, styled it with `layer: overlay`, `display: none` by default, and shown via `Screen.too-small #resize-warning { display: block }`.

### Python 3.14 compatibility

- `pandas-ta` not available for 3.14 — not imported anywhere so irrelevant
- `schwab-py` not available for 3.14 — not needed for cockpit (mock data only)
- `yfinance`, `textual`, `tomllib` (stdlib) all work on 3.14
- Install path: `pip3.14 install ... --break-system-packages` (Homebrew Python)

---

## Deferred items

The following spec sections are explicitly out of scope for this session:
- Live data wiring (Schwab or yfinance) — account panel shows placeholder
- Auto-refresh polling loop — `R` key is manual only
- Watchlist YAML loading — hardcoded in `mock_data.py`
- Drill-down screens for sectors, correlations, individual tickers
- `[DELAYED]` tag in ClockHeader is hardcoded (will be wired to data source latency later)
