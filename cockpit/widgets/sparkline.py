from textual.widgets import Static
from cockpit.format import make_sparkline_percentile


class Sparkline(Static):
    """Compact text-based sparkline using Unicode block characters (▁▂▃▄▅▆▇█).

    Uses percentile-based normalization so one outlier day doesn't compress
    the rest of the data into a featureless block.
    """

    def __init__(self, values: list[float], width: int = 12, **kwargs):
        self._values = list(values)
        self._width = width
        super().__init__(make_sparkline_percentile(values, width), **kwargs)

    def update_values(self, values: list[float]) -> None:
        self._values = list(values)
        self.update(make_sparkline_percentile(self._values, self._width))
