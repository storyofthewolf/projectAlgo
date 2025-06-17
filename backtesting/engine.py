# projectAlgo/backtesting/engine.py

import pandas as pd
import numpy as np
import sys
import os
from math import floor # Import floor for integer share calculation

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..')
sys.path.insert(0, project_root)

from strategies.base_strategy import BaseStrategy
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
        self.capital = initial_capital # This will now represent the CASH held
        self.shares_held = 0 # Number of shares currently held in a long position
        self.position_entry_price = 0.0 # Price at which the current long position was opened (for P&L)
        self.trades = [] # List to store executed trades
        self.equity_curve = pd.Series(dtype=float) # Stores total portfolio value over time (cash + market value of shares)
        self.strategy_name = "N/A" # To store the name of the strategy being run

        print(f"Backtester initialized with {len(self.data)} data points and capital ${self.initial_capital:,.2f}")

    def run_strategy(self, strategy: BaseStrategy):
        self.strategy_name = strategy.name
        print(f"\n--- Running Backtest for Strategy: {self.strategy_name} ---")

        # Get the data with indicators and signals from the strategy
        try:
            # Pass a copy of Backtester's data to strategy. _data should be set by the strategy itself.
            # However, the strategy expects to be initialized with data.
            # Best practice is for strategy to manage its own internal data,
            # but for this setup, we'll pass it to its _data attribute just before processing.
            strategy._data = self.data.copy() # Strategy updates this internal data
            processed_data = strategy.get_strategy_data() # This will call calculate_inidcator and generate_signals
            self.data = processed_data.copy() # Update Backtester's data with processed_data (includes signals)
        except ValueError as e:
            print(f"Error preparing strategy data: {e}")
            return None, None # Indicate failure
        except Exception as e:
            print(f"An unexpected error occurred during strategy data preparation: {e}")
            return None, None

        if 'signal' not in self.data.columns:
            raise ValueError("Strategy did not generate a 'signal' column.")
        
        # Ensure that signals or data might not be present due to NaNs after indicator calculation
        if self.data.empty or self.data['signal'].isnull().all():
            print("No valid signals or data points after strategy preparation (e.g., due to NaNs). Backtest aborted.")
            return None, None

        # Reset capital, shares, and trades for a new backtest run
        self.capital = self.initial_capital # Reset cash
        self.shares_held = 0 # Reset shares held
        self.position_entry_price = 0.0 # Reset entry price for profit/loss calculation
        self.trades = [] # Clear trades list
        
        # Initialize equity curve series with the same index as the data
        self.equity_curve = pd.Series(index=self.data.index, dtype=float)

        # Set initial equity based on starting cash and (0) shares held
        # Use the close price of the first day to value shares if any were magically held
        # In this loop, we start at day 0 to process day 0's potential signals / day 0's close for portfolio val
        self.equity_curve.iloc[0] = self.capital + (self.shares_held * self.data['Close'].iloc[0])

        # --- Main Simulation Loop ---
        # Iterate through each row of the processed data (signals are already included)
        for i in range(len(self.data)):
            current_date = self.data.index[i]
            current_close = self.data['Close'].iloc[i]
            signal = self.data['signal'].iloc[i]

            # --- Trade Execution ---
            # BUY Logic
            if signal == 1: # Buy signal
                if self.shares_held == 0: # Only buy if currently flat (not holding shares)
                    shares_to_buy = floor(self.capital / current_close)
                    
                    if shares_to_buy > 0: # Ensure we can buy at least one share
                        cost = shares_to_buy * current_close
                        self.capital -= cost # Deduct cost from cash
                        self.shares_held += shares_to_buy # Add shares
                        self.position_entry_price = current_close # Record the price at which this position was opened
                        
                        self.trades.append({
                            'date': current_date,
                            'type': 'BUY',
                            'price': current_close,
                            'shares': shares_to_buy,
                            'profit_loss': 0.0 # No profit/loss realized on a buy
                        })
                        print(f"  {current_date.strftime('%Y-%m-%d')}: BUY {shares_to_buy} shares at {current_close:.2f}. Cash left: {self.capital:,.2f}. Total Portfolio: {self.capital + (self.shares_held * current_close):,.2f}")
                    # else: Not enough capital to buy even one share, remain flat
            
            # SELL Logic
            elif signal == -1: # Sell signal
                if self.shares_held > 0: # Only sell if currently holding shares (long position)
                    revenue = self.shares_held * current_close
                    
                    # Calculate realized profit/loss for this specific trade
                    realized_profit_loss = (current_close - self.position_entry_price) * self.shares_held
                    
                    self.capital += revenue # Add revenue to cash
                    
                    self.trades.append({
                        'date': current_date,
                        'type': 'SELL',
                        'price': current_close,
                        'shares': self.shares_held, # Record the total shares sold
                        'profit_loss': realized_profit_loss # Realized P&L
                    })
                    print(f"  {current_date.strftime('%Y-%m-%d')}: SELL {self.shares_held} shares at {current_close:.2f}. P/L: {realized_profit_loss:,.2f}. Cash: {self.capital:,.2f}")
                    
                    self.shares_held = 0 # Close the position
                    self.position_entry_price = 0.0 # Reset entry price
            
            # --- Update Equity Curve ---
            # The total value of the portfolio at the end of the current day
            # is cash + market value of any held shares.
            self.equity_curve.iloc[i] = self.capital + (self.shares_held * current_close)
        
        print(f"\nBacktest finished for {self.strategy_name}.")
        # Final portfolio value is the capital (cash) at the end + market value of any remaining shares.
        # Use the last close price for valuation if shares are still held at the end of the backtest.
        final_portfolio_value = self.capital + (self.shares_held * self.data['Close'].iloc[-1]) 
        print(f"Final Capital: ${final_portfolio_value:,.2f}")
        print(f"Total Return: {((final_portfolio_value - self.initial_capital) / self.initial_capital) * 100:.2f}%")

        return self.equity_curve, pd.DataFrame(self.trades)


# Example usage (for testing/demonstration)
if __name__ == '__main__':
    # Create dummy data for testing
    data_points = 50
    dates = pd.date_range(start='2023-01-01', periods=data_points, freq='D')
    close_prices = np.linspace(100, 150, data_points) + np.random.randn(data_points) * 5
    volume = np.random.randint(100000, 500000, data_points)

    sample_data = pd.DataFrame({
        'Open': close_prices - 1,
        'High': close_prices + 2,
        'Low': close_prices - 2,
        'Close': close_prices,
        'Volume': volume
    }, index=dates)

    # --- Dummy Strategy for demonstration ---
    class DummyStrategy(BaseStrategy):
        def __init__(self, data: pd.DataFrame, name: str = "Dummy Strategy"):
            super().__init__(data, name)
            self.fast_window = 10
            self.slow_window = 20

        def calculate_inidcator(self): # Renamed from apply_indicator as per user's instruction (2025-06-12)
            self._data['SMA_Fast'] = calculate_sma(self._data, window=self.fast_window)
            self._data['SMA_Slow'] = calculate_sma(self._data, window=self.slow_window)
            self._data.dropna(inplace=True) # Drop NaNs created by SMAs

        def generate_signals(self):
            # Ensure indicators are calculated first
            if 'SMA_Fast' not in self._data.columns or 'SMA_Slow' not in self._data.columns:
                self.calculate_inidcator() # Ensure SMAs are there

            fast_sma = self._data['SMA_Fast']
            slow_sma = self._data['SMA_Slow']
            
            # Use .shift(1) to check previous day's crossover for signal generation on current day
            fast_sma_prev = fast_sma.shift(1)
            slow_sma_prev = slow_sma.shift(1)

            # Initialize signal column to 0
            self._data['signal'] = 0

            # Buy signal: Fast SMA crosses above Slow SMA
            buy_condition = (fast_sma_prev <= slow_sma_prev) & \
                            (fast_sma > slow_sma)
            self._data.loc[buy_condition, 'signal'] = 1

            # Sell signal: Fast SMA crosses below Slow SMA
            sell_condition = (fast_sma_prev >= slow_sma_prev) & \
                             (fast_sma < slow_sma)
            self._data.loc[sell_condition, 'signal'] = -1
            
            # Simple position management: only allow one position at a time
            position = 0 # 0 for flat, 1 for long, -1 for short (not implemented)
            for i in range(len(self._data)):
                if self._data['signal'].iloc[i] == 1: # Buy signal
                    if position == 0: # Only buy if currently flat
                        position = 1
                    else: # Already in position, cancel buy signal
                        self._data.loc[self._data.index[i], 'signal'] = 0
                elif self._data['signal'].iloc[i] == -1: # Sell signal
                    if position == 1: # Only sell if in a long position
                        position = 0
                    else: # Not in position, cancel sell signal
                        self._data.loc[self._data.index[i], 'signal'] = 0

            # Drop initial NaNs from signals
            self._data.dropna(subset=['signal'], inplace=True) # Ensure no NaNs in signals from shifts

            print(f"Signals after generation: Buy signals: { (self._data['signal'] == 1).sum() }, Sell signals: { (self._data['signal'] == -1).sum() }")

    # Instantiate and run backtester with dummy strategy
    backtester = Backtester(sample_data, initial_capital=100000.0)
    dummy_strategy = DummyStrategy(sample_data.copy()) # Pass a copy of data to the strategy
    
    equity, trades = backtester.run_strategy(dummy_strategy)
    
    if equity is not None and trades is not None:
        print("\nEquity Curve Head:")
        print(equity.head())
        print("\nEquity Curve Tail:")
        print(equity.tail())
        print("\nTrades Executed:")
        print(trades)