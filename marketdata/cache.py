from datetime import date, timedelta
from pathlib import Path
from typing import Optional
import pandas as pd

# A requested start/end date can fall on a weekend/holiday with no trading
# data, so the stored range's first/last row legitimately sits a few calendar
# days inside the requested window. Treat the range as covering the request
# when the gap is within this many days — it is non-trading days, not missing
# data. 4 days spans a Fri→Mon weekend plus an adjacent holiday.
_EDGE_GRACE_DAYS = 4


class LocalCache:
    """CSV-based local cache for OHLCV data, keyed by (ticker, interval).

    One canonical file per ticker+interval — ``{TICKER}_{interval}.csv`` —
    holding the widest date range fetched so far. This lets overlapping
    requests hit the cache: a window anchored on a slightly different date
    is served by slicing the stored file rather than re-downloading.

    Behavior:
    - get(): if the stored file fully covers [start, end], slice and return
      that window. If the file is missing or its range doesn't cover the
      request, return None (a miss — caller fetches fresh).
    - put(): merge the new data into the stored file (union of date ranges,
      new rows win on overlap), so the cache widens over time.

    The legacy dated filename scheme (``{TICKER}_{interval}_{start}_{end}.csv``)
    is no longer read or written; old files are inert and may be deleted.
    """

    def __init__(self, cache_dir: Path):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _filename(self, ticker: str, interval: str) -> Path:
        return self.cache_dir / f"{ticker.upper()}_{interval}.csv"

    def _load(self, ticker: str, interval: str) -> Optional[pd.DataFrame]:
        """Load the full stored DataFrame for a ticker+interval, or None."""
        path = self._filename(ticker, interval)
        if not path.exists():
            return None
        df = pd.read_csv(path, index_col=0, parse_dates=True)
        if df.empty:
            return None
        return df.sort_index()

    def get(
        self, ticker: str, interval: str, start: date, end: date
    ) -> Optional[pd.DataFrame]:
        """Return cached rows for [start, end] if the stored file covers it."""
        df = self._load(ticker, interval)
        if df is None:
            return None

        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
        grace = timedelta(days=_EDGE_GRACE_DAYS)

        # The stored range must span the whole request to count as a hit.
        # Both edges get a grace window: if the requested start/end lands on a
        # non-trading day, the first/last stored row legitimately sits a few
        # days inside the window — that is still full coverage, not a gap.
        if df.index.min() > start_ts + grace:
            return None
        if df.index.max() < end_ts - grace:
            return None

        window = df.loc[(df.index >= start_ts) & (df.index <= end_ts)]
        if window.empty:
            return None
        return window.copy()

    def put(
        self,
        ticker: str,
        interval: str,
        start: date,
        end: date,
        df: pd.DataFrame,
    ) -> Path:
        """Merge df into the stored file for this ticker+interval.

        start/end are accepted for signature compatibility with the previous
        cache; the merge uses the DataFrame's own index, so they are unused.
        """
        path = self._filename(ticker, interval)
        existing = self._load(ticker, interval)

        if existing is None:
            merged = df.sort_index()
        else:
            # Union of both indexes; new rows win where dates overlap.
            combined = pd.concat([existing, df])
            merged = combined[~combined.index.duplicated(keep="last")].sort_index()

        merged.to_csv(path)
        return path

    def has(self, ticker: str, interval: str, start: date, end: date) -> bool:
        """True if the cache can fully serve [start, end] from stored data."""
        return self.get(ticker, interval, start, end) is not None
