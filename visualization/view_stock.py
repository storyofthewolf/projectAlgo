# /projectAlgo/visualization/view_stock.py
#
# Usage:
#   python -m visualization.view_stock
#   python -m visualization.view_stock --data-dir /absolute/path/to/data/historical_data

import argparse
import os
from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

from core.financial_objects import Stock

# --- Resolve data directory from CLI arg or default ---
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument('--data-dir', default=None,
                     help="Directory for cached historical data. Default: data/historical_data under project root.")
_args, _ = _parser.parse_known_args()

_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = _args.data_dir or os.path.join(_project_root, 'data', 'historical_data')

# --- Initialize the Dash app ---
app = Dash(__name__)

DEFAULT_TICKER = "AAPL"
DEFAULT_INTERVAL = "1d"
DEFAULT_START_DATE = (datetime.now() - pd.DateOffset(years=1)).strftime('%Y-%m-%d')
DEFAULT_END_DATE = datetime.now().strftime('%Y-%m-%d')


# --- Define the layout of your application ---
app.layout = html.Div(children=[
    html.H1(children='Interactive Stock Dashboard'),

    # Input controls
    html.Div([
        html.Label('Ticker Symbol:'),
        dcc.Input(
            id='ticker-input',
            type='text',
            value=DEFAULT_TICKER, # Set default value
            debounce=True, # Wait for user to finish typing
            style={'marginRight':'10px'}
        ),
        html.Label('Interval:'),
        dcc.Dropdown(
            id='interval-dropdown',
            options=[
                {'label': '1 Day', 'value': '1d'},
                {'label': '1 Week', 'value': '1wk'},
                {'label': '1 Month', 'value': '1mo'}
                # You can add more intervals if supported by yfinance and your Stock class
            ],
            value=DEFAULT_INTERVAL, # Set default value
            style={'width': '120px', 'display': 'inline-block', 'marginRight':'10px'}
        ),
        html.Label('Date Range:'),
        dcc.DatePickerRange(
            id='date-range-picker',
            start_date=DEFAULT_START_DATE,
            end_date=DEFAULT_END_DATE,
            display_format='YYYY-MM-DD',
            style={'display': 'inline-block'}
        ),
    ], style={'padding': '20px', 'borderBottom': '1px solid #ccc'}),

    # Graph component - initially empty, will be updated by callback
    dcc.Graph(
        id='candlestick-chart',
        figure={} # Start with an empty figure
    )
])


# --- Define the Callback ---
@app.callback(
    Output('candlestick-chart', 'figure'), # Output: The 'figure' property of the 'candlestick-chart' component
    [
        Input('ticker-input', 'value'),     # Input 1: The 'value' property of 'ticker-input'
        Input('interval-dropdown', 'value'),# Input 2: The 'value' property of 'interval-dropdown'
        Input('date-range-picker', 'start_date'), # Input 3: The 'start_date' property of 'date-range-picker'
        Input('date-range-picker', 'end_date')  # Input 4: The 'end_date' property of 'date-range-picker'
    ]
)
def update_candlestick_chart(ticker, interval, start_date, end_date):
    """
    This function is automatically called by Dash whenever any of its Input properties change.
    It takes the new input values, loads/downloads stock data, and returns a new Plotly figure.
    """
    if not all([ticker, interval, start_date, end_date]):
        # Return an empty figure if any input is missing (e.g., on initial load before values propagate)
        return {}

    print(f"Updating chart for {ticker} from {start_date} to {end_date} ({interval})...")

    stock_data = Stock(ticker)

    try:
        stock_data.load_local_data(start_date, end_date, interval, data_dir=DATA_DIR)
        if stock_data.historical_data.empty:
            print(f"No local data found for {ticker}. Attempting to download...")
            stock_data.download_data(start_date, end_date, interval, data_dir=DATA_DIR)
            if stock_data.historical_data.empty:
                print(f"Error: Could not retrieve data for {ticker}. Please check inputs.")
                return go.Figure()
    except Exception as e:
        print(f"An error occurred during data loading/download: {e}")
        return go.Figure()

    df = stock_data.historical_data.copy()

    if df.empty:
        print(f"DataFrame is empty for {ticker} after data retrieval.")
        return go.Figure() # Return empty figure if no data

    # Create the Candlestick Figure
    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close']
    )])

    # Update layout for better appearance
    fig.update_layout(
        title=f'{ticker} Candlestick Chart ({interval})',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        template='plotly_dark' # Optional: a dark theme for the chart
    )

    return fig # Return the created figure to update the dcc.Graph component


# --- Run the app ---
if __name__ == '__main__':
    app.run(debug=True)