"""Correlation deep-dive screen.

Press 'c' on home to enter. Keyboard-controlled method, lookback, and ticker
preset. Esc returns to home.
"""
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static

from cockpit.widgets.command_footer import CommandFooter
from cockpit.widgets.correlation_table import CorrelationTable
from cockpit.widgets.ranked_pair_list import RankedPairList
from workflows.correlation_snapshot import (
    CorrelationSnapshot,
    build_correlation_snapshot,
)

_VALID_METHODS = ("pearson", "spearman", "kendall")

_COMMANDS = [
    ("ESC", "BACK"),
    ("M", "METHOD"),
    ("[/]", "LOOKBACK"),
    ("P", "PRESET"),
    ("R", "REFRESH"),
    ("T", "THEME"),
]


class CorrelationDeepDiveScreen(Screen):
    """Full-screen correlation matrix + ranked pair list."""

    BINDINGS = [
        Binding("escape", "app.pop_screen",  "Back",      show=True),
        Binding("m",      "cycle_method",    "Method",    show=True),
        Binding("[",      "shrink_lookback", "Lookback−", show=True),
        Binding("]",      "grow_lookback",   "Lookback+", show=True),
        Binding("p",      "cycle_preset",    "Preset",    show=True),
        Binding("r",      "refresh_now",     "Refresh",   show=True),
        Binding("t",      "cycle_theme",     "Theme",     show=False),
        Binding("q",      "quit",            "Quit",      show=False),
    ]

    snapshot: reactive[CorrelationSnapshot | None] = reactive(None)

    def __init__(self) -> None:
        super().__init__()
        cfg = None  # resolved in on_mount when app is available
        self._method_index = 0
        self._lookback_index = 0
        self._preset_index = 0
        self._cfg_loaded = False

    def _load_cfg(self) -> None:
        if self._cfg_loaded:
            return
        cfg = self.app.settings.correlation_deep_dive_config
        self._methods = _VALID_METHODS
        self._method_index = list(self._methods).index(cfg.default_method)
        self._lookback_steps = cfg.lookback_options
        self._lookback_index = list(self._lookback_steps).index(cfg.default_lookback_days)
        self._preset_names = tuple(cfg.presets.keys())
        self._preset_index = list(self._preset_names).index(cfg.default_preset)
        self._cfg_loaded = True

    @property
    def _current_method(self) -> str:
        return self._methods[self._method_index]

    @property
    def _current_lookback(self) -> int:
        return self._lookback_steps[self._lookback_index]

    @property
    def _current_preset_name(self) -> str:
        return self._preset_names[self._preset_index]

    @property
    def _current_tickers(self) -> tuple:
        presets = self.app.settings.correlation_deep_dive_config.presets
        return presets[self._current_preset_name]

    def compose(self) -> ComposeResult:
        yield Static("  CORRELATIONS  ·  loading…", id="corr-dd-header")
        with Horizontal(id="corr-dd-body"):
            yield CorrelationTable(id="corr-table")
            yield RankedPairList(id="corr-pairs")
        yield CommandFooter(_COMMANDS, id="corr-dd-footer")

    def on_mount(self) -> None:
        self._load_cfg()
        self._update_header()
        self.refresh_now_work()
        self.set_interval(
            self.app.settings.correlation_deep_dive_config.refresh_interval_seconds,
            self.refresh_now_work,
        )

    def _update_header(self) -> None:
        ts = self.snapshot.as_of.strftime("%H:%M:%S") if self.snapshot else "loading…"
        method = self._current_method.capitalize()
        lookback = self._current_lookback
        preset = self._current_preset_name
        self.query_one("#corr-dd-header", Static).update(
            f"  CORRELATIONS  ·  {preset}  ·  {method}  ·  {lookback}d  ·  {ts}"
        )

    # ── Worker ────────────────────────────────────────────────────────────────

    @work(exclusive=True, group="corr_deep_dive", thread=True)
    def refresh_now_work(self) -> None:
        self._load_cfg()
        snap = build_correlation_snapshot(
            tickers=list(self._current_tickers),
            lookback_days=self._current_lookback,
            method=self._current_method,
        )
        self.app.call_from_thread(self._set_snapshot, snap)

    def _set_snapshot(self, snapshot: CorrelationSnapshot) -> None:
        self.snapshot = snapshot

    def watch_snapshot(
        self,
        old: CorrelationSnapshot | None,
        new: CorrelationSnapshot | None,
    ) -> None:
        if new is None:
            return
        self.query_one(CorrelationTable).update_snapshot(new)
        self.query_one(RankedPairList).update_snapshot(new)
        self._update_header()

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_cycle_method(self) -> None:
        self._method_index = (self._method_index + 1) % len(self._methods)
        self._update_header()
        self.refresh_now_work()

    def action_shrink_lookback(self) -> None:
        if self._lookback_index > 0:
            self._lookback_index -= 1
            self._update_header()
            self.refresh_now_work()

    def action_grow_lookback(self) -> None:
        if self._lookback_index < len(self._lookback_steps) - 1:
            self._lookback_index += 1
            self._update_header()
            self.refresh_now_work()

    def action_cycle_preset(self) -> None:
        self._preset_index = (self._preset_index + 1) % len(self._preset_names)
        self._update_header()
        self.refresh_now_work()

    def action_refresh_now(self) -> None:
        self.refresh_now_work()

    def action_cycle_theme(self) -> None:
        self.app.action_cycle_theme()

    def action_quit(self) -> None:
        self.app.action_quit()
