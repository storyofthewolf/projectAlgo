# projectAlgo/analysis/technical_analysis.py
import pandas as pd
import numpy as np # Ensure numpy is imported for np.nan

def calculate_sma(df: pd.DataFrame, column: str = 'Close', window: int = 20) -> pd.DataFrame:
    # ... (your existing correct calculate_sma code) ...
    df_copy = df.copy()
    if column not in df_copy.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")
    if not pd.api.types.is_numeric_dtype(df_copy[column]):
        raise TypeError(f"Column '{column}' is not numeric and cannot be used for SMA calculation.")
    new_col_name = f'SMA_{window}'
    df_copy[new_col_name] = df_copy[column].rolling(window=window).mean()
    return df_copy


def calculate_rsi(df: pd.DataFrame, column: str = 'Close', window: int = 14) -> pd.DataFrame:
    """
    Calculates the Relative Strength Index (RSI) for a given column in a DataFrame.
    """
    df_copy = df.copy()
    if column not in df_copy.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")
    if not pd.api.types.is_numeric_dtype(df_copy[column]):
        raise TypeError(f"Column '{column}' is not numeric and cannot be used for RSI calculation.")

    delta = df_copy[column].diff(1)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    # Use span=window and adjust=False for standard RSI EMA calculation
    avg_gain = gain.ewm(span=window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(span=window, adjust=False, min_periods=window).mean()

    # Calculate Relative Strength (RS)
    rs = avg_gain / avg_loss
    
    new_col_name = f'RSI_{window}'
    df_copy[new_col_name] = 100 - (100 / (1 + rs))

    # Handle edge cases for RSI where avg_loss or avg_gain is zero
    # If avg_loss is 0 (no losses), RSI should be 100
    df_copy.loc[avg_loss == 0, new_col_name] = 100
    # If avg_gain is 0 (no gains), RSI should be 0
    df_copy.loc[avg_gain == 0, new_col_name] = 0

    return df_copy