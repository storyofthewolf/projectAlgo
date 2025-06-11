# algo/core/technical_indicators.py

import pandas as pd
import pandas_ta as ta # Excellent library for technical indicators (you'd need to pip install pandas_ta)

def calculate_sma(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """
    Calculates Simple Moving Average (SMA) and adds it as a new column.
    Requires a 'Close' column in the DataFrame.
    """
    if 'Close' not in df.columns:
        raise ValueError("DataFrame must contain a 'Close' column to calculate SMA.")
    
    # Use pandas .rolling().mean()
    df[f'SMA{window}'] = df['Close'].rolling(window=window).mean()
    return df

def calculate_rsi(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    """
    Calculates Relative Strength Index (RSI) and adds it as a new column.
    Requires 'Close' column.
    """
    if 'Close' not in df.columns:
        raise ValueError("DataFrame must contain a 'Close' column to calculate RSI.")

    # A simple implementation for RSI (or use pandas_ta for more robust options)
    # This is a common way to calculate RSI, but pandas_ta is more robust for edge cases.
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)

    avg_gain = gain.ewm(com=window - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=window - 1, adjust=False).mean()

    rs = avg_gain / avg_loss
    df[f'RSI{window}'] = 100 - (100 / (1 + rs))

    # Or, even simpler, if you install pandas_ta:
    # df.ta.rsi(close=df['Close'], length=window, append=True) # This modifies df in place

    return df

def calculate_macd(df: pd.DataFrame, fast_window: int = 12, slow_window: int = 26, signal_window: int = 9) -> pd.DataFrame:
    """
    Calculates Moving Average Convergence Divergence (MACD).
    Requires 'Close' column.
    """
    if 'Close' not in df.columns:
        raise ValueError("DataFrame must contain a 'Close' column to calculate MACD.")

    # Using pandas_ta for robust MACD calculation
    # df.ta.macd(close=df['Close'], fast=fast_window, slow=slow_window, signal=signal_window, append=True)
    # The above would add 'MACD_12_26_9', 'MACDH_12_26_9', 'MACDS_12_26_9' columns

    # Manual calculation (simplified):
    exp1 = df['Close'].ewm(span=fast_window, adjust=False).mean()
    exp2 = df['Close'].ewm(span=slow_window, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=signal_window, adjust=False).mean()
    
    df['MACD'] = macd
    df['MACD_Signal'] = signal
    df['MACD_Hist'] = macd - signal # Histogram

    return df


# You'd add many more indicator functions here, e.g., calculate_bollinger_bands, calculate_stochastic_oscillator, etc.