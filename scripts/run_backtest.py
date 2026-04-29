# projectAlgo/run_backtest.py

import sys
import os
import pandas as pd
import pickle # For saving/loading Python objects
import subprocess # For launching the dashboard
from datetime import datetime # For unique filename suffix
from backtesting.engine import Backtester
from strategies.sma_crossover import SMACrossoverStrategy
from core.financial_objects import Stock # Ensure Stock is imported from here
from analysis.performance_metrics import analyze_backtest_results

# --- Configuration for Backtest ---
TICKER_SYMBOL = "ISRG"
START_DATE = "2024-01-01"
END_DATE = "2025-01-01"
INTERVAL = "1h"
INITIAL_CAPITAL = 100000.0
SLIPPAGE_BPS = 5 # 5 basis points = 0.05%

# Strategy Parameters (for SMA Crossover)
FAST_WINDOW = 50
SLOW_WINDOW = 200
STRATEGY_NAME = "SMA Crossover Strategy" # Descriptive name

# --- Path Setup ---
# Calculate project_root by going up one level from 'scripts' directory
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# Assuming run_backtest.py is in projectAlgo/scripts/
project_root = os.path.abspath(os.path.join(current_script_dir, '..'))
sys.path.insert(0, project_root) # Add projectAlgo root to system path

# --- Define where to save results and historical data ---
# Now, results_dir is relative to project_root, which is correct
results_dir = os.path.join(project_root, 'data', 'backtest_results')
os.makedirs(results_dir, exist_ok=True) # Ensure the directory exists

# NEW: Define absolute path for historical data
HISTORICAL_DATA_DIR = os.path.join(project_root, 'data', 'historical_data')
os.makedirs(HISTORICAL_DATA_DIR, exist_ok=True) # Ensure historical data directory exists

# Create a unique filename for the results using a timestamp
date_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
results_filename = f"{STRATEGY_NAME.replace(' ', '_').replace('(', '').replace(')', '')}_{TICKER_SYMBOL}_{date_suffix}.pkl"
results_filepath = os.path.join(results_dir, results_filename)

print(f"Results will be saved to: {results_filepath}")
print(f"Historical data will be managed in: {HISTORICAL_DATA_DIR}")

# --- 1. Load Real Data ---
print(f"Loading data for {TICKER_SYMBOL} from {START_DATE} to {END_DATE} ({INTERVAL})...")
stock = Stock(TICKER_SYMBOL)
try:
    # Attempt to load local data first, explicitly passing the correct directory
    print(f"Attempting to load local data for {TICKER_SYMBOL} from {START_DATE} to {END_DATE} ({INTERVAL}) from {HISTORICAL_DATA_DIR}...")
    # MODIFIED CALL: Pass HISTORICAL_DATA_DIR
    stock.load_local_data(START_DATE, END_DATE, INTERVAL, data_dir=HISTORICAL_DATA_DIR)
    
    if stock.historical_data.empty:
        print(f"No local data found for {TICKER_SYMBOL}. Downloading data...")
        # MODIFIED CALL: Pass HISTORICAL_DATA_DIR
        stock.download_data(START_DATE, END_DATE, INTERVAL, data_dir=HISTORICAL_DATA_DIR)
        if stock.historical_data.empty:
            raise ValueError(f"Could not retrieve any data for {TICKER_SYMBOL}.")
except Exception as e:
    print(f"Failed to load/download data for {TICKER_SYMBOL}: {e}")
    sys.exit(1)

data = stock.historical_data.copy()
if data.empty:
    print(f"No valid historical data retrieved for {TICKER_SYMBOL}. Exiting.")
    sys.exit(1)

print(f"Data loaded successfully. Shape: {data.shape}")

# --- 2. Instantiate Backtester and Strategy ---
backtester = Backtester(data, initial_capital=INITIAL_CAPITAL, slippage_bps=SLIPPAGE_BPS)
strategy = SMACrossoverStrategy(fast_window=FAST_WINDOW, slow_window=SLOW_WINDOW, name=STRATEGY_NAME)

# --- 3. Run Backtest ---
print(f"Running backtest with {STRATEGY_NAME}...")
equity_curve, trades_df = backtester.run_strategy(strategy)

# --- 4. Calculate Performance Metrics ---
print("Calculating performance metrics...")
performance_metrics = analyze_backtest_results(equity_curve, trades_df, INITIAL_CAPITAL)

# --- 5. Prepare Results for Saving ---
backtest_results = {
    'equity_curve': equity_curve,
    'trades_df': trades_df,
    'processed_data': backtester.data, # This contains OHLC, indicators, and signals
    'performance_metrics': performance_metrics,
    'strategy_name': STRATEGY_NAME,
    'initial_capital': INITIAL_CAPITAL,
    'slippage_bps': SLIPPAGE_BPS,
    'fast_window': FAST_WINDOW,
    'slow_window': SLOW_WINDOW,
    'ticker_symbol': TICKER_SYMBOL,
    'start_date': START_DATE,
    'end_date': END_DATE,
    'interval': INTERVAL
}

# --- 6. Save Results to File ---
print(f"Saving backtest results to: {results_filepath}")
try:
    with open(results_filepath, 'wb') as f:
        pickle.dump(backtest_results, f)
    print("Results saved successfully.")
except Exception as e:
    print(f"Error saving results: {e}")
    sys.exit(1)

