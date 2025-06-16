# /projectAlgo/strategies/sma_crossover.py
import pandas as pd
from strategy.base_strategy import BaseStrategy # Import the base class
from analysis.technical_analysis import calculate_sma # Import indicator functions

class SMACrossoverStrategy(BaseStrategy):
    """
    A concrete strategy based on Simple Moving Average (SMA) crossover.
    Long when fast SMA crosses above slow SMA.
    Flat when fast SMA crosses below slow SMA.
    """
    def __init__(self, data: pd.DataFrame, fast_window: int = 20, slow_window: int = 50):
        super().__init__(data)
        self.name = f"SMA Crossover ({fast_window}/{slow_window})"
        self.fast_window = fast_window
        self.slow_window = slow_window

        if fast_window >= slow_window:
            raise ValueError("Fast SMA window must be smaller than Slow SMA window.")

    def apply_indicators(self):
        """
        Applies fast and slow Simple Moving Averages to the data.
        """
        print(f"Applying indicators for {self.name}...")
        # Use the calculate_sma function directly on our internal data copy
        self._data = calculate_sma(self._data, 'Close', self.fast_window)
        self._data = calculate_sma(self._data, 'Close', self.slow_window)
        # Handle NaN values that appear at the beginning due to rolling window
        self._data.dropna(inplace=True) # Drop rows with NaNs (first `slow_window` rows)
        if self._data.empty:
            raise ValueError("Data became empty after applying indicators due to NaNs. Check data length or window sizes.")
        print(f"Indicators applied. Data length: {len(self.data)}")


    def generate_signals(self) -> pd.DataFrame:
        """
        Generates buy/sell signals based on SMA crossover logic.
        """
        print(f"Generating signals for {self.name}...")
        fast_sma_col = f'SMA_{self.fast_window}'
        slow_sma_col = f'SMA_{self.slow_window}'

        if fast_sma_col not in self._data.columns or slow_sma_col not in self._data.columns:
            raise ValueError(f"Required SMA columns ({fast_sma_col}, {slow_sma_col}) not found. "
                             "Ensure apply_indicators was called.")

        self._data['signal'] = 0 # Initialize signal column

        # Calculate previous day's SMAs for crossover detection
        self._data['fast_sma_prev'] = self._data[fast_sma_col].shift(1)
        self._data['slow_sma_prev'] = self._data[slow_sma_col].shift(1)

        # Buy signal: Fast SMA crosses above Slow SMA
        buy_condition = (self._data[fast_sma_col] > self._data[slow_sma_col]) & \
                        (self._data['fast_sma_prev'] <= self._data['slow_sma_prev'])
        
        # Sell signal: Fast SMA crosses below Slow SMA
        sell_condition = (self._data[fast_sma_col] < self._data[slow_sma_col]) & \
                         (self._data['fast_sma_prev'] >= self._data['slow_sma_prev'])

        self._data.loc[buy_condition, 'signal'] = 1
        self._data.loc[sell_condition, 'signal'] = -1

        # Clean up temporary columns
        self._data = self._data.drop(columns=['fast_sma_prev', 'slow_sma_prev'])

        print(f"Signals generated. Buy signals: {(self._data['signal'] == 1).sum()}, Sell signals: {(self._data['signal'] == -1).sum()}")
        return self._data