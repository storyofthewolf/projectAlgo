# projectAlgo/backtesting/engine.py

import pandas as pd
import numpy as np

# For now, we will import SMA directly for a simple strategy example
# Later, we can make strategies more modular
# from analysis.technical_analysis import calculate_sma # We'll need this for a sample strategy

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

        print(f"Backtester initialized with {len(self.data)} data points and capital ${self.initial_capital:,.2f}")

    def run_strategy(self, strategy_signal_column: str = 'signal'):
        """
        Runs the backtest based on a strategy's signal column.
        Assumes signals are: 1 (buy/go long), -1 (sell/go short), 0 (flat/no change).
        For simplicity, this version assumes full position on buy/sell and no shorting initially.

        Args:
            strategy_signal_column (str): The name of the column in self.data that contains the strategy signals.
        """
        if strategy_signal_column not in self.data.columns:
            raise ValueError(f"Strategy signal column '{strategy_signal_column}' not found in data.")

        # Initialize equity curve with initial capital
        self.equity_curve = pd.Series(index=self.data.index, dtype=float)
        self.equity_curve.iloc[0] = self.initial_capital # Set initial capital

        # --- Simple Simulation Loop ---
        for i in range(1, len(self.data)):
            current_date = self.data.index[i]
            current_close = self.data['Close'].iloc[i]
            previous_close = self.data['Close'].iloc[i-1]
            signal = self.data[strategy_signal_column].iloc[i]

            # Calculate today's value based on yesterday's position
            # If we were holding a position yesterday, update capital based on price change
            if self.position == 1: # Long position
                self.capital += (current_close - previous_close) * (self.capital / previous_close) # Approximate share equivalent profit/loss
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
        
        print("\nBacktest finished.")
        print(f"Final Capital: ${self.capital:,.2f}")
        print(f"Total Return: {((self.capital - self.initial_capital) / self.initial_capital) * 100:.2f}%")

        return self.equity_curve, pd.DataFrame(self.trades) # Return equity curve and trades

# --- Example Usage (for testing the engine directly, not part of Dash yet) ---
if __name__ == "__main__":
    import os
    import sys
    # Add projectAlgo root to the Python path for local testing
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    
    from core.classes import Stock
    from analysis.technical_analysis import calculate_sma # Assuming this exists

    print("--- Running example backtest ---")
    ticker = "MSFT"
    interval = "1d"
    start_date = "2021-01-01"
    end_date = "2024-12-31"

    # 1. Get Data
    stock = Stock(ticker, interval) # If Stock init takes interval
    try:
        stock.load_local_data(start_date, end_date, interval)
        if stock.historical_data.empty:
            print(f"No local data for {ticker}, downloading...")
            stock.download_data(start_date, end_date, interval)
            if stock.historical_data.empty:
                raise ValueError("Could not get data.")
    except Exception as e:
        print(f"Error getting data: {e}")
        sys.exit(1)

    df_data = stock.historical_data.copy()

    # 2. Apply a Simple Strategy (SMA Crossover)
    # This is a very basic example: Buy when 20-day SMA crosses above 50-day SMA, Sell when it crosses below
    df_data = calculate_sma(df_data, 'Close',20)
    df_data = calculate_sma(df_data, 'Close', 50)

    # Generate a 'signal' column
    # Initialize signal to 0 (flat)
    df_data['signal'] = 0

    # Create signals:
    # Go long (1) if fast SMA crosses above slow SMA AND we were not long yesterday
    # Go flat (-1) if fast SMA crosses below slow SMA AND we were long yesterday
    # Using shift() to compare current day's close to previous day's moving averages
    df_data['sma_20_prev'] = df_data['SMA_20'].shift(1)
    df_data['sma_50_prev'] = df_data['SMA_50'].shift(1)

    # Buy signal: SMA_20 crosses above SMA_50
    # Condition: (Current SMA20 > Current SMA50) AND (Previous SMA20 <= Previous SMA50)
    buy_condition = (df_data['SMA_20'] > df_data['SMA_50']) & \
                    (df_data['sma_20_prev'] <= df_data['sma_50_prev'])
    
    # Sell signal: SMA_20 crosses below SMA_50
    # Condition: (Current SMA20 < Current SMA50) AND (Previous SMA20 >= Previous SMA50)
    sell_condition = (df_data['SMA_20'] < df_data['SMA_50']) & \
                     (df_data['sma_20_prev'] >= df_data['sma_50_prev'])

    # Apply signals
    df_data.loc[buy_condition, 'signal'] = 1
    df_data.loc[sell_condition, 'signal'] = -1

    print("\n--- Debugging Signals ---")
    print("Head of Data with Signals:")
    print(df_data[['Close', 'SMA_20', 'SMA_50', 'signal']].head(10)) # First 10 rows
    print("\nTail of Data with Signals:")
    print(df_data[['Close', 'SMA_20', 'SMA_50', 'signal']].tail(10)) # Last 10 rows
    print(f"\nTotal BUY signals (1): {(df_data['signal'] == 1).sum()}")
    print(f"Total SELL signals (-1): {(df_data['signal'] == -1).sum()}")
    print("-------------------------\n")


    # Clean up temporary columns
    df_data = df_data.drop(columns=['sma_20_prev', 'sma_50_prev'])
    
    # 3. Run Backtest
    backtester = Backtester(df_data, initial_capital=100000)
    equity_curve, trades_df = backtester.run_strategy(strategy_signal_column='signal')

    print("\nEquity Curve Head:")
    print(equity_curve.head())
    print("\nEquity Curve Tail:")
    print(equity_curve.tail())

    if not trades_df.empty:
        print("\nTrades Executed:")
        print(trades_df)
    else:
        print("\nNo trades executed for this strategy.")