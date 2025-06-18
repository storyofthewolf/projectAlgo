# projectAlgo/scripts/run_backtest_and_save.py

import sys
import os
import pandas as pd
import pickle # For saving/loading Python objects
import subprocess # For launching the dashboard
from datetime import datetime # For unique filename suffix

# --- PATH SETUP for projectAlgo root ---
# Calculate project_root by going up one level from 'scripts' directory
current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_script_dir, '..')
sys.path.insert(0, project_root) # Add projectAlgo root to system path
# --- END PATH SETUP ---

from backtesting.engine import Backtester
from strategies.sma_crossover import SMACrossoverStrategy
from core.classes import Stock # For loading real data
from analysis.performance_metrics import analyze_backtest_results

# --- Configuration for Backtest ---
TICKER_SYMBOL = "AAPL"
START_DATE = "2023-01-01"
END_DATE = "2024-12-31"
INTERVAL = "1d"
INITIAL_CAPITAL = 100000.0
SLIPPAGE_BPS = 5 # 5 basis points = 0.05%

# Strategy Parameters (for SMA Crossover)
FAST_WINDOW = 10
SLOW_WINDOW = 30
STRATEGY_NAME = "SMA Crossover Strategy (AAPL)" # Descriptive name

# --- Define where to save results ---
# Now, results_dir is relative to project_root, which is correct
results_dir = os.path.join(project_root, 'data', 'backtest_results')
os.makedirs(results_dir, exist_ok=True) # Ensure the directory exists

# Create a unique filename for the results using a timestamp
date_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
results_filename = f"backtest_results_{STRATEGY_NAME.replace(' ', '_').replace('(', '').replace(')', '')}_{date_suffix}.pkl"
results_filepath = os.path.join(results_dir, results_filename)

print(f"Results will be saved to: {results_filepath}")

# --- 1. Load Real Data ---
print(f"Loading data for {TICKER_SYMBOL} from {START_DATE} to {END_DATE} ({INTERVAL})...")
stock = Stock(TICKER_SYMBOL)
try:
    # Attempt to load local data first
    stock.load_local_data(START_DATE, END_DATE, INTERVAL)
    if stock.historical_data.empty:
        print(f"No local data found for {TICKER_SYMBOL}. Downloading data...")
        stock.download_data(START_DATE, END_DATE, INTERVAL)
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

# --- 7. Optionally Launch the Dashboard ---
print(f"\nLaunching backtest dashboard with results from: {results_filepath}")
# Dashboard script path is also now relative to project_root
dashboard_script_path = os.path.join(project_root, 'visualization', 'backtest_dashboard_app.py')

if not os.path.exists(dashboard_script_path):
    print(f"Error: Dashboard script not found at {dashboard_script_path}")
    sys.exit(1)

try:
    if sys.platform == "win32":
        subprocess.Popen(['start', 'cmd', '/k', sys.executable, dashboard_script_path, results_filepath], shell=True)
    elif sys.platform == "darwin": # macOS
        subprocess.Popen(['open', '-a', 'Terminal', sys.executable, dashboard_script_path, results_filepath])
    else: # Linux/other Unix-like
        subprocess.Popen(['xterm', '-e', sys.executable, dashboard_script_path, results_filepath])
    print("Dashboard launched. Check your browser for http://127.0.0.1:8050/")
except Exception as e:
    print(f"Could not automatically launch dashboard: {e}")
    print(f"Please run it manually: python {dashboard_script_path} {results_filepath}")