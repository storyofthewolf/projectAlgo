# projectAlgo/test/test_backtesting.py
import pandas as pd
import pytest
import os
import sys

# Ensure projectAlgo root is in sys.path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the necessary components
from backtesting.engine import Backtester
from strategies.base_strategy import BaseStrategy
from strategies.sma_crossover import SMACrossoverStrategy
from core.classes import Stock # For data loading convenience in test fixtures


# --- Test Cases ---

def test_backtester_initialization(initialized_backtester):
    """Verify Backtester is initialized with correct state."""
    assert initialized_backtester.initial_capital == 10000.0
    assert initialized_backtester.capital == 10000.0
    assert initialized_backtester.shares_held == 0
    assert initialized_backtester.position_entry_price == pytest.approx(0.0) # Use pytest.approx for float comparison
    assert initialized_backtester.trades == []
    assert isinstance(initialized_backtester.equity_curve, pd.Series)
    assert initialized_backtester.equity_curve.empty # Should be empty before run
    assert initialized_backtester.strategy_name == "N/A"

def test_backtester_run_simple_sma_strategy(initialized_backtester, basic_sma_strategy):
    """Test running a simple SMA crossover strategy."""
    initial_capital = initialized_backtester.initial_capital
   
    processed_strategy_data = basic_sma_strategy.get_strategy_data()
    print("\nDEBUG: DataFrame from strategy.get_strategy_data() BEFORE passing to Backtester:")
    print(processed_strategy_data[['Close', 'SMA_2', 'SMA_4', 'signal']])
    
    equity_curve, trades_df = initialized_backtester.run_strategy(basic_sma_strategy)

    assert equity_curve is not None
    assert isinstance(equity_curve, pd.Series)
    assert not equity_curve.empty
    assert equity_curve.iloc[0] == initial_capital # Equity starts at initial capital
    assert equity_curve.index.equals(initialized_backtester.data.index) # Equity curve index matches data index

    assert trades_df is not None
    assert isinstance(trades_df, pd.DataFrame)
    assert not trades_df.empty # Should have trades for this data
   
    # Expecting 2 trades: 1 BUY, 1 SELL
    assert len(trades_df) == 2
    assert trades_df['type'].iloc[0] == 'BUY'
    assert trades_df['type'].iloc[1] == 'SELL'

      # --- UPDATED EXPECTED VALUES BASED ON CORRECT TRACE (BUY at 12, SELL at 18) ---
    # Calculation:
    # Initial Capital: 10000.00
    # Shares bought: floor(10000 / 12) = 833
    # Cost: 833 * 12 = 9996
    # Cash remaining: 10000 - 9996 = 4
    # Revenue from sell: 833 * 18 = 14994
    # Final Capital: 4 + 14994 = 14998.0
    expected_final_capital = 14998.0 
    
    assert initialized_backtester.capital == pytest.approx(expected_final_capital)

     # Profit/loss for the BUY trade is 0.
    assert trades_df['profit_loss'].iloc[0] == pytest.approx(0.0)
    # Profit/loss for the SELL trade (which closes the position and realizes the profit).
    # (Sell Price - Buy Price) * Shares = (18 - 12) * 833 = 6 * 833 = 4998.0
    assert trades_df['profit_loss'].iloc[1] == pytest.approx(4998.0)

    assert equity_curve.iloc[-1] == pytest.approx(expected_final_capital)


def test_backtester_empty_data():
    """Test Backtester handles empty input data."""
    empty_df = pd.DataFrame({'Close': []}, index=pd.to_datetime([]))
    with pytest.raises(ValueError, match="Input DataFrame is empty."):
        Backtester(empty_df)

def test_backtester_strategy_no_signal_column_error():
    """Test Backtester raises error if strategy doesn't produce 'signal' column."""
    class BadStrategy(BaseStrategy):
        def apply_indicators(self):
            self._data['BadIndicator'] = self._data['Close'] * 2
        def generate_signals(self) -> pd.DataFrame:
            # Does NOT add 'signal' column
            return self._data

    data = pd.DataFrame({'Close': [1,2,3]}, index=pd.date_range('2023-01-01', periods=3))
    backtester = Backtester(data.copy(), initial_capital=1000)
    bad_strategy = BadStrategy(data.copy())

    with pytest.raises(ValueError, match="Strategy did not generate a 'signal' column."):
        backtester.run_strategy(bad_strategy)

def test_backtester_invalid_index_data():
    """Test Backtester initialization with non-DatetimeIndex."""
    df_no_datetime_index = pd.DataFrame({'Close': [10, 20]}, index=[1, 2])
    with pytest.raises(ValueError, match="DataFrame index must be a DatetimeIndex."):
        Backtester(df_no_datetime_index)