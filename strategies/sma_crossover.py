# projectAlgo/strategies/sma_crossover.py

import pandas as pd
import sys
import os

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..')
sys.path.insert(0, project_root)
# --- END PATH SETUP ---

from strategies.base_strategy import BaseStrategy
from analysis.technical_analysis import calculate_sma # Assuming this function exists

class SMACrossoverStrategy(BaseStrategy):
    """
    A trading strategy based on the crossover of two Simple Moving Averages.
    """
    def __init__(self, fast_window: int = 10, slow_window: int = 30, name: str = "SMA Crossover Strategy"):
        """
        Initializes the SMA Crossover Strategy.

        Args:
            fast_window (int): The window size for the faster SMA.
            slow_window (int): The window size for the slower SMA.
            name (str): The name of the strategy (e.g., "SMA Crossover (10, 30)").
        """
        super().__init__(name) # Pass the name to the BaseStrategy constructor
        self.fast_window = fast_window
        self.slow_window = slow_window
        # self._data will be set when get_strategy_data is called by the Backtester
        
        print(f"{self.name} initialized with fast_window={self.fast_window}, slow_window={self.slow_window}")


    def get_strategy_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Processes the input data by calculating indicators and generating signals.
        
        Args:
            data (pd.DataFrame): The historical OHLCV data to process.
        
        Returns:
            pd.DataFrame: The data DataFrame updated with indicators and 'signal' column.
        """
        self._data = data.copy() # Store a copy of the data internally
        self.calculate_indicator() # Renamed from apply_indicator
        self.generate_signals()
        return self._data # Return the modified DataFrame


    # Renamed from apply_indicator as per user's instruction (2025-06-12)
    def calculate_indicator(self):
        """
        Calculates the Simple Moving Average indicators and adds them to the data.
        """
        if 'Close' not in self._data.columns:
            raise ValueError("Data must contain a 'Close' column for SMA calculation.")

        # Ensure calculate_sma returns a Series, not a DataFrame
        self._data['SMA_Fast'] = calculate_sma(self._data['Close'], window=self.fast_window)
        self._data['SMA_Slow'] = calculate_sma(self._data['Close'], window=self.slow_window)
        
        # Drop rows with NaN values created by the SMA calculation
        # This ensures signals are only generated where SMAs exist
        self._data.dropna(subset=['SMA_Fast', 'SMA_Slow'], inplace=True)
        
        print(f"{self.name}: Indicators (SMA_Fast, SMA_Slow) calculated.")


    def generate_signals(self):
        """
        Generates buy (1) and sell (-1) signals based on SMA crossover.
        A signal of 0 means no action.
        """
        if 'SMA_Fast' not in self._data.columns or 'SMA_Slow' not in self._data.columns:
            raise ValueError("SMA indicators must be calculated before generating signals.")

        fast_sma = self._data['SMA_Fast']
        slow_sma = self._data['SMA_Slow']
        
        # Use .shift(1) to check previous day's crossover for signal generation on current day
        fast_sma_prev = fast_sma.shift(1)
        slow_sma_prev = slow_sma.shift(1)

        # Initialize signal column to 0
        self._data['signal'] = 0

        # Buy signal: Fast SMA crosses above Slow SMA
        # We ensure prev_day fast <= prev_day slow AND current_day fast > current_day slow
        buy_condition = (fast_sma_prev <= slow_sma_prev) & \
                        (fast_sma > slow_sma)
        self._data.loc[buy_condition, 'signal'] = 1

        # Sell signal: Fast SMA crosses below Slow SMA
        # We ensure prev_day fast >= prev_day slow AND current_day fast < current_day slow
        sell_condition = (fast_sma_prev >= slow_sma_prev) & \
                         (fast_sma < slow_sma)
        self._data.loc[sell_condition, 'signal'] = -1
        
        # Simple position management: only allow opening one long position at a time
        # And only allow selling if in a position
        current_position = 0 # 0 for flat, 1 for long
        signals = self._data['signal'].copy() # Work on a copy of signals
        
        for i in range(len(signals)):
            idx = signals.index[i]
            original_signal = signals.iloc[i]

            if original_signal == 1: # Buy signal
                if current_position == 0: # Only buy if currently flat
                    current_position = 1 # Enter long position
                else:
                    self._data.loc[idx, 'signal'] = 0 # Cancel buy signal if already in position
            elif original_signal == -1: # Sell signal
                if current_position == 1: # Only sell if in a long position
                    current_position = 0 # Exit long position
                else:
                    self._data.loc[idx, 'signal'] = 0 # Cancel sell signal if not in position
            
        # Drop any remaining NaNs in signals from shifts or indicator calculation
        self._data.dropna(subset=['signal'], inplace=True) # Ensure no NaNs in signals from shifts

        print(f"{self.name}: Signals generated. Buy signals: { (self._data['signal'] == 1).sum() }, Sell signals: { (self._data['signal'] == -1).sum() }")