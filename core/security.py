from dataclasses import dataclass, field
from typing import Optional
import pandas as pd


@dataclass
class Stock:
    """A passive data container for a tradeable security.

    This class does NOT fetch data. It is a pure data structure.
    To populate `historical_data`, use marketdata.service.DataService.
    """
    ticker: str
    historical_data: Optional[pd.DataFrame] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.ticker = self.ticker.upper()

    @property
    def has_data(self) -> bool:
        return self.historical_data is not None and not self.historical_data.empty
