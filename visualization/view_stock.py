# /projectAlgo/visualization/view_stock.py
#
# Usage:
#   python -m visualization.view_stock
#   python -m visualization.view_stock --data-dir /absolute/path/to/data/historical_data

import argparse
import os
from datetime import datetime

from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go
import pandas as pd

from marketdata.service import get_data_service

# --data-dir is accepted but unused; DataService reads its cache dir from cockpit.toml.
_parser = argparse.ArgumentParser(add_help=False)
_parser.add_argument('--data-dir', default=None,
                     help="Unused; data directory is read from cockpit.toml.")
_args, _ = _parser.parse_known_args()

app = Dash(__name__)

DEFAULT_TICKER = "AAPL"
DEFAULT_INTERVAL = "1d"
DEFAULT_START_DATE = (datetime.now() - pd.DateOffset(years=1)).strftime('%Y-%m-%d')
DEFAULT_END_DATE = datetime.now().strftime('%Y-%m-%d')

app.layout = html.Div(children=[
    html.H1(children='Interactive Stock Dashboard'),

    html.Div([
        html.Label('Ticker Symbol:'),
        dcc.Input(
            id='ticker-input',
            type='text',
            value=DEFAULT_TICKER,
            debounce=True,
            style={'marginRight': '10px'}
        ),
        html.Label('Interval:'),
        dcc.Dropdown(
            id='interval-dropdown',
            options=[
                {'label': '1 Day', 'value': '1d'},
                {'label': '1 Week', 'value': '1wk'},
                {'label': '1 Month', 'value': '1mo'},
            ],
            value=DEFAULT_INTERVAL,
            style={'width': '120px', 'display': 'inline-block', 'marginRight': '10px'}
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

    dcc.Graph(
        id='candlestick-chart',
        figure={}
    )
])


@app.callback(
    Output('candlestick-chart', 'figure'),
    [
        Input('ticker-input', 'value'),
        Input('interval-dropdown', 'value'),
        Input('date-range-picker', 'start_date'),
        Input('date-range-picker', 'end_date'),
    ]
)
def update_candlestick_chart(ticker, interval, start_date, end_date):
    if not all([ticker, interval, start_date, end_date]):
        return {}

    print(f"Updating chart for {ticker} from {start_date} to {end_date} ({interval})...")

    try:
        service = get_data_service()
        start = datetime.strptime(start_date[:10], '%Y-%m-%d').date()
        end = datetime.strptime(end_date[:10], '%Y-%m-%d').date()
        df = service.get_historical_ohlcv(ticker, start, end, interval=interval)
    except Exception as e:
        print(f"An error occurred during data loading: {e}")
        return go.Figure()

    if df is None or df.empty:
        print(f"DataFrame is empty for {ticker} after data retrieval.")
        return go.Figure()

    fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close']
    )])

    fig.update_layout(
        title=f'{ticker} Candlestick Chart ({interval})',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        template='plotly_dark'
    )

    return fig


if __name__ == '__main__':
    app.run(debug=True)
