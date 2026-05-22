"""Ticker drill-down screen.

Entered via the '/' finder from any screen. Shows live quote + OHLC history
+ SMA/RSI indicators for a single ticker. Esc returns to the previous screen.
"""
import dataclasses
import subprocess
import sys
import webbrowser
from datetime import datetime
from typing import Optional

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.screen import Screen

from cockpit.widgets.clock_header import ClockHeader
from cockpit.widgets.command_footer import CommandFooter
from cockpit.widgets.indicator_panel import IndicatorPanel
from cockpit.widgets.ohlc_table import OHLCTable
from cockpit.widgets.price_chart import PriceChart
from cockpit.widgets.ticker_header import TickerHeader
from workflows.ticker_detail_snapshot import (
    TickerDetailSnapshot,
    build_ticker_detail_snapshot,
    build_ticker_quote_snapshot,
)

_COMMANDS = [
    ("ESC", "BACK"),
    ("R", "REFRESH"),
    ("/", "FIND"),
    ("P", "CHART"),
    ("J/↓", "SCROLL↓"),
    ("K/↑", "SCROLL↑"),
    ("T", "THEME"),
    ("?", "HELP"),
]

# Port for the Dash interactive chart launched via the P key.
_DASH_PORT = 8050


class TickerDetailScreen(Screen):
    """Full-screen ticker drill-down: quote, OHLC table, indicators."""

    BINDINGS = [
        Binding("escape",        "back",         "Back"),
        Binding("r",             "refresh",      "Refresh"),
        Binding("slash",         "find_ticker",  "Find"),
        Binding("p",             "open_dash_chart", "Chart"),
        Binding("j",             "scroll_down",  "Scroll ↓"),
        Binding("k",             "scroll_up",    "Scroll ↑"),
        Binding("down",          "scroll_down",  ""),
        Binding("up",            "scroll_up",    ""),
        Binding("question_mark", "show_help",    "Help"),
        Binding("t",             "cycle_theme",  "Theme"),
        Binding("q",             "quit",         "Quit", show=False),
    ]

    snapshot: reactive[Optional[TickerDetailSnapshot]] = reactive(None)

    # Shared across drill-down instances: one Dash subprocess for the whole session.
    _dash_proc: Optional[subprocess.Popen] = None

    def __init__(self, ticker: str) -> None:
        super().__init__()
        self._ticker = ticker.upper()
        self._cfg = None
        self._scroll_offset = 0

    def compose(self) -> ComposeResult:
        yield ClockHeader()
        yield TickerHeader(id="ticker-header")
        yield PriceChart(id="price-chart")
        with Horizontal(id="detail-body"):
            yield OHLCTable(id="ohlc-table")
            yield IndicatorPanel(id="indicator-panel")
        yield CommandFooter(_COMMANDS, id="detail-footer")

    def on_mount(self) -> None:
        self._cfg = self.app.settings.ticker_detail_config
        self.refresh_full()
        self.set_interval(self._cfg.quote_refresh_seconds, self.refresh_quote)

    # ── Workers ────────────────────────────────────────────────────────────────

    @work(exclusive=True, group="ticker_full", thread=True)
    def refresh_full(self) -> None:
        snap = build_ticker_detail_snapshot(self._ticker, self._cfg)
        self.app.call_from_thread(self._set_snapshot, snap)

    @work(exclusive=True, group="ticker_quote", thread=True)
    def refresh_quote(self) -> None:
        if self.snapshot is None or self.snapshot.error is not None:
            return
        quote = build_ticker_quote_snapshot(self._ticker)
        self.app.call_from_thread(self._apply_quote, quote)

    def _set_snapshot(self, snap: TickerDetailSnapshot) -> None:
        self._scroll_offset = 0
        self.snapshot = snap

    def _apply_quote(self, quote) -> None:
        if self.snapshot is None:
            return
        if quote is None:
            self.snapshot = dataclasses.replace(
                self.snapshot, quote_stale=True, timestamp=datetime.now()
            )
        else:
            new_indicators = None
            if self.snapshot.indicators is not None:
                new_indicators = self._recompute_vs_price(self.snapshot.indicators, quote.price)
            self.snapshot = dataclasses.replace(
                self.snapshot,
                quote=quote,
                quote_stale=False,
                indicators=new_indicators,
                timestamp=datetime.now(),
            )

    def _recompute_vs_price(self, indicators, price: float):
        """Update sma_vs_price_pct for new price; SMA values are unchanged."""
        new_vs = {}
        for w, sma in indicators.sma_values.items():
            if sma is not None and sma != 0:
                new_vs[w] = (price - sma) / sma * 100
            else:
                new_vs[w] = None
        return dataclasses.replace(indicators, sma_vs_price_pct=new_vs)

    # ── Reactive handler ───────────────────────────────────────────────────────

    def watch_snapshot(self, _old, new: Optional[TickerDetailSnapshot]) -> None:
        if new is None:
            return
        self.query_one("#ticker-header", TickerHeader).update_snapshot(new)
        self.query_one("#price-chart", PriceChart).update_snapshot(new)
        self.query_one("#ohlc-table", OHLCTable).update_snapshot(new, self._scroll_offset)
        self.query_one("#indicator-panel", IndicatorPanel).update_snapshot(new)

    # ── Actions ────────────────────────────────────────────────────────────────

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_refresh(self) -> None:
        self.refresh_full()

    def action_find_ticker(self) -> None:
        from cockpit.screens.ticker_finder_modal import TickerFinderModal

        def _on_dismissed(ticker) -> None:
            if ticker is None:
                return
            # Pop-then-push: replace this drill-down so Esc returns to home, not old drill-down
            self.app.pop_screen()
            self.app.push_screen(TickerDetailScreen(ticker))

        self.app.push_screen(TickerFinderModal(), _on_dismissed)

    def action_open_dash_chart(self) -> None:
        """Launch (or reuse) the Dash interactive chart for this ticker.

        The Dash app reads its initial ticker from the --ticker CLI arg, so a
        running server is tied to whichever ticker launched it. If a server is
        already up we just reopen the browser rather than spawning a duplicate.
        """
        url = f"http://127.0.0.1:{_DASH_PORT}/"
        cls = TickerDetailScreen
        proc = cls._dash_proc

        if proc is not None and proc.poll() is None:
            # Server still alive from an earlier launch — just reopen the tab.
            webbrowser.open(url)
            self.notify(f"Dash chart already running — {url}", timeout=4)
            return

        try:
            cls._dash_proc = subprocess.Popen(
                [
                    sys.executable, "-m", "visualization.view_stock",
                    "--ticker", self._ticker,
                    "--port", str(_DASH_PORT),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            self.notify(f"Could not launch Dash chart: {exc}", severity="error", timeout=6)
            return

        # Give the server a moment to bind before opening the browser.
        self.set_timer(1.5, lambda: webbrowser.open(url))
        self.notify(f"Launching Dash chart for {self._ticker} → {url}", timeout=5)

    def action_scroll_down(self) -> None:
        if self.snapshot is None or self.snapshot.history is None:
            return
        max_offset = max(0, len(self.snapshot.history) - self._cfg.history_display_days)
        self._scroll_offset = min(self._scroll_offset + 1, max_offset)
        self.query_one("#ohlc-table", OHLCTable).update_snapshot(self.snapshot, self._scroll_offset)

    def action_scroll_up(self) -> None:
        self._scroll_offset = max(0, self._scroll_offset - 1)
        if self.snapshot is not None:
            self.query_one("#ohlc-table", OHLCTable).update_snapshot(self.snapshot, self._scroll_offset)

    def action_show_help(self) -> None:
        self.app.action_help()

    def action_cycle_theme(self) -> None:
        self.app.action_cycle_theme()

    def action_quit(self) -> None:
        self.app.action_quit()
