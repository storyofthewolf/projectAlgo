# projectAlgo/backtesting/engine.py

import pandas as pd
import numpy as np
import sys
import os
from math import floor

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..')
sys.path.insert(0, project_root)
# --- END PATH SETUP ---

from strategies.base_strategy import BaseStrategy
# from analysis.technical_analysis import calculate_sma # No longer needed directly here, strategy handles it
# from core.classes import Stock # No longer needed directly here, data is passed in

# --- NEW: Transaction Class ---
class Transaction:
    """
    Represents a single trade transaction (buy or sell).
    """
    def __init__(self, date, type, price, shares, cost_basis=0.0, realized_profit_loss=0.0):
        self.date = date
        self.type = type # 'BUY' or 'SELL'
        self.price = price # Executed price (includes slippage)
        self.shares = shares
        self.cost_basis = cost_basis # Total cost for BUY; Cost basis of shares sold for SELL
        self.realized_profit_loss = realized_profit_loss # Only for SELL trades

    def __repr__(self):
        return (f"Transaction(date={self.date.strftime('%Y-%m-%d')}, "
                f"type='{self.type}', price={self.price:.2f}, shares={self.shares}, "
                f"P/L={self.realized_profit_loss:.2f})")

    # This method is for converting to a dictionary, used when creating the trades_df for the dashboard
    def to_dict(self):
        return {
            'date': self.date,
            'type': self.type,
            'price': self.price,
            'shares': self.shares,
            'cost_basis': self.cost_basis,
            'profit_loss': self.realized_profit_loss
        }

class Backtester:
    """
    A simple backtesting engine to simulate trading strategies.
    Incorporates slippage and improved trade tracking (FIFO).
    """
    def __init__(self, data: pd.DataFrame, initial_capital: float = 100000.0, slippage_bps: int = 0):
        """
        Initializes the backtester.

        Args:
            data (pd.DataFrame): Historical data (OHLCV). Expected to have a DatetimeIndex.
            initial_capital (float): Starting capital for the simulation.
            slippage_bps (int): Slippage in basis points (e.g., 5 for 0.05%).
                                Applied to both buy and sell orders.
        """
        if not isinstance(data.index, pd.DatetimeIndex):
            raise ValueError("DataFrame index must be a DatetimeIndex.")
        if data.empty:
            raise ValueError("Input DataFrame is empty.")
        if not all(col in data.columns for col in ['Open', 'High', 'Low', 'Close', 'Volume']):
            raise ValueError("Input data must contain 'Open', 'High', 'Low', 'Close', 'Volume' columns.")

        self.data = data.copy() # Work on a copy to avoid modifying original
        self.initial_capital = initial_capital
        self.capital = initial_capital # Current cash balance
        self.shares_held = 0 # Total number of shares currently held
        self.equity_curve = pd.Series(dtype=float) # Stores total portfolio value over time
        self.trades = [] # List to store executed Transaction objects

        # NEW: For FIFO tracking of open positions
        # Stores tuples of (buy_date, shares_bought, price_bought)
        # This allows accurate cost basis and P&L calculation on partial sells
        self.open_positions_fifo = [] # List of {'date': date, 'shares': shares, 'price': price} dicts

        self.strategy_name = "N/A" # To store the name of the strategy being run

        # NEW: Slippage parameters
        self.slippage_bps = slippage_bps
        self.slippage_factor_buy = 1 + (self.slippage_bps / 10000) # e.g., 1.0005 for 5 bps
        self.slippage_factor_sell = 1 - (self.slippage_bps / 10000) # e.g., 0.9995 for 5 bps

        # Add a column for portfolio value to be updated daily in self.data
        self.data['portfolio_value'] = np.nan

        print(f"Backtester initialized with {len(self.data)} data points, capital ${self.initial_capital:,.2f}, slippage {self.slippage_bps} bps")

    def run_strategy(self, strategy: BaseStrategy):
        self.strategy_name = strategy.name
        print(f"\n--- Running Backtest for Strategy: {self.strategy_name} ---")

        # Get the data with indicators and signals from the strategy
        try:
            # The strategy takes self.data as input, processes it, and returns the modified DataFrame
            processed_data = strategy.get_strategy_data(self.data.copy())
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
        # This check is crucial if indicators lead to many NaNs at the start
        if self.data.empty or self.data['signal'].isnull().all():
            print("No valid signals or data points after strategy preparation (e.g., due to NaNs). Backtest aborted.")
            return None, None

        # Reset state for a new backtest run
        self.capital = self.initial_capital
        self.shares_held = 0
        self.open_positions_fifo = []
        self.trades = []
        
        # Initialize equity curve series with the same index as the data, fill with NaNs initially
        self.equity_curve = pd.Series(index=self.data.index, dtype=float)
        
        # Initial portfolio value recorded for the first day available after any NaNs
        # Find the first non-NaN signal or data point
        first_valid_idx = self.data['Close'].first_valid_index()
        if first_valid_idx is None:
            print("No valid data points found after strategy processing.")
            return None, None

        # Fill prior equity curve points with initial capital if they exist
        initial_data_index = self.data.index.get_loc(first_valid_idx)
        if initial_data_index > 0:
            self.equity_curve.iloc[:initial_data_index] = self.initial_capital

        self.equity_curve.loc[first_valid_idx] = self.initial_capital # Initial capital for first valid day
        self.data.loc[first_valid_idx, 'portfolio_value'] = self.initial_capital


        # --- Main Simulation Loop ---
        # Start loop from the first valid data point
        for i in range(initial_data_index, len(self.data)):
            current_date = self.data.index[i]
            current_close = self.data['Close'].iloc[i]
            signal = self.data['signal'].iloc[i]

            # Update portfolio value at the beginning of the day (before any trades)
            self._update_portfolio_value(current_date, current_close)

            # --- Trade Execution ---
            # BUY Logic
            if signal == 1: # Buy signal
                # Only buy if currently flat (not holding shares) OR we specifically want to average down/up
                # For this simple strategy, we assume we only open one long position at a time
                if self.shares_held == 0: 
                    self._execute_trade(current_date, 'BUY', current_close)
            
            # SELL Logic
            elif signal == -1: # Sell signal
                if self.shares_held > 0: # Only sell if currently holding shares (long position)
                    self._execute_trade(current_date, 'SELL', current_close)
            
            # Ensure equity curve is updated for every day, even if no trade.
            # The _update_portfolio_value takes care of this, but this ensures no gaps.
            if current_date not in self.equity_curve.index or pd.isna(self.equity_curve.loc[current_date]):
                 self.equity_curve.loc[current_date] = self.portfolio_value
            
            # Ensure portfolio_value column in data is updated for the current day
            self.data.loc[current_date, 'portfolio_value'] = self.portfolio_value
        
        # --- End of Backtest Liquidation ---
        # If any shares are still held at the end, liquidate them at the last price
        if self.shares_held > 0:
            last_date = self.data.index[-1]
            last_price = self.data['Close'].iloc[-1]
            print(f"Liquidating remaining {self.shares_held} shares at end of backtest ({last_date.strftime('%Y-%m-%d')}, {last_price:.2f}).")
            self._execute_trade(last_date, 'SELL', last_price)
            # Final update to equity curve after liquidation
            self._update_portfolio_value(last_date, last_price)
            self.equity_curve.loc[last_date] = self.portfolio_value # Ensure last day reflects final liquidation
            self.data.loc[last_date, 'portfolio_value'] = self.portfolio_value

        # Fill any remaining NaNs in equity_curve with the last known value (for periods before first trade)
        self.equity_curve.fillna(method='ffill', inplace=True)
        self.equity_curve.fillna(method='bfill', inplace=True) # For cases where first trade is very late

        print(f"\nBacktest finished for {self.strategy_name}.")
        final_portfolio_value = self.equity_curve.iloc[-1]
        print(f"Final Capital: ${final_portfolio_value:,.2f}")
        print(f"Total Return: {((final_portfolio_value - self.initial_capital) / self.initial_capital) * 100:.2f}%")

        # Convert list of Transaction objects to DataFrame for easier analysis
        trades_df = pd.DataFrame([t.to_dict() for t in self.trades])
        if not trades_df.empty:
            trades_df['date'] = pd.to_datetime(trades_df['date'])
            # Ensure 'cost_basis' and 'profit_loss' are numeric
            trades_df['cost_basis'] = pd.to_numeric(trades_df['cost_basis'])
            trades_df['profit_loss'] = pd.to_numeric(trades_df['profit_loss'])
            trades_df = trades_df.sort_values(by='date').reset_index(drop=True)
        
        return self.equity_curve, trades_df


    def _execute_trade(self, date, trade_type, market_price):
        """Executes a trade, applying slippage and managing open positions (FIFO)."""
        shares_to_trade_calculated = 0
        executed_price = market_price # Start with market price, then adjust for slippage
        
        if trade_type == 'BUY':
            executed_price = market_price * self.slippage_factor_buy
            # Calculate how many shares can be bought with current capital
            if executed_price > 0: # Avoid division by zero
                shares_to_trade_calculated = floor(self.capital / executed_price)
            
            if shares_to_trade_calculated > 0:
                cost = shares_to_trade_calculated * executed_price
                self.capital -= cost # Deduct cost from cash
                self.shares_held += shares_to_trade_calculated # Add shares to total held
                
                # Add to FIFO queue
                self.open_positions_fifo.append({'date': date, 'shares': shares_to_trade_calculated, 'price': executed_price})
                
                self.trades.append(Transaction(date, 'BUY', executed_price, shares_to_trade_calculated, cost_basis=cost))
                print(f"  [{date.strftime('%Y-%m-%d')}] BUY {shares_to_trade_calculated} shares at {executed_price:.2f} (Market: {market_price:.2f}). Cash: {self.capital:,.2f}, Total Shares: {self.shares_held}")
            # else: Not enough capital to buy even one share, no trade
        
        elif trade_type == 'SELL':
            if self.shares_held > 0: # Only sell if holding shares
                shares_to_sell = self.shares_held # Sell all shares held for this simple strategy
                executed_price = market_price * self.slippage_factor_sell

                total_realized_profit_loss = 0.0
                total_cost_basis_sold = 0.0
                shares_actually_sold = 0

                # Process sales from oldest open positions (FIFO)
                # Iterate through a copy of the list to allow modification during iteration
                open_positions_copy = self.open_positions_fifo[:] 
                
                for i, lot in enumerate(open_positions_copy):
                    if shares_to_sell <= 0:
                        break # All target shares sold

                    shares_from_this_lot = min(shares_to_sell, lot['shares'])
                    
                    # Calculate P&L and cost basis for this portion
                    profit_loss_this_lot = (executed_price - lot['price']) * shares_from_this_lot
                    cost_basis_this_lot = lot['price'] * shares_from_this_lot

                    total_realized_profit_loss += profit_loss_this_lot
                    total_cost_basis_sold += cost_basis_this_lot
                    shares_actually_sold += shares_from_this_lot

                    # Update the lot or remove it from the original list
                    original_lot_index = self.open_positions_fifo.index(lot) # Find original index
                    if shares_from_this_lot == lot['shares']:
                        self.open_positions_fifo.pop(original_lot_index) # Remove lot if fully sold
                    else:
                        self.open_positions_fifo[original_lot_index]['shares'] -= shares_from_this_lot # Update shares
                    
                    shares_to_sell -= shares_from_this_lot # Reduce remaining shares to sell

                self.capital += shares_actually_sold * executed_price # Add proceeds to cash
                self.shares_held -= shares_actually_sold # Reduce total shares held

                # Record the consolidated sell transaction
                self.trades.append(Transaction(date, 'SELL', executed_price, shares_actually_sold, 
                                               cost_basis=total_cost_basis_sold, 
                                               realized_profit_loss=total_realized_profit_loss))
                print(f"  [{date.strftime('%Y-%m-%d')}] SELL {shares_actually_sold} shares at {executed_price:.2f} (Market: {market_price:.2f}). P/L: {total_realized_profit_loss:.2f}. Cash: {self.capital:,.2f}, Total Shares: {self.shares_held}")
            # else: No shares held to sell, no trade

        self._update_portfolio_value(date, market_price)


    def _update_portfolio_value(self, date, current_market_price):
        """Updates the total portfolio value (cash + market value of held shares)."""
        # Note: Use market_price for valuation, not the slippage-adjusted executed_price
        current_market_value_of_holdings = self.shares_held * current_market_price
        self.portfolio_value = self.capital + current_market_value_of_holdings
        # Store in equity curve and data DataFrame
        self.equity_curve.loc[date] = self.portfolio_value


    # Example usage (for testing/demonstration) commented out as it's now handled by run_backtest_and_save.py
    '''
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

        # --- Dummy Strategy for demonstration (remains the same if needed for internal testing) ---
        class DummyStrategy(BaseStrategy):
            def __init__(self, name: str = "Dummy Strategy"): # Data is passed in get_strategy_data now
                super().__init__(name)
                self.fast_window = 10
                self.slow_window = 20

            def get_strategy_data(self, data: pd.DataFrame) -> pd.DataFrame:
                # Store data internally or directly process and return
                self._data = data.copy()
                self.calculate_indicator() # Ensure SMAs are there
                self.generate_signals()
                return self._data

            def calculate_indicator(self):
                self._data['SMA_Fast'] = self._data['Close'].rolling(window=self.fast_window).mean()
                self._data['SMA_Slow'] = self._data['Close'].rolling(window=self.slow_window).mean()
                self._data.dropna(inplace=True) # Drop NaNs created by SMAs

            def generate_signals(self):
                fast_sma = self._data['SMA_Fast']
                slow_sma = self._data['SMA_Slow']
                
                fast_sma_prev = fast_sma.shift(1)
                slow_sma_prev = slow_sma.shift(1)

                self._data['signal'] = 0

                buy_condition = (fast_sma_prev <= slow_sma_prev) & (fast_sma > slow_sma)
                self._data.loc[buy_condition, 'signal'] = 1

                sell_condition = (fast_sma_prev >= slow_sma_prev) & (fast_sma < slow_sma)
                self._data.loc[sell_condition, 'signal'] = -1
                
                position = 0
                for i in range(len(self._data)):
                    if self._data['signal'].iloc[i] == 1:
                        if position == 0:
                            position = 1
                        else:
                            self._data.loc[self._data.index[i], 'signal'] = 0
                    elif self._data['signal'].iloc[i] == -1:
                        if position == 1:
                            position = 0
                        else:
                            self._data.loc[self._data.index[i], 'signal'] = 0

                self._data.dropna(subset=['signal'], inplace=True)

                print(f"Signals after generation: Buy signals: { (self._data['signal'] == 1).sum() }, Sell signals: { (self._data['signal'] == -1).sum() }")

        # Instantiate and run backtester with dummy strategy
        backtester = Backtester(sample_data, initial_capital=100000.0, slippage_bps=5) # Now accepts slippage_bps
        dummy_strategy = DummyStrategy() # Data is passed in run_strategy now
        
        equity, trades = backtester.run_strategy(dummy_strategy)
        
        if equity is not None and trades is not None and not equity.empty:
            print("\nEquity Curve Head:")
            print(equity.head())
            print("\nEquity Curve Tail:")
            print(equity.tail())
            print("\nTrades Executed:")
            print(trades)
        else:
            print("\nBacktest returned no valid equity curve or trades.")
    '''