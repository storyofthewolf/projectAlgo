# projectAlgo/visualization/indicator_plot_configs.py

# Import all your technical indicator functions from the analysis module
from analysis.technical_analysis import calculate_sma, calculate_rsi
# from analysis.technical_analysis import calculate_macd # Example for future indicators

# Define the properties for each indicator that are relevant for plotting
INDICATOR_PROPERTIES = {
    'sma': {
        'func': calculate_sma,
        'plot_params': {'panel': 0, 'type': 'line'}, # SMA usually overlays on main chart (panel 0)
        'ylabel_prefix': 'SMA',
        'column_name_format': 'SMA{}' # Format string for generated column name (e.g., SMA20)
    },
    'rsi': {
        'func': calculate_rsi,
        'plot_params': {'panel': 1, 'type': 'line'}, # RSI needs a separate panel (panel 1)
        'ylabel_prefix': 'RSI',
        'column_name_format': 'RSI{}' # Format string for generated column name (e.g., RSI14)
    },
    # Add other indicators here as you implement them:
    # 'macd': {
    #     'func': calculate_macd,
    #     'plot_params': {'panel': 2, 'type': 'line'}, # MACD could be panel 2
    #     'ylabel_prefix': 'MACD',
    #     'column_name_format': 'MACD' # MACD often doesn't use a window in its column name directly
    # },
    # For indicators that produce multiple lines (e.g., MACD with signal line)
    # you might need a slightly more complex structure or separate entries for each line.
    # For now, let's keep it simple with single-line indicators.
}