# projectAlgo/analysis/technical_analysis.py
import pandas as pd
import numpy as np # Ensure numpy is imported for np.nan

def calculate_sma(data: pd.Series | pd.DataFrame, window: int, column: str = 'Close') -> pd.Series:
    """
    Calculates the Simple Moving Average (SMA) for a given data series or DataFrame column.

    Args:
        data (pd.Series | pd.DataFrame): The input data. Can be a Series of prices
                                          or a DataFrame containing the price column.
        window (int): The number of periods for the SMA calculation.
        column (str): The name of the column to use if 'data' is a DataFrame.
                      Defaults to 'Close'. Ignored if 'data' is a Series.

    Returns:
        pd.Series: A Series containing the calculated SMA values.
    """
    if isinstance(data, pd.DataFrame):
        if column not in data.columns:
            raise ValueError(f"Column '{column}' not found in the DataFrame.")
        series_to_calculate = data[column]
    elif isinstance(data, pd.Series):
        series_to_calculate = data
    else:
        raise TypeError("Input 'data' must be a pandas Series or DataFrame.")

    return series_to_calculate.rolling(window=window).mean()


def calculate_rsi(data: pd.Series | pd.DataFrame, window: int = 14, column: str = 'Close') -> pd.Series:
    """
    Calculates the Relative Strength Index (RSI) for a given data series or DataFrame column.

    Args:
        data (pd.Series | pd.DataFrame): The input data. Can be a Series of prices
                                          or a DataFrame containing the price column.
        window (int): The number of periods for the RSI calculation. Defaults to 14.
        column (str): The name of the column to use if 'data' is a DataFrame.
                      Defaults to 'Close'. Ignored if 'data' is a Series.

    Returns:
        pd.Series: A Series containing the calculated RSI values.
    """
    if isinstance(data, pd.DataFrame):
        if column not in data.columns:
            raise ValueError(f"Column '{column}' not found in DataFrame.")
        price_series = data[column]
    elif isinstance(data, pd.Series):
        price_series = data
    else:
        raise TypeError("Input 'data' must be a pandas Series or DataFrame.")

    if not pd.api.types.is_numeric_dtype(price_series):
        raise TypeError(f"The selected data series is not numeric and cannot be used for RSI calculation.")

    delta = price_series.diff(1)
    
    # Separate gains and losses
    # Using .clip(lower=0) ensures negative values become 0 for gains
    # Using .clip(upper=0) and then multiplying by -1 ensures positive values become 0 for losses
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Calculate exponential moving average of gains and losses
    # Using adjust=False for EMA, consistent with standard RSI calculation
    avg_gain = gain.ewm(span=window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(span=window, adjust=False, min_periods=window).mean()

    # Calculate Relative Strength (RS)
    # Handle division by zero: if avg_loss is 0, rs becomes infinity; if both are 0, rs is NaN.
    # We'll handle these edge cases for RSI directly.
    rs = avg_gain / avg_loss
    
    # Calculate RSI
    rsi = 100 - (100 / (1 + rs))

    # Handle edge cases for RSI where avg_loss or avg_gain is zero
    # If avg_loss is 0 (no losses during the window), RSI should be 100
    # If avg_gain is 0 (no gains during the window), RSI should be 0
    # Use np.inf for division by zero to map to 100 correctly via 100 / (1 + inf) = 0 -> 100 - 0 = 100
    # Use np.nan for 0/0 cases (no movement) or if there are no gains/losses after min_periods
    rsi.loc[avg_loss == 0] = 100
    rsi.loc[avg_gain == 0] = 0
    
    # Fill any remaining NaN values that might occur from initial periods or 0/0 situations not caught
    # (e.g., if first few periods have no change)
    rsi = rsi.fillna(method='ffill').fillna(method='bfill') # Or just dropna if desired
    # For RSI, it's common to have NaNs at the beginning due to 'min_periods' and 'diff'
    # These NaNs are typically dropped or left as NaNs.

    # Ensure index is maintained
    rsi.name = f'RSI_{window}' # Assign a name to the Series for clarity
    return rsi