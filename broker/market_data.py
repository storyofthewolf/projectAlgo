# projectAlgo/broker/market_data.py
# Fetches market data from Schwab: historical OHLCV and live quotes.
# All functions return DataFrames in the same column format as the yfinance path
# (Open, High, Low, Close, Volume with a DatetimeIndex) so downstream code is
# source-agnostic.

import pandas as pd
from datetime import datetime, timezone

from broker.schwab_client import get_client


# Maps projectAlgo interval strings to Schwab PriceHistory enum pairs:
# (period_type, period, frequency_type, frequency)
_INTERVAL_MAP = {
    '1m':  ('day',   1,  'minute',  1),
    '5m':  ('day',   5,  'minute',  5),
    '15m': ('day',  10,  'minute', 15),
    '30m': ('month', 1,  'minute', 30),
    '1h':  ('month', 1,  'minute', 30),  # closest available; Schwab has no 1h bar
    '1d':  ('year',  1,  'daily',   1),
    '1wk': ('year',  5,  'weekly',  1),
    '1mo': ('year', 20,  'monthly', 1),
}


def get_historical_ohlcv(ticker: str, start_date: str, end_date: str,
                          interval: str = '1d') -> pd.DataFrame:
    """
    Fetches historical OHLCV data from Schwab for the given ticker and date range.

    Returns a DataFrame with columns Open, High, Low, Close, Volume and a
    DatetimeIndex named 'Date', matching the yfinance output format.
    Returns an empty DataFrame on failure.
    """
    if interval not in _INTERVAL_MAP:
        print(f"Unsupported interval '{interval}' for Schwab. Supported: {list(_INTERVAL_MAP)}")
        return pd.DataFrame()

    try:
        client = get_client()
    except Exception as e:
        print(f"Schwab authentication error: {e}")
        return pd.DataFrame()

    try:
        import schwab
        period_type, period, freq_type, freq = _INTERVAL_MAP[interval]

        # Convert date strings to millisecond timestamps for the Schwab API
        start_ms = int(datetime.strptime(start_date, '%Y-%m-%d')
                       .replace(tzinfo=timezone.utc).timestamp() * 1000)
        end_ms = int(datetime.strptime(end_date, '%Y-%m-%d')
                     .replace(tzinfo=timezone.utc).timestamp() * 1000)

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

        candles = data.get('candles', [])
        if not candles:
            print(f"No Schwab candle data returned for {ticker}.")
            return pd.DataFrame()

        df = pd.DataFrame(candles)
        df['datetime'] = pd.to_datetime(df['datetime'], unit='ms', utc=True).dt.tz_localize(None)
        df = df.set_index('datetime')
        df.index.name = 'Date'
        df = df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low',
            'close': 'Close', 'volume': 'Volume'
        })
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
        print(f"Schwab: fetched {len(df)} rows for {ticker} ({interval}).")
        return df

    except Exception as e:
        print(f"Error fetching Schwab historical data for {ticker}: {e}")
        return pd.DataFrame()


def get_live_quotes(tickers: list) -> pd.DataFrame:
    """
    Fetches live quotes for a list of tickers from Schwab.

    Returns a DataFrame with columns:
        ticker, last_price, bid, ask, volume, change, change_pct
    Returns an empty DataFrame on failure.
    """
    try:
        client = get_client()
    except Exception as e:
        print(f"Schwab authentication error: {e}")
        return pd.DataFrame()

    try:
        resp = client.get_quotes(tickers)
        resp.raise_for_status()
        data = resp.json()

        rows = []
        for symbol, info in data.items():
            q = info.get('quote', {})
            rows.append({
                'ticker':     symbol,
                'last_price': q.get('lastPrice') or q.get('last', 0.0),
                'bid':        q.get('bidPrice', 0.0),
                'ask':        q.get('askPrice', 0.0),
                'volume':     q.get('totalVolume', 0),
                'change':     q.get('netChange', 0.0),
                'change_pct': q.get('netPercentChangeInDouble', 0.0),
            })

        return pd.DataFrame(rows)

    except Exception as e:
        print(f"Error fetching live quotes from Schwab: {e}")
        return pd.DataFrame()
