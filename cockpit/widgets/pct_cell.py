from textual.reactive import reactive
from textual.widgets import Static
from cockpit.format import fmt_pct


class PctCell(Static):
    """A percentage cell that flashes on update then settles to directional color.

    Flash direction is based on sign of the value (positive = up = green).
    """

    value: reactive[float | None] = reactive(None)

    def __init__(self, value: float | None = None, **kwargs):
        self._previous: float | None = None
        super().__init__(fmt_pct(value), **kwargs)
        self.value = value

    def watch_value(self, new: float | None) -> None:
        self.update(fmt_pct(new))

    def update_pct(self, new_value: float) -> None:
        """Update displayed value; flash only when value changed from a known previous.

        First call: sets baseline without flashing (first-flash fix — AC 17).
        """
        if self._previous is None:
            self._previous = new_value
            self.value = new_value
            return

        if abs(new_value - self._previous) < 1e-6:
            return

        direction = "up" if new_value >= 0 else "down"
        self._previous = new_value
        self.value = new_value

        flash_cls = f"flash-{direction}"
        settle_cls = f"directional-{direction}"

        self.add_class(flash_cls)
        self.remove_class("directional-up", "directional-down")

        def settle():
            self.remove_class(flash_cls)
            self.add_class(settle_cls)

        def clear():
            self.remove_class(settle_cls)

        self.set_timer(0.3, settle)
        self.set_timer(3.3, clear)
