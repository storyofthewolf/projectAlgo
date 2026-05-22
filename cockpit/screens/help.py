from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static
from textual.binding import Binding

from cockpit.widgets.panel_frame import PanelFrame
from cockpit.widgets.command_footer import CommandFooter


_HELP_TEXT = """\

  GLOBAL
    Q              QUIT
    R              REFRESH DATA + RELOAD CONFIG
    ?              SHOW THIS HELP
    T              CYCLE THEME
    ESC            BACK TO PREVIOUS SCREEN
    TAB / SHIFT+TAB   FOCUS NEXT / PREVIOUS PANEL

  HOME SCREEN
    S              SECTOR DEEP-DIVE (multi-timeframe RS table)
    C              CORRELATIONS DEEP-DIVE (matrix + ranked pairs)
    W              CYCLE WATCHLIST

  WATCHLIST PANEL (when focused)
    J / DOWN       SCROLL DOWN
    K / UP         SCROLL UP
    G              JUMP TO TOP
    SHIFT+G        JUMP TO BOTTOM

  SECTOR DEEP-DIVE SCREEN (s → enters, Esc → exits)
    ← →            MOVE COLUMN FOCUS
    ENTER          SORT BY FOCUSED COLUMN (toggle asc/desc if already sorted)
    R              REFRESH DATA
    ESC            BACK TO HOME

  CORRELATION DEEP-DIVE SCREEN (c → enters, Esc → exits)
    M              CYCLE METHOD (Pearson → Spearman → Kendall)
    [ / ]          DECREASE / INCREASE LOOKBACK WINDOW
    P              CYCLE TICKER PRESET
    R              REFRESH DATA
    ESC            BACK TO HOME

  RESERVED (future sessions)
    A=ACCOUNT  /=FIND TICKER

"""


class HelpScreen(Screen):
    """Keyboard help screen. Press Esc to return."""

    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back", show=False),
    ]

    def compose(self) -> ComposeResult:
        theme_names = ", ".join(self.app.theme_names)
        current = self.app.theme
        info = (
            f"  CURRENT THEME: {current}\n"
            f"  AVAILABLE: {theme_names}\n"
        )

        yield PanelFrame(
            "HELP",
            Static(_HELP_TEXT + info),
        )
        yield CommandFooter([("ESC", "BACK")])
