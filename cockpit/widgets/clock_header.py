from datetime import datetime
from zoneinfo import ZoneInfo

from textual.widgets import Static

_ET = ZoneInfo("America/New_York")

_MKT_SCHEDULE = [
    ((4, 0),  (9, 30),  "PRE-MKT"),
    ((9, 30), (16, 0),  "MKT OPEN"),
    ((16, 0), (20, 0),  "AFTER-HRS"),
]


def _market_state(now_et: datetime) -> str:
    if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
        return "MKT CLOSED"
    hm = (now_et.hour, now_et.minute)
    for (sh, sm), (eh, em), label in _MKT_SCHEDULE:
        if (sh, sm) <= hm < (eh, em):
            return label
    return "MKT CLOSED"


class ClockHeader(Static):
    """Top header bar: app name | time ET | market state | data status."""

    def __init__(self, data_source: str = "yfinance", **kwargs):
        self._data_source = data_source
        super().__init__("", **kwargs)

    def on_mount(self) -> None:
        self._tick()
        self.set_interval(1, self._tick)

    def _tick(self) -> None:
        now_et = datetime.now(_ET)
        time_str = now_et.strftime("%H:%M:%S ET")
        state = _market_state(now_et)
        data_label = "[DELAYED]" if self._data_source == "yfinance" else "[REAL-TIME]"
        self.update(
            f" projectAlgo cockpit   {time_str} │ {state} │ {data_label} "
        )
