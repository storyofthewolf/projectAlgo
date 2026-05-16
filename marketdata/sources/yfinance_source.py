from datetime import date, datetime
from typing import Optional

import pandas as pd
import yfinance as yf

from core.quote import Quote
from marketdata.exceptions import DataSourceError, SourceUnavailableError
from marketdata.sources.base import MarketDataSource

_SUPPORTED_INTERVALS = {'1d', '1wk', '1mo'}


class YFinanceSource(MarketDataSource):
    """Market data source backed by yfinance."""

    @property
    def name(self) -> str:
        return 'yfinance'

    def supports_interval(self, interval: str) -> bool:
        return interval in _SUPPORTED_INTERVALS

    def is_available(self) -> bool:
        return True

    def get_historical_ohlcv(
        self,
        ticker: str,
        start: date,
        end: date,
        interval: str,
    ) -> pd.DataFrame:
        start_str = start.strftime('%Y-%m-%d')
        end_str = end.strftime('%Y-%m-%d')

        try:
            data = yf.download(
                ticker,
                start=start_str,
                end=end_str,
                interval=interval,
                progress=False,
            )
        except Exception as e:
            raise DataSourceError(f"yfinance download failed for {ticker}: {e}") from e

        if not isinstance(data, pd.DataFrame) or data.empty:
            raise DataSourceError(f"yfinance returned no data for {ticker}")

        # Flatten MultiIndex columns (yfinance returns MultiIndex for single tickers)
        if isinstance(data.columns, pd.MultiIndex):
            if ticker.upper() in data.columns.get_level_values(0):
                data = data[ticker.upper()]
            else:
                data.columns = data.columns.get_level_values(0)

        # Normalize column names to Title case
        data.columns = [col.capitalize() for col in data.columns]

        if 'Close' not in data.columns:
            raise DataSourceError(
                f"'Close' column missing after column processing for {ticker}. "
                f"Columns: {data.columns.tolist()}"
            )

        # Drop extra columns; ensure canonical order
        canonical = ['Open', 'High', 'Low', 'Close', 'Volume']
        data = data[[c for c in canonical if c in data.columns]]

        data['Close'] = pd.to_numeric(data['Close'], errors='coerce')
        data.dropna(subset=['Close'], inplace=True)

        if data.empty:
            raise DataSourceError(f"All Close values are NaN for {ticker} after cleaning")

        return data

    def get_live_quote(self, ticker: str) -> Quote:
        """Fetch most-recent bar from yfinance as a Quote.

        Note: yfinance does not provide real-time data — the price may lag
        by 15–20 minutes depending on the exchange.
        """
        try:
            t = yf.Ticker(ticker)
            info = t.fast_info
            price = float(info.last_price) if info.last_price else 0.0
            prev_close = float(info.previous_close) if info.previous_close else None
            return Quote(
                ticker=ticker,
                price=price,
                timestamp=datetime.now(),
                previous_close=prev_close,
            )
        except Exception as e:
            raise DataSourceError(f"yfinance quote failed for {ticker}: {e}") from e
