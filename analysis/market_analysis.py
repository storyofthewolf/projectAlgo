# projectAlgo/analysis/market_analysis.py
# Market-wide and cross-sectional analysis functions.
# All functions are stateless and operate on pandas DataFrames.

import pandas as pd
import numpy as np
from datetime import datetime


def load_aligned_returns(tickers: list, start_date: str, end_date: str,
                          interval: str = '1d', source: str = 'yfinance',
                          price_col: str = 'Close') -> pd.DataFrame:
    """
    Loads historical data for each ticker, aligns on common trading days,
    and returns a DataFrame of period returns with tickers as columns.

    Missing data at the edges is forward-filled before alignment; any dates
    still missing across any ticker are dropped so all columns are complete.

    Args:
        tickers:    List of ticker symbols.
        start_date: 'YYYY-MM-DD'
        end_date:   'YYYY-MM-DD'
        interval:   Data interval ('1d', '1wk', etc.).
        source:     'yfinance' or 'schwab'.
        price_col:  Column to use for return calculation. Default 'Close'.

    Returns:
        DataFrame with DatetimeIndex and one column per ticker of period returns.
        Tickers that could not be loaded are omitted with a warning.
    """
    from marketdata.service import get_data_service

    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()
    service = get_data_service()

    price_series = {}
    for ticker in tickers:
        try:
            df = service.get_historical_ohlcv(
                ticker, start, end, interval=interval, source=source
            )
            if df.empty:
                print(f"Warning: no data for {ticker} — skipping.")
                continue
            if price_col not in df.columns:
                print(f"Warning: '{price_col}' column missing for {ticker} — skipping.")
                continue
            price_series[ticker] = df[price_col]
        except Exception as e:
            print(f"Warning: could not load {ticker} — skipping. ({e})")
            continue

    if not price_series:
        return pd.DataFrame()

    prices = pd.DataFrame(price_series)
    prices = prices.ffill().dropna()

    returns = prices.pct_change().dropna()
    return returns


def calculate_correlation_matrix(returns: pd.DataFrame,
                                  method: str = 'pearson') -> pd.DataFrame:
    """
    Computes a pairwise correlation matrix from a returns DataFrame.

    Args:
        returns: DataFrame of period returns, one column per ticker.
        method:  'pearson' (linear), 'spearman' (rank), or 'kendall'.

    Returns:
        Square DataFrame (tickers × tickers) of correlation coefficients.
    """
    if returns.empty:
        return pd.DataFrame()
    return returns.corr(method=method)


def summarize_correlations(corr: pd.DataFrame) -> pd.DataFrame:
    """
    Returns a sorted DataFrame of unique ticker pairs with their correlation,
    useful for quickly finding the most and least correlated pairs.
    """
    if corr.empty:
        return pd.DataFrame()

    records = []
    tickers = corr.columns.tolist()
    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            records.append({
                'ticker_a': tickers[i],
                'ticker_b': tickers[j],
                'correlation': corr.iloc[i, j],
            })

    df = pd.DataFrame(records).sort_values('correlation', ascending=False)
    df = df.reset_index(drop=True)
    return df
