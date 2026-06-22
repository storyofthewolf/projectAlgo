from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Horizontal, Vertical

from cockpit.widgets.panel_frame import PanelFrame
from cockpit.widgets.clock_header import ClockHeader
from cockpit.widgets.command_footer import CommandFooter
from cockpit.widgets.watchlist_panel import WatchlistPanel
from cockpit.widgets.market_pulse_panel import MarketPulsePanel
from cockpit.widgets.sector_panel import SectorPanel
from cockpit.widgets.correlation_panel import CorrelationPanel
from cockpit.widgets.account_panel import AccountPanel
from cockpit.screens.sectors import SectorDeepDiveScreen
from cockpit.screens.correlations import CorrelationDeepDiveScreen
from workflows.account_snapshot import AccountSnapshot, build_account_snapshot
from workflows.watchlist_snapshot import WatchlistSnapshot, build_watchlist_snapshot
from workflows.market_pulse_snapshot import PulseSnapshot, build_pulse_snapshot
from workflows.sector_snapshot import SectorSnapshot, build_sector_snapshot
from workflows.correlation_snapshot import CorrelationSnapshot, build_correlation_snapshot

_COMMANDS = [
    ("Q", "QUIT"), ("R", "REFRESH"), ("W", "WATCHLIST"),
    ("S", "SECTORS"), ("C", "CORRELATIONS"), ("?", "HELP"), ("T", "THEME"), ("TAB", "NAV"),
]


class HomeScreen(Screen):
    """Main home screen — all panels wired to real data."""

    BINDINGS = [
        Binding("s",      "open_sector_deep_dive",     "Sectors",      show=True),
        Binding("c",      "open_correlation_deep_dive", "Correlations", show=True),
        Binding("escape", "quit",                       "",             show=False),
    ]

    # Watchlist state
    active_provider: reactive[str] = reactive('yaml')
    active_watchlist: reactive[str] = reactive('default')
    snapshot: reactive[WatchlistSnapshot | None] = reactive(None)

    # Pulse state
    pulse_snapshot: reactive[PulseSnapshot | None] = reactive(None)

    # Sector state
    sector_snapshot: reactive[SectorSnapshot | None] = reactive(None)

    # Correlation state
    correlation_snapshot: reactive[CorrelationSnapshot | None] = reactive(None)

    # Account state
    account_snapshot: reactive[AccountSnapshot | None] = reactive(None)

    def compose(self) -> ComposeResult:
        yield ClockHeader(id="clock-header")

        with Horizontal(id="top-row"):
            with PanelFrame("ACCOUNT", id="panel-account"):
                yield AccountPanel(id="account-widget")
            with PanelFrame("MARKET PULSE", id="panel-pulse"):
                yield MarketPulsePanel(
                    pulse_configs=self.app.settings.pulse_tickers,
                    id="pulse-widget",
                )

        with PanelFrame("WATCHLIST", id="panel-watchlist"):
            yield WatchlistPanel(id="watchlist-widget")

        with PanelFrame("SECTORS", id="panel-sectors"):
            yield SectorPanel(id="sectors-panel")

        with PanelFrame("CORRELATIONS", id="panel-corr"):
            yield CorrelationPanel(id="corr-panel")

        yield CommandFooter(_COMMANDS, id="command-footer")
        yield Static(
            " Please resize your terminal to at least 120×30 ",
            id="resize-warning",
        )

    def on_mount(self) -> None:
        registry = self.app.watchlist_registry
        order = registry.cycle_order()
        if order:
            self.active_provider, self.active_watchlist = order[0]

        interval = self.app.settings.refresh_interval_seconds

        self.refresh_watchlist()
        self.set_interval(interval, self.refresh_watchlist)

        self.refresh_pulse()
        self.set_interval(interval, self.refresh_pulse)

        self.refresh_sectors()
        self.set_interval(
            self.app.settings.sector_config.refresh_interval_seconds,
            self.refresh_sectors,
        )

        self.refresh_correlations()
        self.set_interval(
            self.app.settings.correlation_config.refresh_interval_seconds,
            self.refresh_correlations,
        )

        self.refresh_account()
        self.set_interval(interval, self.refresh_account)

    # ── Watchlist worker ──────────────────────────────────────────────────

    @work(exclusive=True, group="watchlist", thread=True)
    def refresh_watchlist(self) -> None:
        registry = self.app.watchlist_registry
        provider = self.active_provider
        watchlist = self.active_watchlist

        try:
            tickers = registry.get_tickers(provider, watchlist)
        except KeyError:
            order = registry.cycle_order()
            if not order:
                return
            provider, watchlist = order[0]
            tickers = registry.get_tickers(provider, watchlist)
            self.app.call_from_thread(self._set_active, provider, watchlist)

        snap = build_watchlist_snapshot(provider, watchlist, tickers)
        self.app.call_from_thread(self._set_snapshot, snap)

    def _set_active(self, provider: str, watchlist: str) -> None:
        self.active_provider = provider
        self.active_watchlist = watchlist

    def _set_snapshot(self, snapshot: WatchlistSnapshot) -> None:
        self.snapshot = snapshot

    def watch_snapshot(
        self,
        old: WatchlistSnapshot | None,
        new: WatchlistSnapshot | None,
    ) -> None:
        if new is None:
            return
        self.query_one(WatchlistPanel).update_from_snapshot(new)

    # ── Pulse worker ──────────────────────────────────────────────────────

    @work(exclusive=True, group="pulse", thread=True)
    def refresh_pulse(self) -> None:
        snap = build_pulse_snapshot(self.app.settings.pulse_tickers)
        self.app.call_from_thread(self._set_pulse_snapshot, snap)

    def _set_pulse_snapshot(self, snapshot: PulseSnapshot) -> None:
        self.pulse_snapshot = snapshot

    def watch_pulse_snapshot(
        self,
        old: PulseSnapshot | None,
        new: PulseSnapshot | None,
    ) -> None:
        if new is None:
            return
        self.query_one(MarketPulsePanel).update_snapshot(new)

    # ── Sector worker ─────────────────────────────────────────────────────

    @work(exclusive=True, group="sectors", thread=True)
    def refresh_sectors(self) -> None:
        snap = build_sector_snapshot(self.app.settings.sector_config)
        self.app.call_from_thread(self._set_sector_snapshot, snap)

    def _set_sector_snapshot(self, snapshot: SectorSnapshot) -> None:
        self.sector_snapshot = snapshot

    def watch_sector_snapshot(
        self,
        old: SectorSnapshot | None,
        new: SectorSnapshot | None,
    ) -> None:
        if new is None:
            return
        self.query_one("#sectors-panel", SectorPanel).update_snapshot(new)

    # ── Correlation worker ────────────────────────────────────────────────

    @work(exclusive=True, group="correlations", thread=True)
    def refresh_correlations(self) -> None:
        cfg = self.app.settings.correlation_config
        snap = build_correlation_snapshot(
            tickers=list(cfg.tickers),
            lookback_days=cfg.lookback_days,
            method=cfg.method,
        )
        self.app.call_from_thread(self._set_correlation_snapshot, snap)

    def _set_correlation_snapshot(self, snapshot: CorrelationSnapshot) -> None:
        self.correlation_snapshot = snapshot

    def watch_correlation_snapshot(
        self,
        old: CorrelationSnapshot | None,
        new: CorrelationSnapshot | None,
    ) -> None:
        if new is None:
            return
        self.query_one("#corr-panel", CorrelationPanel).update_snapshot(new)

    # ── Account worker ────────────────────────────────────────────────────

    @work(exclusive=True, group="account", thread=True)
    def refresh_account(self) -> None:
        snap = build_account_snapshot()
        self.app.call_from_thread(self._set_account_snapshot, snap)

    def _set_account_snapshot(self, snapshot: AccountSnapshot) -> None:
        self.account_snapshot = snapshot

    def watch_account_snapshot(
        self,
        old: AccountSnapshot | None,
        new: AccountSnapshot | None,
    ) -> None:
        if new is None:
            return
        self.query_one("#account-widget", AccountPanel).update_snapshot(new)

    # ── Refresh (r key) ───────────────────────────────────────────────────

    def action_refresh(self) -> None:
        self.app.watchlist_registry.reload_all()
        self.refresh_watchlist()
        self.refresh_pulse()
        self.refresh_sectors()
        self.refresh_correlations()
        self.refresh_account()

    def refresh_mock(self) -> None:
        self.action_refresh()

    # ── Sector deep-dive (s key) ─────────────────────────────────────────

    def action_open_sector_deep_dive(self) -> None:
        self.app.push_screen(SectorDeepDiveScreen())

    # ── Correlation deep-dive (c key) ────────────────────────────────────

    def action_open_correlation_deep_dive(self) -> None:
        self.app.push_screen(CorrelationDeepDiveScreen())

    # ── Cycle watchlist (w key) ───────────────────────────────────────────

    def action_cycle_watchlist(self) -> None:
        order = self.app.watchlist_registry.cycle_order()
        if not order:
            return
        current = (self.active_provider, self.active_watchlist)
        try:
            idx = list(order).index(current)
            next_idx = (idx + 1) % len(order)
        except ValueError:
            next_idx = 0
        self.active_provider, self.active_watchlist = order[next_idx]
        self.refresh_watchlist()
