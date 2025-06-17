# projectAlgo/strategies/sma_crossover.py
import pandas as pd
from strategies.base_strategy import BaseStrategy # Import the base class
from analysis.technical_analysis import calculate_sma # Import indicator functions

class SMACrossoverStrategy(BaseStrategy):
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
        print(f"\n--- Applying indicators for {self.name} ---")
        initial_data_length = len(self._data)
        print(f"Initial data length: {initial_data_length}")

        self._data = calculate_sma(self._data, 'Close', self.fast_window)
        self._data = calculate_sma(self._data, 'Close', self.slow_window)
        
        # --- CRITICAL CHANGE: REMOVE THIS LINE ---
        # self._data.dropna(inplace=True) 

        print(f"Indicators applied. Data length: {len(self._data)}")
        print("Data after indicator calculation (head):\n", self._data.head(self.slow_window + 5).to_string())
        print("Data after indicator calculation (tail):\n", self._data.tail(5).to_string())


    def generate_signals(self) -> pd.DataFrame:
        """
        Generates buy/sell signals based on SMA crossover logic.
        """
        print(f"\n--- Generating signals for {self.name} ({self.fast_window}/{self.slow_window}) ---")
        fast_sma_col = f'SMA_{self.fast_window}'
        slow_sma_col = f'SMA_{self.slow_window}'

        if fast_sma_col not in self._data.columns or slow_sma_col not in self._data.columns:
            raise ValueError(f"Required SMA columns ({fast_sma_col}, {slow_sma_col}) not found. "
                             "Ensure apply_indicators was called.")

        self._data['signal'] = 0 # Initialize signal column

        print("Data with SMAs (first few rows):")
        print(self._data[[fast_sma_col, slow_sma_col]].head(10).to_string())
        print("Data with SMAs (last few rows):")
        print(self._data[[fast_sma_col, slow_sma_col]].tail(10).to_string())

        # Calculate previous day's SMAs for crossover detection
        # Create these as temporary Series directly for conditions to avoid adding columns if not desired
        fast_sma_prev = self._data[fast_sma_col].shift(1)
        slow_sma_prev = self._data[slow_sma_col].shift(1)

        print("\nFast SMA (shifted, first 10):\n", fast_sma_prev.head(10).to_string())
        print("\nSlow SMA (shifted, first 10):\n", slow_sma_prev.head(10).to_string())
        print("\nFast SMA (shifted, last 10):\n", fast_sma_prev.tail(10).to_string())
        print("\nSlow SMA (shifted, last 10):\n", slow_sma_prev.tail(10).to_string())

        # Buy signal: Fast SMA crosses above Slow SMA
        buy_condition = (fast_sma_prev <= slow_sma_prev) & \
                        (self._data[fast_sma_col] > self._data[slow_sma_col])
        
        # Sell signal: Fast SMA crosses below Slow SMA
        sell_condition = (fast_sma_prev >= slow_sma_prev) & \
                         (self._data[fast_sma_col] < self._data[slow_sma_col])

        self._data.loc[buy_condition, 'signal'] = 1
        self._data.loc[sell_condition, 'signal'] = -1

        # NOTE: Your original code had:
        # self._data['fast_sma_prev'] = self._data[fast_sma_col].shift(1)
        # self._data['slow_sma_prev'] = self._data[slow_sma_col].shift(1)
        # self._data = self._data.drop(columns=['fast_sma_prev', 'slow_sma_prev'])
        # If you prefer to keep them as temporary columns and then drop, that's fine.
        # My current snippet uses them as local Series, which avoids adding/dropping columns.
        # Either way, the signals should be correctly generated.

        print("\nBuy Condition (Boolean Series - first 10):\n", buy_condition.head(10).to_string())
        print("Buy Condition (Boolean Series - last 10):\n", buy_condition.tail(10).to_string())
        print("\nSell Condition (Boolean Series - first 10):\n", sell_condition.head(10).to_string())
        print("Sell Condition (Boolean Series - last 10):\n", sell_condition.tail(10).to_string())

        print(f"\nSignals after generation: Buy signals: {(self._data['signal'] == 1).sum()}, Sell signals: {(self._data['signal'] == -1).sum()}")
        print("--- End Signal Generation Debug ---")
       
        return self._data