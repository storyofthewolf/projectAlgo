# projectAlgo/tests/test_analysis.py

import pandas as pd
import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from analysis.technical_analysis import calculate_sma, calculate_rsi
# No fixture definitions in this file anymore, they are in conftest.py

def test_calculate_sma(sample_dataframe): # sample_dataframe from conftest.py
    df = sample_dataframe.copy()
    window = 3
    df_with_sma = calculate_sma(df, column='Close', window=window)

    assert isinstance(df_with_sma, pd.DataFrame)
    assert f'SMA_{window}' in df_with_sma.columns
    assert len(df_with_sma) == len(df)
    assert pd.isna(df_with_sma[f'SMA_{window}'].iloc[0])
    assert pd.isna(df_with_sma[f'SMA_{window}'].iloc[1])
    assert df_with_sma[f'SMA_{window}'].iloc[2] == pytest.approx((11+12+13)/3)

def test_calculate_sma_invalid_column(sample_dataframe): # sample_dataframe from conftest.py
    df = sample_dataframe.copy()
    with pytest.raises(ValueError, match="Column 'NonExistent' not found"):
        calculate_sma(df, column='NonExistent', window=3)

def test_calculate_rsi(sample_dataframe): # sample_dataframe from conftest.py
    df = sample_dataframe.copy()
    window = 14
    df_with_rsi = calculate_rsi(df, column='Close', window=window)

    assert isinstance(df_with_rsi, pd.DataFrame)
    assert f'RSI_{window}' in df_with_rsi.columns
    assert len(df_with_rsi) == len(df)
    # Assert for 13 NaNs (window - 1) based on your output, for now.
    assert df_with_rsi[f'RSI_{window}'].isnull().sum() == window - 1 
    assert (df_with_rsi[f'RSI_{window}'].dropna() >= 0).all()
    assert (df_with_rsi[f'RSI_{window}'].dropna() <= 100).all()

def test_calculate_rsi_non_numeric_column(sample_dataframe): # sample_dataframe from conftest.py
    df = sample_dataframe.copy()
    df['StringCol'] = 'abc'
    with pytest.raises(TypeError, match="Column 'StringCol' is not numeric."):
        calculate_rsi(df, column='StringCol', window=14)