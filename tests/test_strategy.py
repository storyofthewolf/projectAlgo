# projectAlgo/tests/test_strategy.py
import pandas as pd
import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from strategies.sma_crossover import SMACrossoverStrategy
# No fixture definitions in this file anymore, they are in conftest.py

def test_sma_crossover_strategy_init(sample_strategy_crossover_data_for_sma_3_5): # fixture from conftest.py
    strategy = SMACrossoverStrategy(sample_strategy_crossover_data_for_sma_3_5, fast_window=5, slow_window=10)
    assert strategy.fast_window == 5
    assert strategy.slow_window == 10
    assert strategy.name == "SMA Crossover (5/10)"
    assert not strategy.data.empty

def test_sma_crossover_strategy_apply_indicators(sample_strategy_crossover_data_for_sma_3_5): # fixture from conftest.py
    # Use windows (3/5) that are designed for this specific sample data
    strategy = SMACrossoverStrategy(sample_strategy_crossover_data_for_sma_3_5, fast_window=3, slow_window=5)
    strategy.apply_indicators()
    
    assert f'SMA_{strategy.fast_window}' in strategy.data.columns
    assert f'SMA_{strategy.slow_window}' in strategy.data.columns
    # Expect full original length as dropna() is removed from apply_indicators
    assert len(strategy.data) == len(sample_strategy_crossover_data_for_sma_3_5)
    # You might also want to assert that the initial rows *are* NaN
    # e.g., assert strategy.data[f'SMA_{strategy.slow_window}'].isnull().iloc[strategy.slow_window - 1] == False # first valid SMA
    # assert strategy.data[f'SMA_{strategy.slow_window}'].isnull().iloc[strategy.slow_window - 2] == True # still NaN before that

def test_sma_crossover_strategy_generate_signals(sample_strategy_crossover_data_for_sma_3_5): # fixture from conftest.py
    strategy = SMACrossoverStrategy(sample_strategy_crossover_data_for_sma_3_5, fast_window=3, slow_window=5)
    processed_df = strategy.get_strategy_data() # This calls apply_indicators and generate_signals

    assert 'signal' in processed_df.columns
    # Expect full original length as dropna() is removed from apply_indicators
    assert len(processed_df) == len(sample_strategy_crossover_data_for_sma_3_5)
    
    # Based on the new sample_strategy_crossover_data_for_sma_3_5, we expect 1 BUY and 1 SELL.
    assert (processed_df['signal'] == 1).sum() == 1 # Expect exactly one buy signal
    assert (processed_df['signal'] == -1).sum() == 1 # Expect exactly one sell signal

    # Optional: Verify specific signal dates for robustness if confident in data setup
    # buy_date = pd.Timestamp('2023-01-08') # Based on new data and 3/5 SMAs
    # sell_date = pd.Timestamp('2023-01-16') # Based on new data and 3/5 SMAs
    # assert processed_df.loc[buy_date, 'signal'] == 1
    # assert processed_df.loc[sell_date, 'signal'] == -1