# projectAlgo/analysis/technical_analysis.py

import pandas as pd

def calculate_sma(df, column='Close', window=20):
    """
    Calculates the Simple Moving Average (SMA) for a given DataFrame.

    Args:
        df (pd.DataFrame): The input DataFrame.
        column (str): The column name to calculate SMA on.
        window (int): The window period for the SMA.

    Returns:
        pd.Series: A Series containing the SMA values.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")
    
    # Ensure the column is numeric for calculation
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(f"Column '{column}' is not numeric and cannot be used for SMA calculation.")

    sma_series = df[column].rolling(window=window).mean()
    sma_series.name = f'SMA{window}' # Name the series for easier joining
    return sma_series

def calculate_rsi(df, column='Close', window=14):
    """
    Calculates the Relative Strength Index (RSI) for a given DataFrame.

    Args:
        df (pd.DataFrame): The input DataFrame.
        column (str): The column name to calculate RSI on.
        window (int): The window period for the RSI.

    Returns:
        pd.Series: A Series containing the RSI values.
    """
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")
    
    # Ensure the column is numeric for calculation
    if not pd.api.types.is_numeric_dtype(df[column]):
        raise TypeError(f"Column '{column}' is not numeric and cannot be used for RSI calculation.")

    delta = df[column].diff(1)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()

    rs = avg_gain / avg_loss
    rsi_series = 100 - (100 / (1 + rs))
    rsi_series.name = f'RSI{window}'
    return rsi_series

# Add other indicator functions here as you develop them