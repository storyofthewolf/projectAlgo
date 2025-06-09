# get_data.py

import argparse
import pandas as pd
import os
from datetime import datetime

# Import the functions from your data_manager_functions module
from . import get_historical_data, save_data_to_csv, load_data_from_csv

def main():
    """
    Main function to orchestrate the data collection process using command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Collect historical stock data and save it locally.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--tickers", "-t", 
        nargs='+',
        default=["AAPL", "MSFT", "GOOGL"],
        help="Space-separated list of ticker symbols (e.g., AAPL MSFT NVDA)."
    )
    
    parser.add_argument(
        "--start", "-s", 
        type=str, 
        default="2020-01-01",
        help="Start date for data collection in YYYY-MM-DD format."
    )
    
    parser.add_argument(
        "--end", "-e", 
        type=str, 
        default=datetime.now().strftime('%Y-%m-%d'),
        help="End date for data collection in YYYY-MM-DD format."
    )
    
    parser.add_argument(
        "--output_dir", "-o", 
        type=str, 
        default="data/historical_data", # Already updated this previously
        help="Directory to save the historical CSV files."
    )

    parser.add_argument(
        "--interval", "-i",
        type=str,
        default="1d",
        choices=["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo"],
        help="Data interval (e.g., 1d, 1wk, 1h, 1m). Note: 1m intervals are limited to 7 days of data."
    )
    
    args = parser.parse_args()

    # Assign parsed arguments to variables
    tickers_to_process = args.tickers
    start_date = args.start
    end_date = args.end
    data_output_directory = args.output_dir
    data_interval = args.interval
    
    # Create the output directory if it doesn't exist
    os.makedirs(data_output_directory, exist_ok=True)

    print("\n--- Starting Data Collection Process ---")
    for ticker in tickers_to_process:
        print(f"\n--- Processing {ticker} (Interval: {data_interval}, Dates: {start_date} to {end_date}) ---")
        
        # Pass all necessary parameters to load_data_from_csv
        df_loaded = load_data_from_csv(ticker, directory=data_output_directory, 
                                       interval=data_interval, start_date=start_date, end_date=end_date)
        needs_download = True

        if not df_loaded.empty:
            # If load_data_from_csv returned a non-empty DataFrame for the exact requested file,
            # it means the data for this ticker, interval, and date range is already present.
            print(f"Data for {ticker} (interval: {data_interval}, dates: {start_date} to {end_date}) is already present locally.")
            needs_download = False
            # Note: This check only verifies if the file exists for the exact requested range.
            # It doesn't check for freshness up to 'today' if 'end_date' is dynamic.
            # For dynamic 'end_date' and daily updates, you might want to consider
            # checking the max date in the loaded DataFrame and downloading only missing data.
            # However, for simplicity with date-tagged files, an exact match is usually sufficient.

        if needs_download:
            print(f"Downloading data for {ticker} from {start_date} to {end_date} with interval {data_interval}...")
            # Pass the interval, start_date, and end_date to get_historical_data
            df_downloaded = get_historical_data(ticker, start_date=start_date, end_date=end_date, interval=data_interval)
            
            if not df_downloaded.empty:
                # Pass all necessary parameters to save_data_to_csv
                save_data_to_csv(df_downloaded, ticker, directory=data_output_directory, 
                                 interval=data_interval, start_date=start_date, end_date=end_date)
            else:
                print(f"Skipping {ticker} (interval: {data_interval}, dates: {start_date} to {end_date}) due to download failure or empty data.")
        else:
            pass

    print("\n--- Data collection and storage process complete ---")

if __name__ == "__main__":
    main()