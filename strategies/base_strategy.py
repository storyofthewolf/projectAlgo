# projectAlgo/strategies/base_strategy.py

from abc import ABC, abstractmethod
import pandas as pd # Import pandas for type hinting

class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    Defines the interface that all concrete strategies must implement.
    """
    def __init__(self, name: str = "Unnamed Strategy"):
        self.name = name
        self._data: pd.DataFrame = pd.DataFrame() # Internal storage for processed data
        print(f"BaseStrategy '{self.name}' initialized.")

    # Renamed from 'apply_indicators' to 'calculate_indicator' to match user's preference (2025-06-12)
    @abstractmethod
    def calculate_indicator(self):
        """
        Abstract method to calculate technical indicators required by the strategy
        and add them to the self._data DataFrame.
        """
        pass

    @abstractmethod
    def generate_signals(self):
        """
        Abstract method to generate buy/sell signals based on the calculated indicators
        and add a 'signal' column (1 for buy, -1 for sell, 0 for hold) to self._data.
        """
        pass

    def get_strategy_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        This method is called by the backtesting engine. It orchestrates the
        calculation of indicators and generation of signals.
        
        Concrete strategies should implement their logic by setting self._data
        and then calling self.calculate_indicator() and self.generate_signals().
        """
        if not isinstance(data, pd.DataFrame):
            raise ValueError("Input 'data' must be a pandas DataFrame.")
        self._data = data.copy() # Ensure we work on a copy of the passed data
        
        self.calculate_indicator() # Now calls the correctly named method
        self.generate_signals()
        
        return self._data # Return the processed DataFrame
