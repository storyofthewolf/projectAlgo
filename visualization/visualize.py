# projectAlgo/visualization/financial_visualizer.py

import argparse
import mplfinance as mpf
import pandas as pd
from datetime import datetime

# Import your Stock class (path remains the same)
from core.classes import Stock

# Import your technical indicator functions (path remains the same)
from analysis.technical_analysis import calculate_sma, calculate_rsi

def plot_stock_data(ticker, start_date, end_date, interval, data_dir, show_indicators=None):
    """
    Loads stock data, calculates specified indicators, and plots them using mplfinance.

    Args:
        ticker (str): Stock ticker symbol (e.g., 'AAPL').
        start_date (str): Start date for historical data (YYYY-MM-DD).
        end_date (str): End date for historical data (YYYY-MM-DD).
        interval (str): Data interval (e.g., '1d', '1h', '1wk').
        data_dir (str): Directory where historical data CSVs are stored.
        show_indicators (list, optional): List of indicator names to plot (e.g., ['sma', 'rsi']).
    """
    # --- 1. Load or Download Stock Data ---
    stock = Stock(ticker=ticker)
    
    # Attempt to load local data first
    if not stock.load_local_data(start_date, end_date, interval, data_dir):
        print(f"No local data found for {ticker} ({interval}) from {start_date} to {end_date}. Attempting to download...")
        stock.download_data(start_date, end_date, interval, data_dir)
        if stock.historical_data.empty:
            print(f"Error: Could not retrieve historical data for {ticker}. Please check ticker, dates, or internet connection.")
            return

    df = stock.historical_data.copy() # Work on a copy to avoid unintended modifications outside this function

    # --- 2. Calculate Indicators (if requested) ---
    apds = [] # List to hold `addplot` arguments for mplfinance

    if show_indicators:
        if 'sma' in show_indicators:
            # You might want to pass window values via command line args too,
            # but for simplicity, let's hardcode common ones for now.
            sma_window = 20
            print(f"Calculating SMA({sma_window})...")
            df = stock.calculate_indicator(calculate_sma, window=sma_window, in_place=False, df_to_use=df)
            if f'SMA{sma_window}' in df.columns:
                apds.append(mpf.make_addplot(df[f'SMA{sma_window}']))
            else:
                print(f"Warning: SMA{sma_window} column not found after calculation. Check calculate_sma function.")
        
        if 'rsi' in show_indicators:
            rsi_window = 14
            print(f"Calculating RSI({rsi_window})...")
            df = stock.calculate_indicator(calculate_rsi, window=rsi_window, in_place=False, df_to_use=df)
            if f'RSI{rsi_window}' in df.columns:
                apds.append(mpf.make_addplot(df[f'RSI{rsi_window}'], panel=1, type='line', ylabel=f'RSI({rsi_window})'))
            else:
                print(f"Warning: RSI{rsi_window} column not found after calculation. Check calculate_rsi function.")

    # --- 3. Plotting with mplfinance ---
    print(f"\nDisplaying chart for {ticker} from {start_date} to {end_date} ({interval})...")
    
    # Convert 'Volume' to float if it's not already, as mplfinance expects it
    if 'Volume' in df.columns and df['Volume'].dtype == 'int64':
        df['Volume'] = df['Volume'].astype(float)

    mpf.plot(
        df,
        type='candle', # Candlestick chart
        style='yahoo', # A clean, common style
        title=f"{ticker} ({interval}) - {start_date} to {end_date}",
        ylabel='Price',
        ylabel_lower='Volume',
        volume=True,   # Show volume panel
        addplot=apds if apds else None, # Add indicators if any
        figscale=1.5, # Adjust figure size
        # tight_layout=True # Can help with spacing
    )

    print("Chart displayed. Close the window to continue.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize stock market data and technical indicators.")
    parser.add_argument('-t', '--ticker', type=str, required=True, help="Stock ticker symbol (e.g., AAPL)")
    parser.add_argument('-s', '--start_date', type=str, default='2024-01-01', help="Start date (YYYY-MM-DD)")
    parser.add_argument('-e', '--end_date', type=str, default=datetime.now().strftime('%Y-%m-%d'), help="End date (YYYY-MM-DD)")
    parser.add_argument('-i', '--interval', type=str, default='1d', help="Data interval (e.g., 1d, 1wk, 1h)")
    parser.add_argument('-o', '--data_dir', type=str, default='data/historical_data', help="Directory to store/load historical data")
    parser.add_argument('--show-indicators', nargs='*', choices=['sma', 'rsi'], help="Space-separated list of indicators to show (e.g., --show-indicators sma rsi)")

    args = parser.parse_args()

    plot_stock_data(
        args.ticker,
        args.start_date,
        args.end_date,
        args.interval,
        args.data_dir,
        args.show_indicators
    )