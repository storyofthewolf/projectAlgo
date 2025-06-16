# /projectAlgo/run_analysis.py

import pandas as pd
from core.classes import Stock
# Import the specific indicator functions from your analysis.technical_analysis module
from analysis.technical_analysis import calculate_sma, calculate_rsi
from datetime import datetime, timedelta

def main():
    # --- 1. Initialize a Stock object ---
    ticker = "AAPL"
    stock = Stock(ticker=ticker, name="Apple Inc.")
    print(f"Initialized {stock}")

    # --- 2. Load historical data ---
    # Make sure you have data downloaded for this range first!
    # e.g., by running:
    # python -m data_manager.get_data -t AAPL -i 1d -s 2024-01-01 -e 2025-01-01
    
    start_date = "2024-01-01"
    end_date = "2025-01-01" # Or datetime.now().strftime('%Y-%m-%d')
    interval = "1d"
    data_directory = "data/historical_data"

    if not stock.load_local_data(start_date, end_date, interval, data_directory):
        print(f"Local data not found for {ticker}. Attempting to download...")
        stock.download_data(start_date, end_date, interval, data_directory)
        if stock.historical_data.empty:
            print(f"Could not get historical data for {ticker}. Exiting.")
            return

    print(f"\n--- Original {ticker} Historical Data (last 5 rows) ---")
    print(stock.historical_data.tail())
    print(f"Original DataFrame columns: {stock.historical_data.columns.tolist()}")

    # --- 3. Apply an indicator (SMA) - in_place=False (default) ---
    # Result: A NEW DataFrame is returned. The stock.historical_data remains unchanged.
    sma_window = 20
    print(f"\n--- Applying SMA({sma_window}) - NOT in_place ---")
    df_with_sma = stock.calculate_indicator(calculate_sma, window=sma_window, in_place=False)

    if df_with_sma is not None:
        print(f"DataFrame with SMA({sma_window}) (last 5 rows):")
        print(df_with_sma[['Close', f'SMA{sma_window}']].tail())
        print(f"Returned DataFrame columns: {df_with_sma.columns.tolist()}")
    else:
        print("SMA calculation failed.")

    print(f"\n--- Original {ticker} Historical Data AFTER SMA application (still no SMA column) ---")
    print(f"Original DataFrame columns: {stock.historical_data.columns.tolist()}")
    # You'll notice the SMA column is NOT in stock.historical_data here

    # --- 4. Apply another indicator (RSI) - in_place=True ---
    # Result: The stock.historical_data is UPDATED. The modified DataFrame is also returned.
    rsi_window = 14
    print(f"\n--- Applying RSI({rsi_window}) - IN_PLACE ---")
    df_with_rsi_and_saved = stock.calculate_indicator(calculate_rsi, window=rsi_window, in_place=True)

    if df_with_rsi_and_saved is not None:
        print(f"DataFrame returned from IN_PLACE RSI({rsi_window}) (last 5 rows):")
        print(df_with_rsi_and_saved[['Close', f'RSI{rsi_window}']].tail())
        print(f"Returned DataFrame columns: {df_with_rsi_and_saved.columns.tolist()}")
    else:
        print("RSI calculation failed.")

    print(f"\n--- Original {ticker} Historical Data AFTER IN_PLACE RSI application (RSI column IS present) ---")
    print(f"Original DataFrame columns: {stock.historical_data.columns.tolist()}")
    # You'll notice the RSI column IS now in stock.historical_data here

if __name__ == "__main__":
    main()