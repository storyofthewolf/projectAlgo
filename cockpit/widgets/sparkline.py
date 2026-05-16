from textual.widgets import Static
from cockpit.format import make_sparkline


class Sparkline(Static):
    """A compact text-based sparkline using Unicode block characters (▁▂▃▄▅▆▇█)."""

    def __init__(self, values: list[float], width: int = 10, **kwargs):
        self._values = values
        self._width = width
        super().__init__(make_sparkline(values, width), **kwargs)

    def update_values(self, values: list[float]) -> None:
        self._values = values
        self.update(make_sparkline(values, self._width))
