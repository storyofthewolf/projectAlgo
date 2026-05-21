"""Sector deep-dive screen — multi-timeframe RS table accessed via 's' from home."""
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static

from cockpit.widgets.command_footer import CommandFooter
from cockpit.widgets.sector_table import SectorTable
from workflows.multi_timeframe_sector_snapshot import (
    MultiTimeframeSectorSnapshot,
    build_multi_timeframe_sector_snapshot,
)

_COMMANDS = [
    ("ESC", "BACK"),
    ("R", "REFRESH"),
    ("← →", "MOVE COL"),
    ("ENTER", "SORT"),
    ("?", "HELP"),
    ("T", "THEME"),
]


class SectorDeepDiveScreen(Screen):
    """Full-screen sector relative-strength table. Press Esc to return to home."""

    BINDINGS = [
        Binding("escape",       "app.pop_screen", "Back",    show=True),
        Binding("r",            "refresh",         "Refresh", show=True),
        Binding("left",         "focus_prev",      "← Col",   show=True),
        Binding("right",        "focus_next",      "→ Col",   show=True),
        Binding("enter",        "apply_sort",      "Sort",    show=True),
        Binding("question_mark","help",            "Help",    show=False),
        Binding("t",            "cycle_theme",     "Theme",   show=False),
        Binding("q",            "quit",            "Quit",    show=False),
    ]

    snapshot: reactive[MultiTimeframeSectorSnapshot | None] = reactive(None)

    def compose(self) -> ComposeResult:
        config = self.app.settings.sector_deep_dive_config
        n_tf = len(config.timeframes)
        yield Static(
            f"  SECTOR DEEP-DIVE  ·  {n_tf} timeframes  ·  loading…",
            id="deep-dive-header",
        )
        yield SectorTable(
            initial_sort_column=config.default_sort_column,
            initial_sort_direction=config.default_sort_direction,
            id="sector-table",
        )
        yield CommandFooter(_COMMANDS, id="deep-dive-footer")

    def on_mount(self) -> None:
        self.refresh_sectors_deep()
        self.set_interval(
            self.app.settings.sector_deep_dive_config.refresh_interval_seconds,
            self.refresh_sectors_deep,
        )

    # ── Worker ────────────────────────────────────────────────────────────

    @work(exclusive=True, group="sector_deep_dive", thread=True)
    def refresh_sectors_deep(self) -> None:
        """Fetch multi-timeframe snapshot in a thread."""
        snap = build_multi_timeframe_sector_snapshot(
            timeframes=self.app.settings.sector_deep_dive_config.timeframes,
            sector_config=self.app.settings.sector_config,
        )
        self.app.call_from_thread(self._set_snapshot, snap)

    def _set_snapshot(self, snapshot: MultiTimeframeSectorSnapshot) -> None:
        self.snapshot = snapshot

    def watch_snapshot(
        self,
        old: MultiTimeframeSectorSnapshot | None,
        new: MultiTimeframeSectorSnapshot | None,
    ) -> None:
        if new is None:
            return
        self.query_one(SectorTable).snapshot = new
        ts = new.timestamp.strftime("%H:%M:%S")
        n_tf = len(new.timeframe_labels)
        self.query_one("#deep-dive-header", Static).update(
            f"  SECTOR DEEP-DIVE  ·  {n_tf} timeframes  ·  as of {ts}"
        )

    # ── Keystroke actions (delegate to SectorTable) ───────────────────────

    def action_refresh(self) -> None:
        self.refresh_sectors_deep()

    def action_focus_prev(self) -> None:
        self.query_one(SectorTable).focus_prev_column()

    def action_focus_next(self) -> None:
        self.query_one(SectorTable).focus_next_column()

    def action_apply_sort(self) -> None:
        self.query_one(SectorTable).apply_sort()

    def action_help(self) -> None:
        self.app.action_help()

    def action_cycle_theme(self) -> None:
        self.app.action_cycle_theme()

    def action_quit(self) -> None:
        self.app.action_quit()
