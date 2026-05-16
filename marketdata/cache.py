from datetime import date
from pathlib import Path
from typing import Optional
import pandas as pd


class LocalCache:
    """CSV-based local cache for OHLCV data.

    File naming convention (unchanged from previous data_manager):
        {TICKER}_{interval}_{YYYYMMDD}_{YYYYMMDD}.csv

    Behavior:
    - If the exact file exists, load and return it.
    - If not, return None.
    - Writing always overwrites.
    - No smart invalidation in this session (TODO for future).
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _filename(self, ticker: str, interval: str, start: date, end: date) -> Path:
        s = start.strftime('%Y%m%d')
        e = end.strftime('%Y%m%d')
        return self.cache_dir / f"{ticker.upper()}_{interval}_{s}_{e}.csv"

    def get(
        self, ticker: str, interval: str, start: date, end: date
    ) -> Optional[pd.DataFrame]:
        path = self._filename(ticker, interval, start, end)
        if not path.exists():
            return None
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        return df

    def put(
        self,
        ticker: str,
        interval: str,
        start: date,
        end: date,
        df: pd.DataFrame,
    ) -> Path:
        path = self._filename(ticker, interval, start, end)
        df.to_csv(path)
        return path

    def has(self, ticker: str, interval: str, start: date, end: date) -> bool:
        return self._filename(ticker, interval, start, end).exists()
