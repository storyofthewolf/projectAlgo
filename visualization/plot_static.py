# projectAlgo/visualization/plot_static.py

import argparse
import mplfinance as mpf
import pandas as pd
from datetime import datetime

from marketdata.service import get_data_service
from visualization.indicator_plot_configs import INDICATOR_PROPERTIES


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
            if name in INDICATOR_PROPERTIES:
                windows = [int(p.strip()) for p in params_str.split(',') if p.strip().isdigit()]
                if windows:
                    indicators_to_plot[name] = {'windows': windows}
                else:
                    print(f"Warning: No valid window(s) found for indicator '{name}'. Skipping.")
            else:
                print(f"Warning: Indicator '{name}' not recognized. Skipping.")
        else:
            name = spec.strip().lower()
            if name in INDICATOR_PROPERTIES:
                indicators_to_plot[name] = {'windows': []}
            else:
                print(f"Warning: Indicator '{name}' not recognized. Skipping.")
    return indicators_to_plot


def plot_stock_data(ticker, start_date, end_date, interval, data_dir=None,
                    indicators_config_str=None):
    """
    Loads stock data, calculates specified indicators, and plots them using mplfinance.
    """
    service = get_data_service()
    start = datetime.strptime(start_date, '%Y-%m-%d').date()
    end = datetime.strptime(end_date, '%Y-%m-%d').date()

    try:
        df = service.get_historical_ohlcv(ticker, start, end, interval=interval)
    except Exception as e:
        print(f"Error: Could not retrieve historical data for {ticker}: {e}")
        return

    if df is None or df.empty:
        print(f"Error: No data returned for {ticker}.")
        return

    df = df.copy()

    indicators_to_plot = parse_indicator_config(indicators_config_str)
    apds = []

    for indicator_name, config in indicators_to_plot.items():
        if indicator_name not in INDICATOR_PROPERTIES:
            print(f"Warning: Indicator '{indicator_name}' not defined. Skipping.")
            continue

        indicator_info = INDICATOR_PROPERTIES[indicator_name]
        indicator_func = indicator_info['func']
        plot_params = indicator_info['plot_params']
        ylabel_prefix = indicator_info['ylabel_prefix']
        column_name_format = indicator_info.get('column_name_format', '{}')

        windows = config.get('windows', [])
        if not windows:
            print(f"Skipping {indicator_name}: No window specified.")
            continue

        for window in windows:
            print(f"Calculating {indicator_name.upper()} with window {window}...")
            col_name = column_name_format.format(window)

            try:
                result = indicator_func(df, window=window)
                df[col_name] = result
            except Exception as e:
                print(f"Warning: Indicator '{indicator_name.upper()}({window})' calculation failed: {e}")
                continue

            if col_name not in df.columns or df[col_name].isna().all():
                print(f"Warning: Column '{col_name}' empty after calculation. Skipping.")
                continue

            current_plot_params = plot_params.copy()
            if current_plot_params.get('panel') != 0:
                current_plot_params['ylabel'] = f'{ylabel_prefix}({window})'

            apds.append(mpf.make_addplot(df[col_name], **current_plot_params))

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
    parser.add_argument('-e', '--end_date', type=str, default=datetime.now().strftime('%Y-%m-%d'),
                        help="End date (YYYY-MM-DD)")
    parser.add_argument('-i', '--interval', type=str, default='1d',
                        help="Data interval (e.g., 1d, 1wk, 1h)")
    parser.add_argument('-o', '--data_dir', type=str, default=None,
                        help="Unused; data directory is read from cockpit.toml")
    parser.add_argument('--indicators', type=str,
                        help="Indicators and windows, e.g. 'sma:20,50;rsi:14'")
    args = parser.parse_args()

    if args.end_date.lower() == 'today':
        args.end_date = datetime.now().strftime('%Y-%m-%d')

    plot_stock_data(
        args.ticker,
        args.start_date,
        args.end_date,
        args.interval,
        args.data_dir,
        args.indicators,
    )
