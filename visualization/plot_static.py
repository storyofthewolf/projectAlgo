# projectAlgo/visualization/plot_static.py

import argparse
import mplfinance as mpf
import pandas as pd
from datetime import datetime

# Import your Stock class
from core.financial_objects import Stock

# --- Import INDICATOR_PROPERTIES from indicator_plot_configs.py ---
from visualization.indicator_plot_configs import INDICATOR_PROPERTIES

# --- The parse_indicator_config function remains the same (for now) ---
def parse_indicator_config(config_string):
    """
    Parses a string like "sma:20,50;rsi:14" into a dictionary.
    E.g., {'sma': {'windows': [20, 50]}, 'rsi': {'windows': [14]}}
    """
    indicators_to_plot = {}
    if not config_string:
        return indicators_to_plot

    indicator_specs = config_string.split(';')
    for spec in indicator_specs:
        if ':' in spec:
            name, params_str = spec.split(':', 1)
            name = name.strip().lower()
            # --- Check against INDICATOR_PROPERTIES for valid indicator names ---
            if name in INDICATOR_PROPERTIES:
                windows = [int(p.strip()) for p in params_str.split(',') if p.strip().isdigit()]
                if windows:
                    indicators_to_plot[name] = {'windows': windows}
                else:
                    print(f"Warning: No valid window(s) found for indicator '{name}'. Skipping.")
            else:
                print(f"Warning: Indicator '{name}' not recognized or defined in INDICATOR_PROPERTIES. Skipping.")
        else:
            name = spec.strip().lower()
            # --- Check against INDICATOR_PROPERTIES for valid indicator names ---
            if name in INDICATOR_PROPERTIES:
                indicators_to_plot[name] = {'windows': []} # Empty list indicates no window or default
            else:
                print(f"Warning: Indicator '{name}' not recognized or defined in INDICATOR_PROPERTIES. Skipping.")
    return indicators_to_plot


def plot_stock_data(ticker, start_date, end_date, interval, data_dir, indicators_config_str=None):
    """
    Loads stock data, calculates specified indicators, and plots them using mplfinance.

    Args:
        ticker (str): Stock ticker symbol (e.g., 'AAPL').
        start_date (str): Start date for historical data (YYYY-MM-DD).
        end_date (str): End date for historical data (YYYY-MM-DD).
        interval (str): Data interval (e.g., '1d', '1h', '1wk').
        data_dir (str): Directory where historical data CSVs are stored.
        indicators_config_str (str, optional): A string defining indicators and their params
                                                (e.g., "sma:20,50;rsi:14").
    """
    # --- 1. Load or Download Stock Data ---
    stock = Stock(ticker=ticker)
    
    if not stock.load_local_data(start_date, end_date, interval, data_dir):
        print(f"No local data found for {ticker} ({interval}) from {start_date} to {end_date}. Attempting to download...")
        stock.download_data(start_date, end_date, interval, data_dir)
        if stock.historical_data.empty:
            print(f"Error: Could not retrieve historical data for {ticker}. Please check ticker, dates, or internet connection.")
            return

    df = stock.historical_data.copy()

    # --- 2. Parse indicator configuration ---
    indicators_to_plot = parse_indicator_config(indicators_config_str)
    apds = [] # List to hold `addplot` arguments for mplfinance
    
    # --- 3. Dynamically Calculate and Prepare Indicators for Plotting ---
    for indicator_name, config in indicators_to_plot.items():
        if indicator_name in INDICATOR_PROPERTIES:
            indicator_info = INDICATOR_PROPERTIES[indicator_name]
            indicator_func = indicator_info['func']
            plot_params = indicator_info['plot_params']
            ylabel_prefix = indicator_info['ylabel_prefix']
            column_name_format = indicator_info.get('column_name_format', '{}') # Get format, default to just name if not specified

            windows = config.get('windows', [])
            
            # Decide on parameters to pass to indicator_func
            # For now, we only handle 'window' parameters here
            func_kwargs = {}
            if windows: # If windows were specified in the command line
                # We iterate for each window instance
                pass # The loop below will handle it
            else: # If no windows specified, but the function might take one (e.g., default)
                # This branch handles indicators that might not use 'window' or use a default.
                # For simplicity, if 'windows' list is empty, we attempt to call the function once without it
                # or with a default we infer (which is more complex and might be added later)
                # For now, if 'windows' is empty, we will skip it in this loop as current functions expect 'window'.
                # More robust handling for non-window indicators will come later.
                print(f"Skipping {indicator_name}: No window specified and current implementation expects one.")
                continue


            # Loop through each window for the current indicator (e.g., 20 and 50 for SMA)
            for window in windows:
                print(f"Calculating {indicator_name.upper()} with window {window}...")
                
                # Pass the correct window to the indicator function via kwargs
                df_with_indicator = stock.calculate_indicator(
                    indicator_func,
                    in_place=False,
                    df_to_use=df,
                    window=window # Pass window as a kwarg for the indicator function
                )

                if df_with_indicator is not None:
                    # Check if the returned df is actually new/modified (to avoid self-assignment issues)
                    if not df_with_indicator.equals(df): # A more robust check than `is not df`
                         df = df_with_indicator
                    else:
                        print(f"Warning: Indicator '{indicator_name.upper()}({window})' calculation did not modify DataFrame.")
                        # This might happen if there's not enough data for the window etc.
                        continue # Skip adding this indicator to plot

                else:
                    print(f"Warning: Indicator '{indicator_name.upper()}({window})' calculation failed.")
                    continue # Skip adding this indicator to plot


                # Prepare addplot for mplfinance
                # --- MODIFIED: Use column_name_format for robustness ---
                indicator_col_name = column_name_format.format(window)
                if indicator_col_name in df.columns:
                    current_plot_params = plot_params.copy()
                    if current_plot_params.get('panel') != 0: # If it's a separate panel
                        current_plot_params['ylabel'] = f'{ylabel_prefix}({window})' # e.g., RSI(14)
                    
                    apds.append(mpf.make_addplot(df[indicator_col_name], **current_plot_params))
                else:
                    print(f"Warning: Column '{indicator_col_name}' not found after calculation for {indicator_name.upper()}. "
                          "Check indicator function's return column name.")
        else:
            print(f"Warning: Indicator '{indicator_name}' requested but not defined in INDICATOR_PROPERTIES. Skipping.")


    # --- 4. Staic Plotting with mplfinance ---
    print(f"\nDisplaying chart for {ticker} from {start_date} to {end_date} ({interval})...")
    print("Close the window to continue.")
    
    if 'Volume' in df.columns and df['Volume'].dtype == 'int64':
        df['Volume'] = df['Volume'].astype(float)

    mpf.plot(
        df,
        type='candle',
        style='yahoo',
        title=f"{ticker} ({interval}) - {start_date} to {end_date}",
        ylabel='Price',
        ylabel_lower='Volume',
        volume=True,
        addplot=apds if apds else None,
        figscale=1.5,
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize stock market data and technical indicators.")
    parser.add_argument('-t', '--ticker', type=str, required=True, help="Stock ticker symbol (e.g., AAPL)")
    parser.add_argument('-s', '--start_date', type=str, default='2024-01-01', help="Start date (YYYY-MM-DD)")
    parser.add_argument('-e', '--end_date', type=str, default=datetime.now().strftime('%Y-%m-%d'), help="End date (YYYY-MM-DD) or 'today'")
    parser.add_argument('-i', '--interval', type=str, default='1d', help="Data interval (e.g., 1d, 1wk, 1h)")
    parser.add_argument('-o', '--data_dir', type=str, default='data/historical_data', help="Directory to store/load historical data")
    parser.add_argument(
        '--indicators',
        type=str,
        help="Specify indicators and windows (e.g., 'sma:20,50;rsi:14'). "
             "Separate indicators with ';', window/params with ':'. "
             "Parameters for windowed indicators are comma-separated. "
             "Example: --indicators \"sma:20,50;rsi:14\""
    )

    args = parser.parse_args()

    if args.end_date.lower() == 'today':
        args.end_date = datetime.now().strftime('%Y-%m-%d')

    plot_stock_data(
        args.ticker,
        args.start_date,
        args.end_date,
        args.interval,
        args.data_dir,
        args.indicators
    )