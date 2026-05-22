# /projectAlgo/visualization/view_stock.py
#
# Interactive stock dashboard: candlestick + SMA overlays, volume bars,
# and an RSI subplot. Data flows through DataService (cache + yfinance/Schwab).
#
# Usage:
#   python -m visualization.view_stock
#   python -m visualization.view_stock --ticker NVDA --interval 1d
#   python -m visualization.view_stock --ticker AAPL --start 2023-01-01 --port 8050

import argparse
from datetime import datetime

from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from analysis.technical_analysis import calculate_rsi, calculate_sma
from marketdata.service import get_data_service

_SMA_WINDOWS = [20, 50, 200]
_SMA_COLORS = {20: "#4dd0e1", 50: "#ffb74d", 200: "#ba68c8"}
_RSI_WINDOW = 14

_parser = argparse.ArgumentParser(description="Interactive stock dashboard")
_parser.add_argument("--ticker", default="AAPL", help="Initial ticker symbol")
_parser.add_argument("--interval", default="1d", choices=["1d", "1wk", "1mo"],
                     help="Initial bar interval")
_parser.add_argument("--start", default=None,
                     help="Initial start date (YYYY-MM-DD); defaults to 1 year ago")
_parser.add_argument("--port", type=int, default=8050, help="Port for the Dash server")
_args, _ = _parser.parse_known_args()

DEFAULT_TICKER = _args.ticker.upper()
DEFAULT_INTERVAL = _args.interval
DEFAULT_START_DATE = _args.start or (
    datetime.now() - pd.DateOffset(years=1)
).strftime("%Y-%m-%d")
DEFAULT_END_DATE = datetime.now().strftime("%Y-%m-%d")

app = Dash(__name__)

app.layout = html.Div(children=[
    html.H1(children="Interactive Stock Dashboard"),

    html.Div([
        html.Label("Ticker Symbol:"),
        dcc.Input(
            id="ticker-input",
            type="text",
            value=DEFAULT_TICKER,
            debounce=True,
            style={"marginRight": "10px"},
        ),
        html.Label("Interval:"),
        dcc.Dropdown(
            id="interval-dropdown",
            options=[
                {"label": "1 Day", "value": "1d"},
                {"label": "1 Week", "value": "1wk"},
                {"label": "1 Month", "value": "1mo"},
            ],
            value=DEFAULT_INTERVAL,
            style={"width": "120px", "display": "inline-block", "marginRight": "10px"},
        ),
        html.Label("Date Range:"),
        dcc.DatePickerRange(
            id="date-range-picker",
            start_date=DEFAULT_START_DATE,
            end_date=DEFAULT_END_DATE,
            display_format="YYYY-MM-DD",
            style={"display": "inline-block"},
        ),
    ], style={"padding": "20px", "borderBottom": "1px solid #ccc"}),

    dcc.Graph(id="candlestick-chart", figure={}, style={"height": "85vh"}),
])


@app.callback(
    Output("candlestick-chart", "figure"),
    [
        Input("ticker-input", "value"),
        Input("interval-dropdown", "value"),
        Input("date-range-picker", "start_date"),
        Input("date-range-picker", "end_date"),
    ],
)
def update_candlestick_chart(ticker, interval, start_date, end_date):
    if not all([ticker, interval, start_date, end_date]):
        return {}

    ticker = ticker.upper()
    print(f"Updating chart for {ticker} from {start_date} to {end_date} ({interval})...")

    try:
        service = get_data_service()
        start = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
        end = datetime.strptime(end_date[:10], "%Y-%m-%d").date()
        df = service.get_historical_ohlcv(ticker, start, end, interval=interval)
    except Exception as e:
        print(f"An error occurred during data loading: {e}")
        return _empty_figure(f"Error loading {ticker}")

    if df is None or df.empty:
        print(f"DataFrame is empty for {ticker} after data retrieval.")
        return _empty_figure(f"No data for {ticker}")

    return _build_figure(ticker, interval, df)


def _empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        template="plotly_dark",
        annotations=[dict(text=message, showarrow=False, font=dict(size=18))],
    )
    return fig


def _build_figure(ticker: str, interval: str, df: pd.DataFrame) -> go.Figure:
    """3-row figure: candles+SMA (tall), volume bars, RSI subplot."""
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.62, 0.16, 0.22],
        subplot_titles=("", "Volume", f"RSI({_RSI_WINDOW})"),
    )

    # Row 1 — candlesticks
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"],
            name="Price",
        ),
        row=1, col=1,
    )

    # Row 1 — SMA overlays
    for window in _SMA_WINDOWS:
        if len(df) >= window:
            sma = calculate_sma(df["Close"], window=window)
            fig.add_trace(
                go.Scatter(
                    x=df.index, y=sma, mode="lines",
                    name=f"SMA{window}",
                    line=dict(width=1.3, color=_SMA_COLORS[window]),
                ),
                row=1, col=1,
            )

    # Row 2 — volume
    fig.add_trace(
        go.Bar(
            x=df.index, y=df["Volume"],
            name="Volume", marker=dict(color="#5c6bc0"),
        ),
        row=2, col=1,
    )

    # Row 3 — RSI
    if len(df) >= _RSI_WINDOW + 1:
        rsi = calculate_rsi(df["Close"], window=_RSI_WINDOW)
        fig.add_trace(
            go.Scatter(
                x=df.index, y=rsi, mode="lines",
                name=f"RSI({_RSI_WINDOW})",
                line=dict(width=1.3, color="#e0e0e0"),
            ),
            row=3, col=1,
        )
        fig.add_hline(y=70, line=dict(color="#c75450", width=1, dash="dot"), row=3, col=1)
        fig.add_hline(y=30, line=dict(color="#87a96b", width=1, dash="dot"), row=3, col=1)
        fig.update_yaxes(range=[0, 100], row=3, col=1)

    fig.update_layout(
        title=f"{ticker} — {interval}",
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    fig.update_yaxes(title_text="Price", row=1, col=1)

    return fig


if __name__ == "__main__":
    app.run(debug=False, host="127.0.0.1", port=_args.port)
