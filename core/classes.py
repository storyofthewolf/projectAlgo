# projectAlgo/core/classes.py

import pandas as pd
# Import the specific functions from data_manager_functions.py
from data_manager.data_manager_functions import get_historical_data, save_data_to_csv, load_data_from_csv

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

    # consider depreciating, see notes below.
    def calculate_indicator(self, indicator_func, column='Close', in_place=True, df_to_use=None, **indicator_kwargs):
        """
        Calculates a technical indicator using a provided function.
        Conveience function for manipulating Stock class dataframes.
        Could perhaps depreciate as it is no longer central to visualization, strategy, and backtesting.

        Args:
            indicator_func (function): The function to calculate the indicator (e.g., calculate_sma).
                                       It should expect (df, column, **kwargs).
            column (str): The name of the column to calculate the indicator on (default: 'Close').
            in_place (bool): If True, adds the indicator directly to the Stock's historical_data DataFrame.
                             If False, returns a new DataFrame with the indicator.
            df_to_use (pd.DataFrame, optional): A specific DataFrame to use for calculation instead
                                                of self.historical_data. Useful for chaining operations.
            **indicator_kwargs: Additional keyword arguments to pass ONLY to the indicator_func.

        Returns:
            pd.DataFrame or None: The DataFrame with the new indicator column if in_place is False,
                                  or the modified historical_data DataFrame if in_place is True.
                                  Returns None if calculation fails or historical_data is empty.
        """
        if self.historical_data.empty and df_to_use is None:
            print(f"Cannot calculate indicator for {self.ticker}: No historical data available.")
            return None

        # Determine which DataFrame to operate on
        # Make a copy to avoid unintended modifications if in_place is False later,
        # or if df_to_use was passed and we don't want to modify the caller's original.
        if df_to_use is None:
            df_working = self.historical_data.copy()
        else:
            df_working = df_to_use.copy()

        # Check if the target column exists in the DataFrame
        if column not in df_working.columns:
            print(f"Error: Column '{column}' not found in data for {self.ticker}.")
            return None

        try:
            # Call the indicator function. The indicator function expects the DataFrame
            # as its first positional argument, followed by 'column' and other indicator_kwargs.
            # `df_to_use` from calculate_indicator's signature is consumed by calculate_indicator itself,
            # and is NOT passed on to indicator_func.
            result_series = indicator_func(df_working, column=column, **indicator_kwargs)

            # Ensure result_series is a Series or DataFrame, and has a name for the new column
            if result_series is None:
                print(f"Indicator function '{indicator_func.__name__}' returned None.")
                return None
            if not isinstance(result_series, (pd.Series, pd.DataFrame)):
                print(f"Indicator function '{indicator_func.__name__}' did not return a pandas Series or DataFrame.")
                return None

            # Add the indicator to the working DataFrame
            # If result_series is a Series, it needs a name
            if isinstance(result_series, pd.Series) and result_series.name is None:
                # Try to infer a name from the indicator function's name or kwargs
                if 'window' in indicator_kwargs:
                    result_series.name = f"{indicator_func.__name__.replace('calculate_', '').upper()}{indicator_kwargs['window']}"
                else:
                    result_series.name = indicator_func.__name__.replace('calculate_', '').upper()

            # For multi-output indicators (like MACD), result_series might be a DataFrame
            if isinstance(result_series, pd.Series):
                df_working = df_working.join(result_series)
            elif isinstance(result_series, pd.DataFrame):
                df_working = df_working.join(result_series)
            else:
                print(f"Warning: Indicator function '{indicator_func.__name__}' returned an unexpected type ({type(result_series)}).")
                return None


            if in_place:
                self.historical_data = df_working # Update the Stock's actual historical_data
                return self.historical_data
            else:
                return df_working # Return the modified copy
        
        except TypeError as e:
            print(f"Error calculating indicator '{indicator_func.__name__}' for {self.ticker}: {e}")
            print(f"Please ensure '{indicator_func.__name__}' has signature like (df, column, **kwargs).")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during indicator '{indicator_func.__name__}' calculation for {self.ticker}: {e}")
            return None
