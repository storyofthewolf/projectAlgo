# Session 9 Preflight Inventory

## Dependents of modules to be deleted

- **backtesting/**: `scripts/run_backtest.py`, `backtesting/engine.py` (internal — imports from strategies/)
- **strategies/**: `scripts/run_backtest.py`, `backtesting/engine.py`
- **analysis/screener.py**: `scripts/scan.py`
- **analysis/performance_metrics.py**: `scripts/run_backtest.py`
- **visualization/**: `scripts/correlations.py` (plot_correlation_heatmap), `scripts/run_backtest.py`
- **core/transaction.py**: `backtesting/engine.py`
- **universes/**: `scripts/scan.py` (path resolution)
- **cockpit/widgets/ohlc_table.py**: `cockpit/screens/ticker_detail.py`, `scripts/verify_session8.py`
- **cockpit/widgets/price_chart.py**: `cockpit/screens/ticker_detail.py`, `scripts/verify_session8.py`
- **cockpit/widgets/indicator_panel.py**: `cockpit/screens/ticker_detail.py`, `scripts/verify_session8.py`
- **cockpit/widgets/ticker_header.py**: `cockpit/screens/ticker_detail.py`, `scripts/verify_session8.py`

Note: `scripts/verify_session8.py` references the orphan widgets but is itself a leaf script with no internal dependents.

## Ticker detail workflow imports

`workflows/ticker_detail_snapshot.py` imports:
- `analysis.technical_analysis` — `calculate_rsi`, `calculate_sma`
- `config.settings` — `TickerDetailConfig`
- `core.quote` — `Quote`
- `marketdata.service` — `get_data_service`
- Standard library: `logging`, `dataclasses`, `datetime`, `typing`
- `pandas`
- Inline: `yfinance` (in `_fetch_ticker_name()` only)

Does NOT import from `analysis.screener` or `analysis.performance_metrics`. ✓

## Ticker detail screen widget composition

`cockpit/screens/ticker_detail.py` composes:
- `ClockHeader`
- `TickerHeader` (id="ticker-header") ← orphaned widget
- `PriceChart` (id="price-chart") ← orphaned widget
- `OHLCTable` (id="ohlc-table") ← orphaned widget
- `IndicatorPanel` (id="indicator-panel") ← orphaned widget
- `CommandFooter`

Expected list from spec: `TickerHeader`, `OHLCTable`, `PriceChart`, `IndicatorPanel`. ✓
No unexpected widgets.

## requirements.txt lines to remove

Line 4: `mplfinance`
Line 5: `dash`
Line 6: `plotly`
Line 7: `pandas-ta`
Line 12: `textual-plotext>=1.0`

## Surprises

- `scripts/verify_session8.py` imports the four orphaned widgets. It will need to be treated as a leaf and left in place (or deleted) — it's a historical verifier script. The spec does not list it for deletion explicitly; it will remain on disk but becomes unreachable/broken after Phase 4. The Phase 3 deletion list does not include it. However, since it only imports deleted widgets, it will fail to import after Phase 4. **Resolution:** The spec says surviving scripts that are importable must pass; `verify_session8.py` is not in the verified-surviving list in Phase 5's `verify_session9.py`. It can be left as is (a dead script, like old specs in `notes/`).
- `core/__init__.py` exports `Stock` from `core.security` — no `Transaction`. No cleanup needed.
- `cockpit/widgets/__init__.py` is empty (comment only) — no widget exports to remove.
- `analysis/__init__.py` is a comment only — no exports to remove.
- No surviving production module imports from any module in the deletion list.
