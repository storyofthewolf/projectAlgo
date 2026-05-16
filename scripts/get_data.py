# projectAlgo/scripts/get_data.py

import argparse
import logging
from datetime import datetime, date

from marketdata.service import get_data_service

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')


def main():
    parser = argparse.ArgumentParser(description="Download and manage historical stock data.")
    parser.add_argument("-t", "--tickers", nargs='+', required=True,
                        help="Space-separated list of ticker symbols (e.g., AAPL MSFT)")
    parser.add_argument("-i", "--interval", type=str, default="1d",
                        help="Data interval (e.g., 1d, 1wk, 1h). Default: 1d")
    parser.add_argument("-s", "--start", type=str, default="2023-01-01",
                        help="Start date (YYYY-MM-DD). Default: 2023-01-01")
    parser.add_argument("-e", "--end", type=str,
                        default=datetime.today().strftime('%Y-%m-%d'),
                        help="End date (YYYY-MM-DD). Default: today")
    parser.add_argument("--source", type=str, default=None,
                        choices=["yfinance", "schwab"],
                        help="Data source override. Default: uses cockpit.toml preferred_source")
    args = parser.parse_args()

    print("/------------------------------  get_data.py ------------------------------/")

    start = datetime.strptime(args.start, '%Y-%m-%d').date()
    end = datetime.strptime(args.end, '%Y-%m-%d').date()

    service = get_data_service()

    for ticker_symbol in args.tickers:
        ticker_symbol = ticker_symbol.upper()
        try:
            df = service.get_historical_ohlcv(
                ticker_symbol,
                start,
                end,
                interval=args.interval,
                source=args.source,
            )
            print(f"Data for {ticker_symbol} (first 5 rows):\n{df.head()}")
            print(f"Data for {ticker_symbol} (last 5 rows):\n{df.tail()}")
        except Exception as e:
            print(f"Failed to retrieve data for {ticker_symbol}: {e}")

    print("/--------------------------------------------------------------------------/")


if __name__ == "__main__":
    main()
