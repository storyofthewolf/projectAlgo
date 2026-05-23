"""Ticker drill-down screen.

Entered via the '/' finder from any screen. Shows scalar metrics for a single
ticker. Esc returns to the previous screen.
"""
from typing import Optional

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import Screen

from cockpit.widgets.clock_header import ClockHeader
from cockpit.widgets.command_footer import CommandFooter
from cockpit.widgets.ticker_metrics_panel import TickerMetricsPanel
from workflows.ticker_metrics_snapshot import TickerMetrics, build_ticker_metrics

_COMMANDS = [
    ("ESC", "BACK"),
    ("R", "REFRESH"),
    ("/", "FIND"),
    ("T", "THEME"),
    ("?", "HELP"),
]


class TickerDetailScreen(Screen):
    """Full-screen ticker drill-down: scalar metrics panel."""

    BINDINGS = [
        Binding("escape",        "back",        "Back"),
        Binding("r",             "refresh",     "Refresh"),
        Binding("slash",         "find_ticker", "Find"),
        Binding("question_mark", "show_help",   "Help"),
        Binding("t",             "cycle_theme", "Theme"),
        Binding("q",             "quit",        "Quit", show=False),
    ]

    metrics: reactive[Optional[TickerMetrics]] = reactive(None)

    def __init__(self, ticker: str) -> None:
        super().__init__()
        self._ticker = ticker.upper()
        self._cfg = None

    def compose(self) -> ComposeResult:
        yield ClockHeader()
        yield TickerMetricsPanel(ticker=self._ticker, id="ticker-metrics")
        yield CommandFooter(_COMMANDS, id="detail-footer")

    def on_mount(self) -> None:
        self._cfg = self.app.settings.ticker_detail_config
        self.refresh_metrics()
        self.set_interval(self._cfg.refresh_interval_seconds, self.refresh_metrics)

    # ── Worker ─────────────────────────────────────────────────────────────

    @work(exclusive=True, group="ticker_metrics", thread=True)
    def refresh_metrics(self) -> None:
        snap = build_ticker_metrics(self._ticker, self._cfg)
        self.app.call_from_thread(self._set_metrics, snap)

    def _set_metrics(self, snap: TickerMetrics) -> None:
        self.metrics = snap

    # ── Reactive handler ───────────────────────────────────────────────────

    def watch_metrics(self, _old, new: Optional[TickerMetrics]) -> None:
        if new is None:
            return
        self.query_one("#ticker-metrics", TickerMetricsPanel).update_metrics(new)

    # ── Actions ────────────────────────────────────────────────────────────

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self.refresh_metrics()

    def action_find_ticker(self) -> None:
        from cockpit.screens.ticker_finder_modal import TickerFinderModal

        def _on_dismissed(ticker) -> None:
            if ticker is None:
                return
            self.app.pop_screen()
            self.app.push_screen(TickerDetailScreen(ticker))

        self.app.push_screen(TickerFinderModal(), _on_dismissed)

    def action_show_help(self) -> None:
        self.app.action_help()

    def action_cycle_theme(self) -> None:
        self.app.action_cycle_theme()

    def action_quit(self) -> None:
        self.app.action_quit()
