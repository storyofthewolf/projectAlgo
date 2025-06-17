# projectAlgo/tests/conftest.py
import pytest
import pandas as pd

# This fixture provides generic sample data. It's the 45-point data used for test_analysis.py.
@pytest.fixture(scope="session")
def sample_dataframe():
    """
    Provides a basic DataFrame for testing indicators in analysis/technical_analysis.py.
    This is the 45-period dataset.
    """
    data = {
        'Open': [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54],
        'High': [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56],
        'Low': [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53],
        'Close': [11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55],
        'Volume': [100]*45
    }
    index = pd.date_range(start='2023-01-01', periods=len(data['Close']), freq='D')
    return pd.DataFrame(data, index=index)

# This fixture provides data specifically for the backtester's 2/4 SMA strategy.
@pytest.fixture(scope="session")
def sample_backtest_data_for_sma_2_4():
    """
    Provides a controlled DataFrame for backtesting a 2/4 SMA crossover strategy.
    Designed to produce a clear SMA crossover buy and then a sell.
    """
    data = {
        'Close': [
            10, 10, 10, 10, 10, 10, # Establish initial low, SMA2 ~= SMA4
            12, 14, 16, 18, 20, # Strong uptrend to force clear Fast > Slow for BUY
            19, 18, 17, 16, 15 # Strong downtrend to force clear Fast < Slow for SELL
        ]
    }
    data['Open'] = data['High'] = data['Low'] = data['Close'] # Simplified
    data['Volume'] = [100] * len(data['Close'])

    index = pd.date_range(start='2023-01-01', periods=len(data['Close']), freq='D')
    df = pd.DataFrame(data, index=index)
    return df

# This fixture provides data specifically for the strategy's 3/5 SMA, guaranteeing a buy and sell.
@pytest.fixture(scope="session")
def sample_strategy_crossover_data_for_sma_3_5():
    """
    Provides sample data with clear SMA 3/5 crossovers for strategy testing.
    This data is designed to generate both a buy and a sell signal.
    """
    data_for_crossovers = {
        'Close': [
            10, 10, 10, 10,  # Start flat/low
            11, 12, 13, 14, 15, 16, # Upward trend, Fast SMA will cross above Slow SMA (BUY)
            15, 14, 13, 12, 11, 10, # Downward trend, Fast SMA will cross below Slow SMA (SELL)
            11, 12, 13, 14 # End with some data
        ]
    }
    index = pd.date_range(start='2023-01-01', periods=len(data_for_crossovers['Close']), freq='D')
    return pd.DataFrame(data_for_crossovers, index=index)

# Fixtures for Backtester instance and Strategy instance, using the appropriate data.
@pytest.fixture
def initialized_backtester(sample_backtest_data_for_sma_2_4):
    from backtesting.engine import Backtester
    return Backtester(sample_backtest_data_for_sma_2_4, initial_capital=10000.0)

@pytest.fixture
def basic_sma_strategy(sample_backtest_data_for_sma_2_4):
    from strategies.sma_crossover import SMACrossoverStrategy
    # These windows (2/4) are for the backtesting test, aligned with sample_backtest_data_for_sma_2_4
    return SMACrossoverStrategy(sample_backtest_data_for_sma_2_4, fast_window=2, slow_window=4)