from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static
from textual.binding import Binding

from cockpit.widgets.panel_frame import PanelFrame
from cockpit.widgets.command_footer import CommandFooter


_HELP_TEXT = """\

  GLOBAL
    Q              QUIT
    R              REFRESH SCREEN
    ?              SHOW THIS HELP
    T              CYCLE THEME
    ESC            BACK TO PREVIOUS SCREEN
    TAB / SHIFT+TAB   FOCUS NEXT / PREVIOUS PANEL

  HOME SCREEN
    (additional bindings reserved for future sessions:
     A=ACCOUNT  S=SECTORS  C=CORRELATIONS  W=WATCHLISTS  /=FIND)

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
