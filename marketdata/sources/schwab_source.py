from datetime import date, datetime, timezone

import pandas as pd

from core.quote import Quote
from marketdata.exceptions import DataSourceError, SourceUnavailableError, UnsupportedIntervalError
from marketdata.sources.base import MarketDataSource

# Maps projectAlgo interval strings to Schwab PriceHistory enum pairs:
# (period_type, period, frequency_type, frequency)
_INTERVAL_MAP = {
    '1m':  ('day',    1, 'minute',  1),
    '5m':  ('day',    5, 'minute',  5),
    '15m': ('day',   10, 'minute', 15),
    '30m': ('month',  1, 'minute', 30),
    '1h':  ('month',  1, 'minute', 30),  # closest available; Schwab has no 1h bar
    '1d':  ('year',   1, 'daily',   1),
    '1wk': ('year',   5, 'weekly',  1),
    '1mo': ('year',  20, 'monthly', 1),
}

_SUPPORTED_INTERVALS = set(_INTERVAL_MAP.keys())


class SchwabSource(MarketDataSource):
    """Market data source backed by the Schwab API."""

    @property
    def name(self) -> str:
        return 'schwab'

    def supports_interval(self, interval: str) -> bool:
        return interval in _SUPPORTED_INTERVALS

    def is_available(self) -> bool:
        """Return True only if Schwab credentials exist and a token file is present.

        Must NOT raise — returns False for any unavailability condition.
        """
        try:
            from broker.schwab_client import is_authenticated
            return is_authenticated()
        except Exception:
            return False

    def get_historical_ohlcv(
        self,
        ticker: str,
        start: date,
        end: date,
        interval: str,
    ) -> pd.DataFrame:
        if interval not in _INTERVAL_MAP:
            raise UnsupportedIntervalError(
                f"Schwab does not support interval '{interval}'. "
                f"Supported: {sorted(_SUPPORTED_INTERVALS)}"
            )

        if not self.is_available():
            raise SourceUnavailableError(
                "Schwab is not authenticated. Run 'python -m scripts.schwab_auth' first."
            )

        try:
            from broker.schwab_client import get_client
            import schwab
            client = get_client()
        except Exception as e:
            raise SourceUnavailableError(f"Schwab authentication error: {e}") from e

        try:
            period_type, period, freq_type, freq = _INTERVAL_MAP[interval]

            start_ms = int(
                datetime.combine(start, datetime.min.time())
                .replace(tzinfo=timezone.utc).timestamp() * 1000
            )
            end_ms = int(
                datetime.combine(end, datetime.min.time())
                .replace(tzinfo=timezone.utc).timestamp() * 1000
            )

            PH = schwab.client.Client.PriceHistory
            freq_type_enum = getattr(PH.FrequencyType, freq_type.upper())
            period_type_enum = getattr(PH.PeriodType, period_type.upper())

            resp = client.get_price_history(
                ticker,
                period_type=period_type_enum,
                frequency_type=freq_type_enum,
                frequency=freq,
                start_datetime=start_ms,
                end_datetime=end_ms,
                need_extended_hours_data=False,
            )
            resp.raise_for_status()
            data = resp.json()

        except SourceUnavailableError:
            raise
        except Exception as e:
            raise DataSourceError(f"Schwab historical fetch failed for {ticker}: {e}") from e

        candles = data.get('candles', [])
        if not candles:
            raise DataSourceError(f"Schwab returned no candle data for {ticker}")

        df = pd.DataFrame(candles)
        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms', utc=True).dt.tz_localize(None)
        df = df.set_index('datetime')
        df.index.name = 'Date'
        df = df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low',
            'close': 'Close', 'volume': 'Volume',
        })
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        return df

    def get_live_quote(self, ticker: str) -> Quote:
        if not self.is_available():
            raise SourceUnavailableError(
                "Schwab is not authenticated. Run 'python -m scripts.schwab_auth' first."
            )

        try:
            from broker.schwab_client import get_client
            client = get_client()
        except Exception as e:
            raise SourceUnavailableError(f"Schwab authentication error: {e}") from e

        try:
            resp = client.get_quotes([ticker])
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            raise DataSourceError(f"Schwab quote fetch failed for {ticker}: {e}") from e

        info = data.get(ticker, {})
        q = info.get('quote', {})
        price = float(q.get('lastPrice') or q.get('last', 0.0))
        prev_close_raw = q.get('closePrice') or q.get('regularMarketPreviousClose')
        prev_close = float(prev_close_raw) if prev_close_raw is not None else None

        return Quote(
            ticker=ticker,
            price=price,
            timestamp=datetime.now(),
            bid=float(q.get('bidPrice', 0.0)),
            ask=float(q.get('askPrice', 0.0)),
            volume=int(q.get('totalVolume', 0)),
            previous_close=prev_close,
        )
