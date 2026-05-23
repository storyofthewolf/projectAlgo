"""
Session 9 verifier — confirms the post-cleanup tree is import-clean and
the cockpit's snapshot workflows can be instantiated.

Run: python3.14 -m scripts.verify_session9

Exit code 0 = all checks passed.
Exit code 1 = at least one check failed; details printed to stdout.
"""

import sys
import traceback

CHECKS = []  # list of (name, callable) pairs


def check(name):
    """Decorator to register a check."""
    def decorator(fn):
        CHECKS.append((name, fn))
        return fn
    return decorator


# --- Imports of every surviving top-level module ---

@check("import config.settings")
def _():
    from config.settings import Settings
    Settings.load()  # confirms cockpit.toml parses


@check("import marketdata")
def _():
    from marketdata.service import get_data_service, DataService
    from marketdata.cache import LocalCache
    from marketdata.exceptions import DataSourceError
    from marketdata.sources.base import MarketDataSource
    from marketdata.sources.yfinance_source import YFinanceSource
    from marketdata.sources.schwab_source import SchwabSource


@check("import core")
def _():
    from core.security import Stock
    from core.quote import Quote
    # core.transaction should NOT be importable
    try:
        from core import transaction  # noqa: F401
        raise AssertionError("core.transaction should have been deleted")
    except ImportError:
        pass


@check("import broker")
def _():
    from broker import schwab_client
    from broker import account


@check("import analysis (trimmed)")
def _():
    from analysis.technical_analysis import calculate_sma, calculate_rsi
    from analysis.market_analysis import (
        load_aligned_returns,
        calculate_relative_strength,
        calculate_correlation_matrix,
        summarize_correlations,
    )
    # screener and performance_metrics should be gone
    for missing in ["analysis.screener", "analysis.performance_metrics"]:
        try:
            __import__(missing)
            raise AssertionError(f"{missing} should have been deleted")
        except ImportError:
            pass


@check("import workflows")
def _():
    from workflows.watchlist_snapshot import build_watchlist_snapshot
    from workflows.market_pulse_snapshot import build_pulse_snapshot
    from workflows.sector_snapshot import build_sector_snapshot
    from workflows.multi_timeframe_sector_snapshot import (
        build_multi_timeframe_sector_snapshot,
    )
    from workflows.correlation_snapshot import build_correlation_snapshot
    from workflows.ticker_metrics_snapshot import (
        build_ticker_metrics,
        TickerMetrics,
    )
    # old ticker_detail_snapshot should be gone
    try:
        import workflows.ticker_detail_snapshot  # noqa: F401
        raise AssertionError("workflows.ticker_detail_snapshot should be deleted")
    except ImportError:
        pass


@check("deleted modules are not importable")
def _():
    deleted = [
        "backtesting",
        "backtesting.engine",
        "strategies",
        "strategies.base_strategy",
        "strategies.sma_crossover",
        "visualization",
        "visualization.plot_static",
        "visualization.view_stock",
        "visualization.view_backtest",
    ]
    for mod in deleted:
        try:
            __import__(mod)
            raise AssertionError(f"{mod} should have been deleted")
        except ImportError:
            pass


@check("import cockpit app and screens")
def _():
    from cockpit.app import CockpitApp
    from cockpit.screens.home import HomeScreen
    from cockpit.screens.help import HelpScreen
    from cockpit.screens.sectors import SectorDeepDiveScreen
    from cockpit.screens.correlations import CorrelationDeepDiveScreen
    from cockpit.screens.ticker_finder_modal import TickerFinderModal
    from cockpit.screens.ticker_detail import TickerDetailScreen
    # Can instantiate the app class itself (Textual lets you do this without
    # running the event loop)
    CockpitApp()


@check("import cockpit widgets (surviving only)")
def _():
    from cockpit.widgets.clock_header import ClockHeader
    from cockpit.widgets.command_footer import CommandFooter
    from cockpit.widgets.panel_frame import PanelFrame
    from cockpit.widgets.price_cell import PriceCell
    from cockpit.widgets.pct_cell import PctCell
    from cockpit.widgets.sparkline import Sparkline
    from cockpit.widgets.watchlist_panel import WatchlistPanel
    from cockpit.widgets.market_pulse_panel import MarketPulsePanel
    from cockpit.widgets.sector_panel import SectorPanel
    from cockpit.widgets.sector_table import SectorTable
    from cockpit.widgets.correlation_panel import CorrelationPanel
    from cockpit.widgets.correlation_table import CorrelationTable
    from cockpit.widgets.ranked_pair_list import RankedPairList
    from cockpit.widgets.ticker_metrics_panel import TickerMetricsPanel
    # deleted widgets
    deleted = [
        "cockpit.widgets.ohlc_table",
        "cockpit.widgets.price_chart",
        "cockpit.widgets.indicator_panel",
        "cockpit.widgets.ticker_header",
        "cockpit.mock_data",
    ]
    for mod in deleted:
        try:
            __import__(mod)
            raise AssertionError(f"{mod} should have been deleted")
        except ImportError:
            pass


@check("import surviving scripts")
def _():
    # Importing scripts as modules confirms no syntax errors.
    # Note: some scripts have argparse at module level; import alone is fine.
    import scripts.get_data        # noqa: F401
    import scripts.account         # noqa: F401
    import scripts.quote           # noqa: F401
    import scripts.cockpit         # noqa: F401
    import scripts.schwab_auth     # noqa: F401
    import scripts.clean_data      # noqa: F401
    # scripts.run_analysis is a pre-Session-9 legacy script that references
    # core.financial_objects (removed in the original Session 1→2 refactor).
    # It was already non-functional before this cleanup session.
    # deleted scripts
    deleted = [
        "scripts.run_backtest",
        "scripts.scan",
        "scripts.correlations",
        "scripts.inspect_pickle",
    ]
    for mod in deleted:
        try:
            __import__(mod)
            raise AssertionError(f"{mod} should have been deleted")
        except ImportError:
            pass


# --- Main ---

def main():
    failures = []
    for name, fn in CHECKS:
        try:
            fn()
            print(f"  PASS  {name}")
        except Exception as exc:
            failures.append((name, exc, traceback.format_exc()))
            print(f"  FAIL  {name}: {exc}")
    print()
    print(f"{len(CHECKS) - len(failures)} / {len(CHECKS)} checks passed.")
    if failures:
        print()
        for name, _exc, tb in failures:
            print(f"--- {name} ---")
            print(tb)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
