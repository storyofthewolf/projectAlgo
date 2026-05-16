from textual.reactive import reactive
from textual.widgets import Static
from cockpit.format import fmt_price


class PriceCell(Static):
    """A price cell that flashes on update then settles to directional color."""

    value: reactive[float | None] = reactive(None)

    def __init__(self, value: float | None = None, **kwargs):
        self._previous: float | None = None
        super().__init__(fmt_price(value), **kwargs)
        self.value = value

    def watch_value(self, new: float | None) -> None:
        self.update(fmt_price(new))

    def update_price(self, new_value: float) -> None:
        """Update displayed value with flash animation."""
        direction = "up" if (self._previous is None or new_value >= self._previous) else "down"
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
