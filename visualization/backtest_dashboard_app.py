# projectAlgo/visualization/backtest_dashboard_app.py

import dash
from dash import html, dcc, dash_table
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import sys
import os
import pickle # Used for loading saved Python objects

# --- PATH SETUP for projectAlgo root ---
# Adjust path to import modules from projectAlgo root
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..', '..') # Go up two levels to reach 'projectAlgo'
sys.path.insert(0, project_root)
# --- END PATH SETUP ---

# --- Function to Load Backtest Results ---
def load_backtest_results(filepath: str):
    """Loads backtest results from a pickled file."""
    try:
        with open(filepath, 'rb') as f:
            results = pickle.load(f)
        
        # Ensure all expected components are present
        required_keys = ['equity_curve', 'trades_df', 'processed_data', 'performance_metrics', 'strategy_name', 'initial_capital', 'slippage_bps']
        for key in required_keys:
            if key not in results:
                raise ValueError(f"Missing key '{key}' in loaded results file.")
        
        return (results['equity_curve'], results['trades_df'], 
                results['processed_data'], results['performance_metrics'],
                results['strategy_name'], results['initial_capital'], results['slippage_bps'])
    except FileNotFoundError:
        print(f"Error: Results file not found at '{filepath}'.")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading backtest results from '{filepath}': {e}")
        sys.exit(1)

# --- Main Logic for Data Loading ---
# This app now expects the results file path as a command-line argument
if len(sys.argv) < 2:
    print("Usage: python backtest_dashboard_app.py <path_to_backtest_results_file>")
    sys.exit(1)

results_filepath = sys.argv[1]
(equity_curve, trades_df, processed_data, performance_metrics, 
 strategy_name, initial_capital_value, slippage_bps_value) = load_backtest_results(results_filepath)

# --- IMPORTANT: Ensure 'date' column is Datetime for plotting, if trades_df is not empty ---
# CHANGED: Confirming 'date' column for conversion
if not trades_df.empty and 'date' in trades_df.columns:
    trades_df['date'] = pd.to_datetime(trades_df['date']) # Ensure it's datetime

# Handle potential empty results after loading (e.g., if a backtest truly yielded no trades)
if equity_curve.empty:
    equity_curve = pd.Series([initial_capital_value], index=[pd.Timestamp.now()])
if trades_df.empty:
    # CHANGED: Recreate with confirmed column names: 'date' and 'profit_loss'
    trades_df = pd.DataFrame(columns=['date', 'type', 'price', 'shares', 'cost_basis', 'profit_loss'])
    
# --- Initialize the Dash app ---
app = dash.Dash(__name__, external_stylesheets=['https://codepen.io/chriddyp/pen/bWLwgP.css']) # Basic CSS

# --- Prepare Data for Plotly Figures ---

# OHLC Chart
ohlc_data = go.Candlestick(
    x=processed_data.index,
    open=processed_data['Open'],
    high=processed_data['High'],
    low=processed_data['Low'],
    close=processed_data['Close'],
    name='OHLC',
    increasing_line_color='green', 
    decreasing_line_color='red'
)

# Indicators (dynamic check for existence based on processed_data)
indicator_traces = []
# You can extend this logic to check for other indicator columns as your strategies add them
for col in processed_data.columns:
    if col.startswith('SMA_'):
        indicator_traces.append(go.Scatter(
            x=processed_data.index, y=processed_data[col], mode='lines',
            name=col.replace('_', ' '), line=dict(width=1),
            # Assign different colors dynamically if desired, or hardcode for known indicators
            line_color='blue' if 'Fast' in col else 'red' if 'Slow' in col else None,
            hovertemplate=f'Date: %{{x}}<br>{col.replace("_", " ")}: %{{y:.2f}}<extra></extra>'
        ))

# BUY/SELL Signals
buy_signals = trades_df[trades_df['type'] == 'BUY']
sell_signals = trades_df[trades_df['type'] == 'SELL']

buy_signal_scatter = go.Scatter(
    x=buy_signals['date'], y=buy_signals['price'], mode='markers', name='Buy Signal', # CONFIRMED: 'date'
    marker=dict(symbol='triangle-up', size=10, color='lime'),
    hovertemplate='Date: %{x}<br>Buy Price: %{y:.2f}<br>Shares: %{customdata[0]}<extra></extra>',
    customdata=buy_signals[['shares']].values
)

sell_signal_scatter = go.Scatter(
    x=sell_signals['date'], y=sell_signals['price'], mode='markers', name='Sell Signal', # CONFIRMED: 'date'
    marker=dict(symbol='triangle-down', size=10, color='magenta'),
    hovertemplate='Date: %{x}<br>Sell Price: %{y:.2f}<br>Shares: %{customdata[0]}<br>P/L: %{customdata[1]:.2f}<extra></extra>',
    customdata=sell_signals[['shares', 'profit_loss']].values # CONFIRMED: 'profit_loss'
)

# Equity Curve
equity_curve_trace = go.Scatter(
    x=equity_curve.index, y=equity_curve, mode='lines', name='Equity Curve',
    line=dict(color='cyan', width=2), fill='tozeroy', fillcolor='rgba(0,255,255,0.1)',
    hovertemplate='Date: %{x}<br>Equity: %{y:,.2f}<extra></extra>'
)

# --- Create Plotly Figure with Subplots ---
fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
    row_heights=[0.7, 0.3], subplot_titles=[f'OHLC, Indicators & Trades for {strategy_name}', 'Equity Curve']
)

# Add traces to the first subplot (OHLC, Indicators, Signals)
fig.add_trace(ohlc_data, row=1, col=1)
for trace in indicator_traces:
    fig.add_trace(trace, row=1, col=1)
fig.add_trace(buy_signal_scatter, row=1, col=1)
fig.add_trace(sell_signal_scatter, row=1, col=1)

# Add Equity Curve to the second subplot
fig.add_trace(equity_curve_trace, row=2, col=1)

fig.update_layout(
    title_text=f"Algorithmic Trading Backtest Results",
    xaxis_rangeslider_visible=False, hovermode="x unified", template="plotly_dark", height=850,
    margin=dict(l=40, r=40, t=80, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
fig.update_xaxes(showgrid=True, zeroline=False, row=1, col=1)
fig.update_yaxes(title_text="Price", showgrid=True, zeroline=False, row=1, col=1)
fig.update_xaxes(title_text="Date", showgrid=True, zeroline=False, row=2, col=1)
fig.update_yaxes(title_text="Portfolio Value", showgrid=True, zeroline=False, row=2, col=1)

# --- Format Performance Metrics for Display ---
metrics_display_items = []
metric_order = [
    'initial_capital', 'final_capital', 'total_return_pct', 'annualized_return_pct',
    'max_drawdown_pct', 'drawdown_peak_date', 'drawdown_trough_date', 'sharpe_ratio',
    'total_trades', 'winning_trades', 'losing_trades', 'win_rate',
    'average_win', 'average_loss', 'profit_factor'
]

for key in metric_order:
    value = performance_metrics.get(key)
    formatted_value = ''
    if key in ['initial_capital', 'final_capital', 'average_win', 'average_loss']:
        formatted_value = f"${value:,.2f}" if isinstance(value, (int, float)) else "N/A"
    elif key.endswith('_pct'):
        formatted_value = f"{value:,.2f}%" if isinstance(value, (int, float)) else "N/A"
    elif key in ['sharpe_ratio', 'profit_factor']:
        formatted_value = f"{value:,.2f}" if isinstance(value, (int, float)) else "N/A"
    elif isinstance(value, pd.Timestamp):
        formatted_value = value.strftime('%Y-%m-%d')
    else:
        formatted_value = str(value)

    metrics_display_items.append(html.Div([
        html.Strong(f"{key.replace('_', ' ').title()}:"),
        html.Span(formatted_value, style={'margin-left': '10px'})
    ], style={'margin-bottom': '5px'}))

# --- Dash App Layout ---
app.layout = html.Div(children=[
    html.H1(children='Algorithmic Trading Backtest Dashboard', style={'textAlign': 'center', 'color': '#FFFFFF', 'padding-top': '20px'}),

    html.Div(children=[
        html.H2(f"Strategy: {strategy_name}", style={'color': '#ADD8E6'}),
        html.P(f"Initial Capital: ${initial_capital_value:,.2f}", style={'color': '#D3D3D3'}),
        html.P(f"Slippage: {slippage_bps_value} bps", style={'color': '#D3D3D3'}),
    ], style={'textAlign': 'center', 'margin-bottom': '30px', 'background-color': '#333333', 'padding': '15px', 'border-radius': '8px'}),

    html.Div([
        dcc.Graph(
            id='backtest-chart',
            figure=fig
        )
    ]),

    html.H2(children='Performance Metrics', style={'textAlign': 'center', 'margin-top': '40px', 'color': '#FFFFFF'}),
    html.Div(children=metrics_display_items, style={
        'display': 'grid',
        'grid-template-columns': 'repeat(auto-fit, minmax(300px, 1fr))',
        'gap': '15px',
        'width': '90%',
        'margin': 'auto',
        'padding': '25px',
        'border': '1px solid #555555',
        'border-radius': '10px',
        'background-color': '#282828',
        'color': '#E0E0E0',
        'box-shadow': '0px 0px 15px rgba(0,255,255,0.2)'
    }),
    
    html.H2(children='Trade Log', style={'textAlign': 'center', 'margin-top': '40px', 'color': '#FFFFFF'}),
    html.Div([
        dash_table.DataTable(
            id='trades-table',
            # This line dynamically gets columns. 'id' will be 'profit_loss' based on your data
            columns=[{"name": i.replace('_', ' ').title(), "id": i} for i in trades_df.columns], 
            data=trades_df.to_dict('records'),
            sort_action="native",
            filter_action="native",
            page_action="native",
            page_size=10,
            style_table={'overflowX': 'auto', 'margin': 'auto', 'width': '90%', 'border-radius': '10px'},
            style_cell={
                'textAlign': 'left',
                'minWidth': '80px', 'width': '120px', 'maxWidth': '180px',
                'whiteSpace': 'normal',
                'backgroundColor': '#1E1E1E',
                'color': '#E0E0E0',
                'border': '1px solid #333333'
            },
            style_header={
                'backgroundColor': '#333333',
                'fontWeight': 'bold',
                'color': '#FFFFFF'
            },
            style_data_conditional=[
                # CONFIRMED: 'profit_loss' for styling conditions
                {'if': {'column_id': 'profit_loss', 'filter_query': '{profit_loss} > 0'}, 
                 'color': 'lime'},
                {'if': {'column_id': 'profit_loss', 'filter_query': '{profit_loss} < 0'}, 
                 'color': 'magenta'}
            ]
        )
    ], style={'display': 'flex', 'justifyContent': 'center', 'margin-bottom': '50px', 'padding-bottom': '20px'})
], style={'backgroundColor': '#121212', 'font-family': 'Arial, sans-serif'})

if __name__ == '__main__':
    print(f"\n--- Starting Backtest Dash App ---")
    print(f"To run this app, you must provide a path to a backtest results file.")
    print(f"Example: python backtest_dashboard_app.py ../data/backtest_results_sma.pkl")
    print(f"Navigate your web browser to: http://127.0.0.1:8050/")
    print(f"Press Ctrl+C in the terminal to stop the server.")
    app.run(debug=True)