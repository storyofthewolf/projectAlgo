# /projectAlgo/scripts/get_data.py

import argparse
from datetime import datetime
from core import Stock # Import your Stock class

def main():
    parser = argparse.ArgumentParser(description="Download and manage historical stock data.")
    parser.add_argument("-t", "--tickers", nargs='+', required=True, help="Space-separated list of ticker symbols (e.g., AAPL MSFT)")
    parser.add_argument("-i", "--interval", type=str, default="1d", help="Data interval (e.g., 1d, 1wk, 1h). Default: 1d")
    parser.add_argument("-s", "--start", type=str, default="2023-01-01", help="Start date (YYYY-MM-DD). Default: 2023-01-01")
    parser.add_argument("-e", "--end", type=str, default=datetime.today().strftime('%Y-%m-%d'), help="End date (YYYY-MM-DD). Default: today")
    parser.add_argument("-o", "--output_dir", type=str, default="data/historical_data", help="Directory to save data. Default: data/historical_data")

    args = parser.parse_args()
  
    print(f"/------------------------------  get_data.py ------------------------------/")

    # Iterate through each ticker and manage its data using the Stock object
    for ticker_symbol in args.tickers:
        stock = Stock(ticker=ticker_symbol)

        # Attempt to load data first
        data_loaded = stock.load_local_data(
            start_date=args.start,
            end_date=args.end,
            interval=args.interval,
            data_dir=args.output_dir
        )

        # If data was not found locally, then download it
        if not data_loaded or stock.historical_data.empty:
            print(f"Local data not found or empty for {ticker_symbol}. Attempting to download.")
            stock.download_data(
                start_date=args.start,
                end_date=args.end,
                interval=args.interval,
                data_dir=args.output_dir
            )
        else:
            print(f"Using local data for {ticker_symbol}.")

        # Now, 'stock.historical_data' will contain the data (either loaded or downloaded)
        if not stock.historical_data.empty:
            print(f"Data for {stock.ticker} (first 5 rows):\n{stock.historical_data.head()}")
            print(f"Data for {stock.ticker} (last 5 rows):\n{stock.historical_data.tail()}")
        else:
            print(f"No data available for {stock.ticker} after all attempts.")

    print(f"/--------------------------------------------------------------------------/")

if __name__ == "__main__":
    main()