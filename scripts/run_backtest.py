# projectAlgo/scripts/run_backtest.py

import sys
import os
import pandas as pd

# Add projectAlgo root to the Python path for imports
# This ensures imports like 'backtesting.engine' and 'strategy.sma_crossover' work correctly
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..') # Go up two levels to 'projectAlgo'
sys.path.insert(0, project_root)

# Import the necessary classes/modules
from core.classes import Stock
from backtesting.engine import Backtester
from strategies.sma_crossover import SMACrossoverStrategy # Your concrete strategy

print("--- Running example backtest ---")
ticker = "MSFT"
interval = "1d"
start_date = "2023-01-01"
end_date = "2023-12-31"

# 1. Get Data
stock = Stock(ticker) 
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

df_data_for_strategy = stock.historical_data.copy()

# 2. Instantiate the Strategy
# Pass the data to the strategy at its creation
my_strategy = SMACrossoverStrategy(df_data_for_strategy, fast_window=20, slow_window=50)

# 3. Run Backtest with the strategy object
backtester = Backtester(df_data_for_strategy, initial_capital=100000)
equity_curve, trades_df = backtester.run_strategy(my_strategy)

if equity_curve is not None:
    print("\nEquity Curve Head:")
    print(equity_curve.head())
    print("\nEquity Curve Tail:")
    print(equity_curve.tail())

    if not trades_df.empty:
        print("\nTrades Executed:")
        print(trades_df)
    else:
        print("\nNo trades executed for this strategy.")
else:
    print("\nBacktest failed or returned no results.")