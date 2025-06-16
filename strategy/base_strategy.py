# /projectAlgo/strategy/base_strategy.py

from abc import ABC, abstractmethod
import pandas as pd
import numpy as np
import sys
import os

# Add projectAlgo root to the Python path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..')
sys.path.insert(0, project_root)

# Import necessary functions from your analysis module
from analysis.technical_analysis import calculate_sma, calculate_rsi # etc.

class BaseStrategy(ABC):
    """
    Abstract Base Class for all trading strategies.
    Concrete strategies must implement apply_indicators and generate_signals.
    """
    def __init__(self, data: pd.DataFrame):
        if not isinstance(data, pd.DataFrame) or data.empty:
            raise ValueError("Strategy requires a non-empty Pandas DataFrame.")
        self._data = data.copy() # Store a copy of the data internally
        self.name = "Base Strategy" # Default name, can be overridden

    @property
    def data(self) -> pd.DataFrame:
        """Provides access to the strategy's internal data."""
        return self._data

    @abstractmethod
    def apply_indicators(self):
        """
        Applies all necessary technical indicators to the strategy's data.
        Modifies self._data in-place by adding new indicator columns.
        """
        pass

    @abstractmethod
    def generate_signals(self) -> pd.DataFrame:
        """
        Generates buy (1), sell (-1), or no-position (0) signals based on the applied indicators.
        Adds a 'signal' column to self._data.

        Returns:
            pd.DataFrame: The DataFrame with the 'signal' column added.
        """
        pass

    def get_strategy_data(self) -> pd.DataFrame:
        """
        Executes the full strategy logic and returns the data with indicators and signals.
        """
        self.apply_indicators()
        return self.generate_signals()


