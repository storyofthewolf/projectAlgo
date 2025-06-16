# /projectAlgo/backtesting/engine.py

import pandas as pd
import numpy as np
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..')
sys.path.insert(0, project_root)

from strategy.base_strategy import BaseStrategy # Import the BaseStrategy
# No longer need direct import of calculate_sma, calculate_rsi here for Backtester logic
# but keep for the if __name__ block
from analysis.technical_analysis import calculate_sma # Keep for the example strategy below
from core.classes import Stock # Keep for data loading in example

class Backtester:
    """
    A simple backtesting engine to simulate trading strategies.
    """
    def __init__(self, data: pd.DataFrame, initial_capital: float = 100000.0):
        """
        Initializes the backtester.

        Args:
            data (pd.DataFrame): Historical data (OHLCV). Expected to have a DatetimeIndex.
            initial_capital (float): Starting capital for the simulation.
        """
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index must be a DatetimeIndex.")
        if data.empty:
            raise ValueError("Input DataFrame is empty.")

        self.data = data.copy() # Work on a copy to avoid modifying original
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.position = 0 # -1 for short, 0 for flat, 1 for long
        self.trades = [] # List to store executed trades
        self.equity_curve = pd.Series(dtype=float) # Stores portfolio value over time
        self.strategy_name = "N/A" # To store the name of the strategy being run

        print(f"Backtester initialized with {len(self.data)} data points and capital ${self.initial_capital:,.2f}")

    def run_strategy(self, strategy: BaseStrategy): # Changed to accept a Strategy object
        """
        Runs the backtest based on a provided strategy object.

        Args:
            strategy (BaseStrategy): An instance of a strategy class (e.g., SMACrossoverStrategy).
                                     It must have apply_indicators and generate_signals methods.
        """
        self.strategy_name = strategy.name
        print(f"\n--- Running Backtest for Strategy: {self.strategy_name} ---")

        # Get the data with indicators and signals from the strategy
        try:
            # Ensure the strategy operates on the data held by the Backtester
            # This allows the strategy to modify and return the data as needed
            strategy._data = self.data.copy() # Pass a copy of Backtester's data to strategy
            processed_data = strategy.get_strategy_data() # This will call apply_indicators and generate_signals
            self.data = processed_data.copy() # Update Backtester's data with processed_data
        except ValueError as e:
            print(f"Error preparing strategy data: {e}")
            return None, None # Indicate failure
        except Exception as e:
            print(f"An unexpected error occurred during strategy data preparation: {e}")
            return None, None

        if 'signal' not in self.data.columns:
            raise ValueError("Strategy did not generate a 'signal' column.")
        
        if self.data.empty:
            print("No data left after strategy preparation (e.g., due to NaNs). Backtest aborted.")
            return None, None

        # Reset capital and position for a new backtest run
        self.capital = self.initial_capital
        self.position = 0
        self.trades = []
        self.equity_curve = pd.Series(index=self.data.index, dtype=float)
        self.equity_curve.iloc[0] = self.initial_capital # Set initial capital

        # --- Simple Simulation Loop ---
        for i in range(1, len(self.data)):
            current_date = self.data.index[i]
            current_close = self.data['Close'].iloc[i]
            previous_close = self.data['Close'].iloc[i-1]
            signal = self.data['signal'].iloc[i] # Use the signal from the processed data

            # Calculate today's value based on yesterday's position
            # If we were holding a position yesterday, update capital based on price change
            if self.position == 1: # Long position
                # This assumes all capital is deployed and is a simplified calculation
                self.capital += (current_close - previous_close) * (self.capital / previous_close)
            # Add logic for shorting later if needed (position == -1)
            
            # --- Execute Trades based on signal ---
            if signal == 1: # Buy / Go Long
                if self.position == 0: # If currently flat, open a long position
                    self.position = 1
                    # In a real scenario, you'd track shares, fees, slippage
                    self.trades.append({
                        'date': current_date,
                        'type': 'BUY',
                        'price': current_close,
                        'capital': self.capital,
                        'position': self.position
                    })
                    print(f"  {current_date.strftime('%Y-%m-%d')}: BUY at {current_close:.2f}. Capital: {self.capital:,.2f}")
                # else: already long, do nothing or add to position (not implemented yet)
            
            elif signal == -1: # Sell / Go Flat (or go short - simpler: just go flat for now)
                if self.position == 1: # If currently long, close the position
                    self.position = 0
                    self.trades.append({
                        'date': current_date,
                        'type': 'SELL',
                        'price': current_close,
                        'capital': self.capital,
                        'position': self.position
                    })
                    print(f"  {current_date.strftime('%Y-%m-%d')}: SELL at {current_close:.2f}. Capital: {self.capital:,.2f}")
                # else: already flat or short, do nothing
            
            # Update equity curve for today
            self.equity_curve.iloc[i] = self.capital
        
        print(f"\nBacktest finished for {self.strategy_name}.")
        print(f"Final Capital: ${self.capital:,.2f}")
        print(f"Total Return: {((self.capital - self.initial_capital) / self.initial_capital) * 100:.2f}%")

        return self.equity_curve, pd.DataFrame(self.trades)
