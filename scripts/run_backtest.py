# projectAlgo/scripts/run_backtest.py
# Run a backtest from the command line. Results are pickled to data/backtest_results/.
#
# Usage (all parameters have defaults matching the original hardcoded values):
#   python -m scripts.run_backtest
#   python -m scripts.run_backtest -t AAPL -s 2023-01-01 -e 2025-01-01 -i 1d
#   python -m scripts.run_backtest -t NVDA --fast-window 20 --slow-window 100 --source schwab

import sys
import os
import argparse
import pickle
from datetime import datetime

from backtesting.engine import Backtester
from strategies.sma_crossover import SMACrossoverStrategy
from core.financial_objects import Stock
from analysis.performance_metrics import analyze_backtest_results

# Registry of available strategies (extend as new strategies are added)
STRATEGY_REGISTRY = {
    'sma-crossover': SMACrossoverStrategy,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run a trading strategy backtest.")
    parser.add_argument('-t', '--ticker', default='ISRG', help="Ticker symbol (default: ISRG)")
    parser.add_argument('-s', '--start', default='2024-01-01', help="Start date YYYY-MM-DD (default: 2024-01-01)")
    parser.add_argument('-e', '--end', default='2025-01-01', help="End date YYYY-MM-DD (default: 2025-01-01)")
    parser.add_argument('-i', '--interval', default='1h', help="Data interval, e.g. 1d 1h 1wk (default: 1h)")
    parser.add_argument('--capital', type=float, default=100000.0, help="Initial capital (default: 100000)")
    parser.add_argument('--slippage', type=int, default=5, help="Slippage in basis points (default: 5)")
    parser.add_argument('--strategy', default='sma-crossover', choices=list(STRATEGY_REGISTRY),
                        help="Strategy to run (default: sma-crossover)")
    parser.add_argument('--fast-window', type=int, default=50, help="Fast SMA window (default: 50)")
    parser.add_argument('--slow-window', type=int, default=200, help="Slow SMA window (default: 200)")
    parser.add_argument('--source', default='yfinance', choices=['yfinance', 'schwab'],
                        help="Data source (default: yfinance)")
    parser.add_argument('--data-dir', default=None,
                        help="Directory for cached historical data (default: data/historical_data under project root)")
    return parser.parse_args()


def main():
    args = parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    historical_data_dir = args.data_dir or os.path.join(project_root, 'data', 'historical_data')
    results_dir = os.path.join(project_root, 'data', 'backtest_results')
    os.makedirs(historical_data_dir, exist_ok=True)
    os.makedirs(results_dir, exist_ok=True)

    strategy_label = f"{args.strategy}_{args.fast_window}_{args.slow_window}"
    date_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_filename = f"{strategy_label}_{args.ticker}_{date_suffix}.pkl"
    results_filepath = os.path.join(results_dir, results_filename)

    print(f"Backtest: {args.ticker} | {args.start} → {args.end} | {args.interval} | source={args.source}")
    print(f"Strategy: {args.strategy} (fast={args.fast_window}, slow={args.slow_window})")
    print(f"Capital: ${args.capital:,.0f}  Slippage: {args.slippage} bps")
    print(f"Results will be saved to: {results_filepath}\n")

    # --- Load data ---
    stock = Stock(args.ticker)
    stock.load_local_data(args.start, args.end, args.interval, data_dir=historical_data_dir)

    if stock.historical_data.empty:
        stock.download_data(args.start, args.end, args.interval,
                            data_dir=historical_data_dir, source=args.source)
        if stock.historical_data.empty:
            raise SystemExit(f"Could not retrieve data for {args.ticker}.")

    data = stock.historical_data.copy()
    print(f"Data loaded: {data.shape[0]} rows.\n")

    # --- Instantiate strategy ---
    StrategyClass = STRATEGY_REGISTRY[args.strategy]
    strategy_name = f"{args.strategy} ({args.fast_window}/{args.slow_window})"
    strategy = StrategyClass(
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        name=strategy_name,
    )

    # --- Run backtest ---
    backtester = Backtester(data, initial_capital=args.capital, slippage_bps=args.slippage)
    equity_curve, trades_df = backtester.run_strategy(strategy)

    if equity_curve is None:
        raise SystemExit("Backtest produced no results.")

    # --- Performance metrics ---
    performance_metrics = analyze_backtest_results(equity_curve, trades_df, args.capital)

    # --- Save results ---
    backtest_results = {
        'equity_curve':       equity_curve,
        'trades_df':          trades_df,
        'processed_data':     backtester.data,
        'performance_metrics': performance_metrics,
        'strategy_name':      strategy_name,
        'initial_capital':    args.capital,
        'slippage_bps':       args.slippage,
        'fast_window':        args.fast_window,
        'slow_window':        args.slow_window,
        'ticker_symbol':      args.ticker,
        'start_date':         args.start,
        'end_date':           args.end,
        'interval':           args.interval,
    }

    with open(results_filepath, 'wb') as f:
        pickle.dump(backtest_results, f)
    print(f"\nResults saved to: {results_filepath}")
    print(f"View with: python visualization/view_backtest.py {results_filepath}")


if __name__ == '__main__':
    main()
