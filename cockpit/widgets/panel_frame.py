from textual.containers import Container
from textual.widget import Widget


class PanelFrame(Container):
    """A panel container with a Bloomberg-style title in the top border.

    Textual's built-in `border_title` property handles title-in-border rendering.
    The title is uppercased automatically.
    """

    DEFAULT_CSS = """
    PanelFrame {
        border: round $border;
        border-title-color: $primary;
        border-title-style: bold;
        padding: 0 1;
    }
    """

    def __init__(self, title: str, *children: Widget, **kwargs):
        super().__init__(*children, **kwargs)
        self.border_title = title.upper()
