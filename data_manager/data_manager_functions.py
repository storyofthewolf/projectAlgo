import yfinance as yf
import pandas as pd
import os
from datetime import datetime, timedelta

# contains ::
# get_historical_data  :: Downloads historical stock data for a given ticker, period, interval 
# save_data_to_csv     :: Saves historical data to CSV file 
# load_data_from_csv   :: Loads saved data from CSV files


def get_historical_data(ticker: str, start_date: str = None, end_date: str = None, period: str = None, interval: str = '1d') -> pd.DataFrame:
    """
    Downloads historical stock data for a given ticker.

    Args:
        ticker (str): The stock ticker symbol (e.g., 'AAPL', 'MSFT').
        start_date (str, optional): Start date in 'YYYY-MM-DD' format.
                                    If None, defaults to yfinance's behavior (usually 1999-01-01 or max available).
        end_date (str, optional): End date in 'YYYY-MM-DD' format.
                                  If None, defaults to today.
        period (str, optional): Valid periods: "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max".
                                If specified, start_date and end_date are ignored.
        interval (str, optional): Valid intervals: "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo".
                                  Intraday intervals (1m, 2m, etc.) only work for very short periods (e.g., 7 days for 1m).

    Returns:
        pd.DataFrame: A DataFrame containing the historical data (Open, High, Low, Close, Volume, Dividends, Stock Splits).
                      Returns an empty DataFrame if data cannot be fetched.
    """

    print(f"Attempting to download data for {ticker}...")
    data = pd.DataFrame()

    try:
        if period:
            data = yf.download(ticker, period=period, interval=interval, progress=False) # Added progress=False
        else:
            data = yf.download(ticker, start=start_date, end=end_date, interval=interval, progress=False) # Added progress=False

        #print(f"DEBUG: Type of 'data' after yf.download for {ticker}: {type(data)}")
        #if isinstance(data, pd.DataFrame) and not data.empty:
        #    print(f"DEBUG: Original columns after yf.download for {ticker}:\n{data.columns}")

        if not isinstance(data, pd.DataFrame) or data.empty:
            print(f"No valid DataFrame returned for {ticker} or data is empty. Type received: {type(data)}")
            return pd.DataFrame()

        # --- COLUMN HANDLING START ---
        if isinstance(data.columns, pd.MultiIndex):
            #print(f"DEBUG: MultiIndex detected for {ticker}. Current MultiIndex structure:\n{data.columns.values}")
            
            # This is the most common MultiIndex structure when downloading multiple tickers.
            # For a single ticker causing MultiIndex, it's often (Metric, Ticker).
            # Example: [('Close', 'AAPL'), ('High', 'AAPL')]
            
            # Check if the ticker is in the first level (less likely for single ticker, but covers it)
            if ticker in data.columns.levels[0]:
                #print(f"DEBUG: Ticker '{ticker}' found in first level of MultiIndex. Selecting ticker data.")
                data = data[ticker] # Selects the sub-DataFrame for this ticker
                # Now columns are single-level, e.g., 'Open', 'High', 'Close'
            # Else, if ticker is NOT in the first level, it's likely (Metric, Ticker) structure.
            # We want to flatten to just the Metric.
            else:
                #print(f"DEBUG: Ticker '{ticker}' NOT found in first level of MultiIndex. Assuming (Metric, Ticker) structure. Flattening to Metric names.")
                # This line is the key: it takes the first level of the MultiIndex as the new columns.
                # e.g., turns [('Close', 'AAPL')] into ['Close']
                data.columns = data.columns.get_level_values(0)
                
            #print(f"DEBUG: Columns after MultiIndex flattening:\n{data.columns}")
            
        # Ensure column names are capitalized (Open, High, Low, Close, Volume, etc.)
        # This applies whether it was a MultiIndex or already single-level
        data.columns = [col.capitalize() for col in data.columns]
        #print(f"DEBUG: Columns after final capitalization: {data.columns.tolist()}")
        # --- COLUMN HANDLING END ---
        
        # Now, check for 'Close' column after column standardization
        if 'Close' not in data.columns:
            print(f"CRITICAL ERROR: 'Close' column not found in data for {ticker} after all column processing. Available columns: {data.columns.tolist()}")
            return pd.DataFrame()

        # Convert 'Close' column to numeric, coercing errors to NaN, then drop rows with NaN Close price
        data['Close'] = pd.to_numeric(data['Close'], errors='coerce')
        data.dropna(subset=['Close'], inplace=True)

        if data.empty:
            print(f"No valid 'Close' price data for {ticker} after cleaning (all NaN or removed).")
            return pd.DataFrame()

        print(f"Successfully downloaded {len(data)} rows for {ticker}.")
        return data

    except Exception as e:
        print(f"An error occurred during download for {ticker}. Exception type: {type(e)}, Message: {e}")
        return pd.DataFrame()


def _generate_filename(ticker: str, interval: str, start_date: str, end_date: str) -> str:
    """Helper to generate a consistent filename."""
    # Ensure dates are in YYYY-MM-DD format for consistency in filename
    # If start/end dates are None, use a placeholder or handle explicitly if needed
    # For simplicity, we'll assume they're always provided when calling save/load with date tags
    start_tag = start_date.replace('-', '') if start_date else 'undated_start'
    end_tag = end_date.replace('-', '') if end_date else 'undated_end'
    
    return f"{ticker}_{interval}_{start_tag}_{end_tag}.csv"


def save_data_to_csv(df: pd.DataFrame, ticker: str, directory: str, interval: str, start_date: str, end_date: str):
    """
    Saves a DataFrame to a CSV file, including interval and date range in the filename.

    Args:
        df (pd.DataFrame): The DataFrame to save.
        ticker (str): The stock ticker symbol.
        directory (str): The directory to save the file in.
        interval (str): The interval of the data (e.g., '1d', '1wk', '1h').
        start_date (str): The start date of the data in 'YYYY-MM-DD' format.
        end_date (str): The end date of the data in 'YYYY-MM-DD' format.
    """
     
    if df.empty:
        print(f"Warning: Cannot save empty DataFrame for {ticker}.")
        return None

    if not os.path.exists(directory):
        os.makedirs(directory) # Create the directory if it doesn't exist

    # create filename and file path
    file_name = _generate_filename(ticker, interval, start_date, end_date)
    file_path = os.path.join(directory, file_name)
    
    try:
        df.to_csv(file_path, index=True) # index=True saves the Date/DatetimeIndex
        print(f"Successfully saved {ticker} data (interval: {interval}, dates: {start_date} to {end_date}) to {file_path}")
    except Exception as e:
        print(f"Error saving data for {ticker} (interval: {interval}, dates: {start_date} to {end_date}) to {file_path}: {e}")


def load_data_from_csv(ticker: str, directory: str, interval: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    Loads historical stock data from a CSV file, using interval and date range in the filename.

    Args:
        ticker (str): The stock ticker symbol.
        directory (str): The directory where the file is located.
        interval (str): The interval of the data (e.g., '1d', '1wk', '1h').
        start_date (str): The start date of the data in 'YYYY-MM-DD' format.
        end_date (str): The end date of the data in 'YYYY-MM-DD' format.

    Returns:
        pd.DataFrame: A DataFrame containing the historical data, or an empty DataFrame if not found.
    """
    file_name = _generate_filename(ticker, interval, start_date, end_date)
    file_path = os.path.join(directory, file_name)
    
    if not os.path.exists(file_path):
        print(f"Data file not found for {ticker} (interval: {interval}, dates: {start_date} to {end_date}) at {file_path}. Please download it first.")
        return pd.DataFrame()
    
    try:
        df = pd.read_csv(file_path, index_col='Date', parse_dates=True)
        print(f"Successfully loaded {len(df)} rows for {ticker} (interval: {interval}, dates: {start_date} to {end_date}) from {file_path}")
        return df
    except Exception as e:
        print(f"Error loading data for {ticker} (interval: {interval}, dates: {start_date} to {end_date}) from {file_path}: {e}")
        return pd.DataFrame()
