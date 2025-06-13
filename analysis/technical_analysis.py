# projectAlgo/analysis/technical_analysis.py

import pandas as pd

def calculate_sma(df: pd.DataFrame, column: str = 'Close', window: int = 20) -> pd.DataFrame:
    """
    Calculates the Simple Moving Average (SMA) for a given column in a DataFrame.

    Args:
        df (pd.DataFrame): The input DataFrame.
        column (str): The column name to calculate SMA on.
        window (int): The window period for the SMA.

    Returns:
        pd.DataFrame: The DataFrame with the new SMA column added.
    """
    # Always work on a copy to prevent modifying the original DataFrame passed in,
    # and to avoid potential SettingWithCopyWarning.
    df_copy = df.copy()

    if column not in df_copy.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")
    
    if not pd.api.types.is_numeric_dtype(df_copy[column]):
        raise TypeError(f"Column '{column}' is not numeric and cannot be used for SMA calculation.")

    new_col_name = f'SMA_{window}'
    
    # Calculate the SMA and add it as a new column to the DataFrame copy
    df_copy[new_col_name] = df_copy[column].rolling(window=window).mean()

    # --- CRUCIAL: Return the modified DataFrame, not just the Series ---
    return df_copy


def calculate_rsi(df: pd.DataFrame, column: str = 'Close', window: int = 14) -> pd.DataFrame:
    """
    Calculates the Relative Strength Index (RSI) for a given column in a DataFrame.

    Args:
        df (pd.DataFrame): The input DataFrame.
        column (str): The column name to calculate RSI on.
        window (int): The window period for the RSI.

    Returns:
        pd.DataFrame: The DataFrame with the new RSI column added.
    """
    # Always work on a copy
    df_copy = df.copy()

    if column not in df_copy.columns:
        raise ValueError(f"Column '{column}' not found in DataFrame.")
    
    if not pd.api.types.is_numeric_dtype(df_copy[column]):
        raise TypeError(f"Column '{column}' is not numeric and cannot be used for RSI calculation.")

    delta = df_copy[column].diff(1)
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(com=window - 1, min_periods=window).mean()
    avg_loss = loss.ewm(com=window - 1, min_periods=window).mean()

    rs = avg_gain / avg_loss
    
    new_col_name = f'RSI_{window}'
    df_copy[new_col_name] = 100 - (100 / (1 + rs))

    # --- CRUCIAL: Return the modified DataFrame, not just the Series ---
    return df_copy

# Add other indicator functions here as you develop them