from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Quote:
    """A live or most-recent-available market quote."""
    ticker: str
    price: float
    timestamp: datetime
    bid: Optional[float] = None
    ask: Optional[float] = None
    volume: Optional[int] = None
    previous_close: Optional[float] = None

    @property
    def change(self) -> Optional[float]:
        if self.previous_close is None:
            return None
        return self.price - self.previous_close

    @property
    def change_pct(self) -> Optional[float]:
        if self.previous_close is None or self.previous_close == 0:
            return None
        return (self.price - self.previous_close) / self.previous_close
