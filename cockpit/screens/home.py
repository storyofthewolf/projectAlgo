from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Horizontal, Vertical

from cockpit import mock_data as md
from cockpit.format import (
    fmt_pct, fmt_arrow, fmt_ticker,
    fmt_yield, make_sparkline, fmt_corr,
)
from cockpit.themes import THEMES_CONFIG
from cockpit.widgets.panel_frame import PanelFrame
from cockpit.widgets.clock_header import ClockHeader
from cockpit.widgets.command_footer import CommandFooter
from cockpit.widgets.watchlist_panel import WatchlistPanel
from cockpit.widgets.market_pulse_panel import MarketPulsePanel
from cockpit.widgets.sector_panel import SectorPanel
from cockpit.screens.sectors import SectorDeepDiveScreen
from workflows.watchlist_snapshot import WatchlistSnapshot, build_watchlist_snapshot
from workflows.market_pulse_snapshot import PulseSnapshot, build_pulse_snapshot
from workflows.sector_snapshot import SectorSnapshot, build_sector_snapshot

_COMMANDS = [
    ("Q", "QUIT"), ("R", "REFRESH"), ("W", "WATCHLIST"),
    ("S", "SECTORS"), ("?", "HELP"), ("T", "THEME"), ("TAB", "NAV"),
]


def _corr_color(v: float, cfg: dict) -> str:
    if abs(v - 1.0) < 1e-9:
        return cfg["text_dim"]
    if v >= 0.7:
        return cfg["primary"]
    if v >= 0.3:
        return cfg["secondary"]
    if v > -0.3:
        return cfg["text_dim"]
    return cfg["negative"]


def _render_correlations(
    tickers: list[str],
    corr_rows: list[tuple],
    theme_cfg: dict | None = None,
) -> str:
    header = "         " + "".join(f"{t:>7}" for t in tickers)
    rows = [header]
    for row_ticker, values in corr_rows:
        cells = []
        for v in values:
            cell_str = f"{fmt_corr(v):>7}"
            if theme_cfg:
                color = _corr_color(v, theme_cfg)
                cells.append(f"[{color}]{cell_str}[/{color}]")
            else:
                cells.append(cell_str)
        rows.append(f" {row_ticker:<7} " + "".join(cells))
    return "\n".join(rows)


class HomeScreen(Screen):
    """Main home screen — watchlist + pulse + sectors wired to real data; corr still mock."""

    BINDINGS = [
        Binding("s", "open_sector_deep_dive", "Sectors", show=True),
    ]

    # Watchlist state
    active_provider: reactive[str] = reactive('yaml')
    active_watchlist: reactive[str] = reactive('default')
    snapshot: reactive[WatchlistSnapshot | None] = reactive(None)

    # Pulse state
    pulse_snapshot: reactive[PulseSnapshot | None] = reactive(None)

    # Sector state
    sector_snapshot: reactive[SectorSnapshot | None] = reactive(None)

    def _theme_cfg(self) -> dict:
        theme = self.app.theme if self.app.theme in THEMES_CONFIG else "claude-warm"
        return THEMES_CONFIG[theme]

    def compose(self) -> ComposeResult:
        data = md.regenerate_mock()
        self._current_mock = data
        cfg = self._theme_cfg()

        yield ClockHeader(id="clock-header")

        with Horizontal(id="top-row"):
            with PanelFrame("ACCOUNT", id="panel-account"):
                yield Static(
                    "\n Schwab not connected.\n\n"
                    " Run:\n"
                    "  python -m\n"
                    "  scripts.schwab_auth\n\n"
                    " See CLAUDE.md\n"
                    " for setup.",
                    id="account-content",
                )
            with PanelFrame("MARKET PULSE", id="panel-pulse"):
                yield MarketPulsePanel(
                    pulse_configs=self.app.settings.pulse_tickers,
                    id="pulse-widget",
                )

        with PanelFrame("WATCHLIST", id="panel-watchlist"):
            yield WatchlistPanel(id="watchlist-widget")

        with Horizontal(id="bottom-row"):
            with PanelFrame("SECTOR HEATMAP", id="panel-sectors"):
                yield SectorPanel(id="sectors-panel")
            with PanelFrame("CORRELATIONS (30D, HOLDINGS)", id="panel-corr"):
                yield Static(
                    _render_correlations(md.WATCHLIST_TICKERS, data["corr"], cfg),
                    id="corr-content",
                )

        yield CommandFooter(_COMMANDS, id="command-footer")
        yield Static(
            " Please resize your terminal to at least 120×30 ",
            id="resize-warning",
        )

    def on_mount(self) -> None:
        # Sync active watchlist from registry default
        registry = self.app.watchlist_registry
        order = registry.cycle_order()
        if order:
            self.active_provider, self.active_watchlist = order[0]

        interval = self.app.settings.refresh_interval_seconds

        # Watchlist: initial fetch + polling
        self.refresh_watchlist()
        self.set_interval(interval, self.refresh_watchlist)

        # Pulse: initial fetch + polling (independent timer)
        self.refresh_pulse()
        self.set_interval(interval, self.refresh_pulse)

        # Sectors: initial fetch + polling (independent timer, longer interval)
        self.refresh_sectors()
        self.set_interval(
            self.app.settings.sector_config.refresh_interval_seconds,
            self.refresh_sectors,
        )

    # ── Watchlist worker ──────────────────────────────────────────────────

    @work(exclusive=True, thread=True)
    def refresh_watchlist(self) -> None:
        """Fetch watchlist snapshot in a thread so network I/O doesn't block UI."""
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

    @work(exclusive=True, thread=True)
    def refresh_pulse(self) -> None:
        """Fetch pulse snapshot in a thread, independent of the watchlist worker."""
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
        """Fetch sector snapshot in a thread, independent of other workers."""
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

    # ── Refresh (r key) ───────────────────────────────────────────────────

    def action_refresh(self) -> None:
        """Full refresh: reload YAML config, re-fetch watchlist + pulse + sector data."""
        self.app.watchlist_registry.reload_all()
        self._refresh_mock_panels()
        self.refresh_watchlist()
        self.refresh_pulse()
        self.refresh_sectors()

    def refresh_mock(self) -> None:
        self.action_refresh()

    def _refresh_mock_panels(self) -> None:
        """Refresh panels still on mock data (correlations only; sectors wired to real data)."""
        data = md.regenerate_mock()
        self._current_mock = data
        cfg = self._theme_cfg()
        self.query_one("#corr-content", Static).update(
            _render_correlations(md.WATCHLIST_TICKERS, data["corr"], cfg)
        )

    # ── Sector deep-dive (s key) ─────────────────────────────────────────

    def action_open_sector_deep_dive(self) -> None:
        """Push the sector deep-dive screen."""
        self.app.push_screen(SectorDeepDiveScreen())

    # ── Cycle watchlist (w key) ───────────────────────────────────────────

    def action_cycle_watchlist(self) -> None:
        """Cycle to the next (provider, watchlist) pair."""
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
