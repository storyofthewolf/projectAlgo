# /projectAlgo/visualization/dashboard_app.py

from dash import Dash, html, dcc, Input, Output # Import Input and Output
import plotly.graph_objects as go
import pandas as pd
import sys
import os
from datetime import datetime # Import datetime for default dates

# --- REVISED PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..')
sys.path.insert(0, project_root)
# --- END REVISED PATH SETUP ---

from core.classes import Stock # Import your Stock class

# --- Initialize the Dash app ---
app = Dash(__name__)

# Define default values for the inputs
DEFAULT_TICKER = "AAPL"
DEFAULT_INTERVAL = "1d"
DEFAULT_START_DATE = (datetime.now() - pd.DateOffset(years=1)).strftime('%Y-%m-%d') # 1 year ago
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

    stock_data = Stock(ticker) # Stock class now uses interval in download/load methods, not constructor
    
    # Attempt to load or download data
    try:
        stock_data.load_local_data(start_date, end_date, interval)
        if stock_data.historical_data.empty:
            print(f"No local data found for {ticker} with current parameters. Attempting to download...")
            stock_data.download_data(start_date, end_date, interval) # Pass interval here
            if stock_data.historical_data.empty:
                print(f"Error: Could not retrieve data for {ticker}. Please check inputs.")
                return go.Figure() # Return empty figure on data failure
    except Exception as e:
        print(f"An error occurred during data loading/download: {e}")
        return go.Figure() # Return empty figure on error

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