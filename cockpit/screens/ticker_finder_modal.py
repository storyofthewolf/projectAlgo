"""Ticker finder modal.

Centered modal that accepts a ticker symbol and returns it (upper-cased)
on Enter, or None on Esc. Launched globally via the '/' binding.
"""
import re

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Input, Static


_TICKER_RE = re.compile(r"^[A-Z0-9.\-=^]{1,12}$")


def _is_valid_ticker(s: str) -> bool:
    return bool(_TICKER_RE.match(s))


class TickerFinderModal(ModalScreen):
    """Centered modal accepting a ticker symbol.

    Returns the validated ticker (upper-cased) or None on Esc.
    """

    BINDINGS = [("escape", "cancel", "Cancel")]

    AUTO_FOCUS = "#finder-input"

    def compose(self) -> ComposeResult:
        with Container(id="finder-box"):
            yield Static("FIND TICKER", id="finder-title")
            yield Input(placeholder="ticker symbol…", id="finder-input")

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus_input)

    def _focus_input(self) -> None:
        self.set_focus(self.query_one("#finder-input", Input))

    def on_screen_resume(self) -> None:
        # Re-assert focus whenever this screen becomes active again.
        self.set_focus(self.query_one("#finder-input", Input))

    def on_input_submitted(self, event: Input.Submitted) -> None:
        raw = event.value.strip().upper()
        if not raw:
            return
        if not _is_valid_ticker(raw):
            return
        self.dismiss(raw)

    def action_cancel(self) -> None:
        self.dismiss(None)
