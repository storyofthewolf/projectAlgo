from textual.reactive import reactive
from textual.widgets import Static
from cockpit.format import fmt_price


class PriceCell(Static):
    """A price cell that flashes on update then settles to directional color.

    format_func: callable(float | None) -> str, defaults to fmt_price.
    Supports yield ("4.482%") and index ("16.42") formats via PulseCell.
    """

    value: reactive[float | None] = reactive(None)

    def __init__(
        self,
        value: float | None = None,
        format_func=None,
        **kwargs,
    ):
        self._previous: float | None = None
        self._format_func = format_func if format_func is not None else fmt_price
        super().__init__(self._format_func(value), **kwargs)
        self.value = value

    def watch_value(self, new: float | None) -> None:
        self.update(self._format_func(new))

    def update_price(self, new_value: float) -> None:
        """Update displayed value; flash only when value changed from a known previous.

        First call: sets baseline without flashing (first-flash fix — AC 17).
        Subsequent calls: flash only when value differs by more than 1e-6.
        """
        if self._previous is None:
            self._previous = new_value
            self.value = new_value
            return

        if abs(new_value - self._previous) < 1e-6:
            return

        direction = "up" if new_value >= self._previous else "down"
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
