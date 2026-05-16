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
import logging
import pickle
from datetime import datetime

from backtesting.engine import Backtester
from strategies.sma_crossover import SMACrossoverStrategy
from core.security import Stock
from analysis.performance_metrics import analyze_backtest_results
from marketdata.service import get_data_service

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

STRATEGY_REGISTRY = {
    'sma-crossover': SMACrossoverStrategy,
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run a trading strategy backtest.")
    parser.add_argument('-t', '--ticker', default='ISRG', help="Ticker symbol (default: ISRG)")
    parser.add_argument('-s', '--start', default='2024-01-01', help="Start date YYYY-MM-DD (default: 2024-01-01)")
    parser.add_argument('-e', '--end', default='2025-01-01', help="End date YYYY-MM-DD (default: 2025-01-01)")
    parser.add_argument('-i', '--interval', default='1d', help="Data interval, e.g. 1d 1wk (default: 1d)")
    parser.add_argument('--capital', type=float, default=100000.0, help="Initial capital (default: 100000)")
    parser.add_argument('--slippage', type=int, default=5, help="Slippage in basis points (default: 5)")
    parser.add_argument('--strategy', default='sma-crossover', choices=list(STRATEGY_REGISTRY),
                        help="Strategy to run (default: sma-crossover)")
    parser.add_argument('--fast-window', type=int, default=50, help="Fast SMA window (default: 50)")
    parser.add_argument('--slow-window', type=int, default=200, help="Slow SMA window (default: 200)")
    parser.add_argument('--source', default=None, choices=['yfinance', 'schwab'],
                        help="Data source override (default: uses cockpit.toml preferred_source)")
    return parser.parse_args()


def main():
    args = parse_args()

    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    results_dir = os.path.join(project_root, 'data', 'backtest_results')
    os.makedirs(results_dir, exist_ok=True)

    strategy_label = f"{args.strategy}_{args.fast_window}_{args.slow_window}"
    date_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_filename = f"{strategy_label}_{args.ticker}_{date_suffix}.pkl"
    results_filepath = os.path.join(results_dir, results_filename)

    print(f"Backtest: {args.ticker} | {args.start} → {args.end} | {args.interval} | source={args.source or 'preferred'}")
    print(f"Strategy: {args.strategy} (fast={args.fast_window}, slow={args.slow_window})")
    print(f"Capital: ${args.capital:,.0f}  Slippage: {args.slippage} bps")
    print(f"Results will be saved to: {results_filepath}\n")

    start = datetime.strptime(args.start, '%Y-%m-%d').date()
    end = datetime.strptime(args.end, '%Y-%m-%d').date()

    service = get_data_service()
    df = service.get_historical_ohlcv(
        args.ticker, start, end, interval=args.interval, source=args.source
    )
    if df.empty:
        raise SystemExit(f"Could not retrieve data for {args.ticker}.")

    stock = Stock(ticker=args.ticker, historical_data=df)
    data = stock.historical_data.copy()
    print(f"Data loaded: {data.shape[0]} rows.\n")

    StrategyClass = STRATEGY_REGISTRY[args.strategy]
    strategy_name = f"{args.strategy} ({args.fast_window}/{args.slow_window})"
    strategy = StrategyClass(
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        name=strategy_name,
    )

    backtester = Backtester(data, initial_capital=args.capital, slippage_bps=args.slippage)
    equity_curve, trades_df = backtester.run_strategy(strategy)

    if equity_curve is None:
        raise SystemExit("Backtest produced no results.")

    performance_metrics = analyze_backtest_results(equity_curve, trades_df, args.capital)

    backtest_results = {
        'equity_curve':        equity_curve,
        'trades_df':           trades_df,
        'processed_data':      backtester.data,
        'performance_metrics': performance_metrics,
        'strategy_name':       strategy_name,
        'initial_capital':     args.capital,
        'slippage_bps':        args.slippage,
        'fast_window':         args.fast_window,
        'slow_window':         args.slow_window,
        'ticker_symbol':       args.ticker,
        'start_date':          args.start,
        'end_date':            args.end,
        'interval':            args.interval,
    }

    with open(results_filepath, 'wb') as f:
        pickle.dump(backtest_results, f)
    print(f"\nResults saved to: {results_filepath}")
    print(f"View with: python visualization/view_backtest.py {results_filepath}")


if __name__ == '__main__':
    main()
