# algo/core/classes.py

import pandas as pd
# Import the specific functions from data_manager_functions.py
from data_manager.data_manager_functions import get_historical_data, save_data_to_csv, load_data_from_csv

# Import your technical indicator functions (if you have them here)
# from core.technical_indicators import calculate_sma, calculate_rsi, calculate_macd

class Stock:
    def __init__(self, ticker: str, name: str = None, exchange: str = None):
        self.ticker = ticker.upper()
        self.name = name
        self.exchange = exchange
        self.historical_data = pd.DataFrame() # To store the loaded data

    def __str__(self):
        return f"Stock({self.ticker}{f' - {self.name}' if self.name else ''})"

    def __repr__(self):
        return f"<Stock ticker={self.ticker}>"

    def download_data(self, start_date: str, end_date: str, interval: str = '1d', data_dir: str = 'data/historical_data'):
        """
        Downloads historical data for this stock using get_historical_data,
        and saves it using save_data_to_csv.
        """
        print(f"Downloading data for {self.ticker} from {start_date} to {end_date} ({interval})...")
        df = get_historical_data(
            ticker=self.ticker,
            start_date=start_date,
            end_date=end_date,
            interval=interval
        )
        if not df.empty:
            self.historical_data = df # Update the stock's internal data
            save_data_to_csv(
                df=self.historical_data,
                ticker=self.ticker,
                directory=data_dir,
                interval=interval,
                start_date=start_date,
                end_date=end_date
            )
            print(f"Successfully downloaded and saved data for {self.ticker}.")
        else:
            print(f"Failed to download data for {self.ticker}.")

    def load_local_data(self, start_date: str, end_date: str, interval: str = '1d', data_dir: str = 'data/historical_data') -> bool:
        """
        Loads historical data for this stock from local CSV using load_data_from_csv.
        Returns True if data was loaded, False otherwise.
        """
        print(f"Attempting to load local data for {self.ticker} from {start_date} to {end_date} ({interval})...")
        df = load_data_from_csv(
            ticker=self.ticker,
            directory=data_dir,
            interval=interval,
            start_date=start_date,
            end_date=end_date
        )
        if not df.empty:
            self.historical_data = df # Update the stock's internal data
            print(f"Successfully loaded {len(self.historical_data)} rows for {self.ticker}.")
            return True
        else:
            print(f"No local data found for {self.ticker} with specified parameters.")
            return False

    # ... (Your apply_indicator method would go here, which uses self.historical_data) ...
    def apply_indicator(self, indicator_function, in_place: bool = False, **kwargs) -> pd.DataFrame | None:
        # ... (implementation as provided in the previous answer) ...
        if self.historical_data.empty:
            print(f"Cannot apply indicator: No historical data available for {self.ticker}.")
            return None

        df_to_process = self.historical_data.copy()

        try:
            result_df = indicator_function(df_to_process, **kwargs)
            final_df_with_indicator = result_df if result_df is not None else df_to_process

            if in_place:
                self.historical_data = final_df_with_indicator
                print(f"Applied indicator '{indicator_function.__name__}' to {self.ticker}'s data in-place.")
            else:
                print(f"Applied indicator '{indicator_function.__name__}' to {self.ticker}'s data (temporary calculation).")

            return final_df_with_indicator

        except Exception as e:
            print(f"Error applying indicator '{indicator_function.__name__}' to {self.ticker}: {e}")
            return None