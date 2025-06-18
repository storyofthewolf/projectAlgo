# projectAlgo/analysis/performance_metrics.py

import pandas as pd
import numpy as np

def calculate_returns(equity_curve: pd.Series) -> pd.Series:
    """Calculates daily returns from an equity curve."""
    return equity_curve.pct_change().dropna()

def calculate_total_return(equity_curve: pd.Series) -> float:
    """Calculates the total return percentage."""
    if equity_curve.empty or equity_curve.iloc[0] == 0:
        return 0.0
    return ((equity_curve.iloc[-1] - equity_curve.iloc[0]) / equity_curve.iloc[0]) * 100

def calculate_annualized_return(equity_curve: pd.Series, periods_per_year: int = 252) -> float:
    """
    Calculates the annualized return.
    Assumes periods_per_year (e.g., 252 for daily, 12 for monthly).
    """
    if equity_curve.empty or len(equity_curve) < 2 or equity_curve.iloc[0] == 0:
        return 0.0
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
    num_years = len(equity_curve) / periods_per_year
    if num_years <= 0: # Handle cases with less than a year of data
        return total_return * 100 # Return total return as percentage if less than a year
    return ((1 + total_return)**(1/num_years) - 1) * 100

def calculate_max_drawdown(equity_curve: pd.Series) -> tuple[float, pd.Timestamp, pd.Timestamp]:
    """
    Calculates the maximum drawdown and its start/end dates.
    Returns (max_drawdown_percentage, drawdown_start_date, drawdown_end_date).
    """
    if equity_curve.empty:
        return 0.0, None, None

    # Calculate the running maximum of the equity curve
    running_max = equity_curve.cummax()
    # Calculate the daily drawdown
    drawdown = (equity_curve / running_max - 1) * 100

    max_drawdown_value = drawdown.min()
    end_date = drawdown.idxmin()

    # Find the start date of the max drawdown: the last peak before the max drawdown's end date
    peak_slice = running_max.loc[:end_date]
    if peak_slice.empty: # Edge case for very short or flat curves
        peak_date = equity_curve.index[0]
    else:
        peak_date = peak_slice.idxmax()

    return max_drawdown_value, peak_date, end_date

def calculate_sharpe_ratio(equity_curve: pd.Series, risk_free_rate: float = 0.02, periods_per_year: int = 252) -> float:
    """
    Calculates the Sharpe Ratio.
    Args:
        equity_curve (pd.Series): The equity curve.
        risk_free_rate (float): Annual risk-free rate (e.g., 0.02 for 2%).
        periods_per_year (int): Number of periods per year (e.g., 252 for daily).
    """
    returns = calculate_returns(equity_curve)
    if returns.empty or returns.std() == 0:
        return 0.0

    # Convert annual risk-free rate to daily
    daily_risk_free_rate = (1 + risk_free_rate)**(1/periods_per_year) - 1

    excess_returns = returns - daily_risk_free_rate
    
    if excess_returns.std() == 0:
        return 0.0 # Avoid division by zero
    
    sharpe_ratio = np.sqrt(periods_per_year) * (excess_returns.mean() / excess_returns.std())
    return sharpe_ratio

def calculate_trade_metrics(trades: pd.DataFrame) -> dict:
    """
    Calculates various trade-related metrics.
    Args:
        trades (pd.DataFrame): DataFrame of trades with 'type' and 'profit_loss' columns.
    Returns:
        dict: A dictionary of trade metrics.
    """
    metrics = {
        'total_trades': 0,
        'winning_trades': 0,
        'losing_trades': 0,
        'win_rate': 0.0,
        'average_win': 0.0,
        'average_loss': 0.0,
        'profit_factor': 0.0
    }

    if trades.empty:
        return metrics

    # Filter for realized profit/loss from 'SELL' trades
    sell_trades = trades[trades['type'] == 'SELL'].copy()

    if sell_trades.empty:
        return metrics

    winning_trades_pl = sell_trades[sell_trades['profit_loss'] > 0]['profit_loss']
    losing_trades_pl = sell_trades[sell_trades['profit_loss'] < 0]['profit_loss']

    metrics['total_trades'] = len(sell_trades) # Only count completed (sell) trades for these metrics
    metrics['winning_trades'] = len(winning_trades_pl)
    metrics['losing_trades'] = len(losing_trades_pl)
    
    if metrics['total_trades'] > 0:
        metrics['win_rate'] = (metrics['winning_trades'] / metrics['total_trades']) * 100

    if not winning_trades_pl.empty:
        metrics['average_win'] = winning_trades_pl.mean()
    if not losing_trades_pl.empty:
        metrics['average_loss'] = losing_trades_pl.mean() # This will be negative
    
    total_gross_profit = winning_trades_pl.sum()
    total_gross_loss = abs(losing_trades_pl.sum()) # Take absolute value for profit factor denominator

    if total_gross_loss > 0:
        metrics['profit_factor'] = total_gross_profit / total_gross_loss
    elif total_gross_profit > 0: # All wins, no losses
        metrics['profit_factor'] = float('inf') # Infinite profit factor
    else: # No wins, no losses, or only 0 P/L trades
        metrics['profit_factor'] = 0.0

    return metrics

def analyze_backtest_results(equity_curve: pd.Series, trades: pd.DataFrame, initial_capital: float) -> dict:
    """
    Aggregates all performance metrics into a single dictionary.
    """
    results = {}

    results['initial_capital'] = initial_capital
    results['final_capital'] = equity_curve.iloc[-1] if not equity_curve.empty else initial_capital

    results['total_return_pct'] = calculate_total_return(equity_curve)
    results['annualized_return_pct'] = calculate_annualized_return(equity_curve)
    
    max_drawdown_pct, drawdown_peak, drawdown_trough = calculate_max_drawdown(equity_curve)
    results['max_drawdown_pct'] = max_drawdown_pct
    results['drawdown_peak_date'] = drawdown_peak
    results['drawdown_trough_date'] = drawdown_trough

    results['sharpe_ratio'] = calculate_sharpe_ratio(equity_curve)
    
    trade_metrics = calculate_trade_metrics(trades)
    results.update(trade_metrics) # Add trade-specific metrics

    return results