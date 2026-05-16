# projectAlgo/scripts/correlations.py
# Compute and display pairwise return correlations across a set of tickers.
#
# Usage:
#   python -m scripts.correlations -t AAPL MSFT NVDA GOOGL SPY
#   python -m scripts.correlations -t AAPL MSFT SPY -s 2022-01-01 -e 2025-01-01
#   python -m scripts.correlations -t AAPL MSFT SPY --method spearman --plot
#   python -m scripts.correlations -t AAPL MSFT SPY --source schwab --interval 1wk

import argparse
from datetime import datetime

from analysis.market_analysis import (
    load_aligned_returns,
    calculate_correlation_matrix,
    summarize_correlations,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Compute pairwise return correlations across tickers."
    )
    parser.add_argument('-t', '--tickers', nargs='+', required=True,
                        help="Two or more ticker symbols")
    parser.add_argument('-s', '--start', default='2023-01-01',
                        help="Start date YYYY-MM-DD (default: 2023-01-01)")
    parser.add_argument('-e', '--end',
                        default=datetime.today().strftime('%Y-%m-%d'),
                        help="End date YYYY-MM-DD (default: today)")
    parser.add_argument('-i', '--interval', default='1d',
                        help="Data interval: 1d, 1wk, 1mo (default: 1d)")
    parser.add_argument('--method', default='pearson',
                        choices=['pearson', 'spearman', 'kendall'],
                        help="Correlation method (default: pearson)")
    parser.add_argument('--source', default='yfinance',
                        choices=['yfinance', 'schwab'],
                        help="Data source (default: yfinance)")
    parser.add_argument('--plot', action='store_true',
                        help="Open an interactive heatmap in the browser")
    parser.add_argument('--pairs', action='store_true',
                        help="Also print a ranked list of all ticker pairs")
    return parser.parse_args()


def _color(val: float) -> str:
    """ANSI color for a correlation value printed in the terminal."""
    if val >= 0.7:
        return '\033[92m'   # bright green
    elif val >= 0.4:
        return '\033[32m'   # green
    elif val <= -0.4:
        return '\033[91m'   # red
    return '\033[0m'        # default

RESET = '\033[0m'


def print_matrix(corr):
    tickers = corr.columns.tolist()
    col_w = max(8, max(len(t) for t in tickers) + 2)

    # Header row
    header = ' ' * col_w + ''.join(f'{t:>{col_w}}' for t in tickers)
    print(header)
    print(' ' * col_w + '-' * (col_w * len(tickers)))

    for row_t in tickers:
        row = f'{row_t:<{col_w}}'
        for col_t in tickers:
            val = corr.loc[row_t, col_t]
            if row_t == col_t:
                cell = f'{"1.00":>{col_w}}'
            else:
                c = _color(val)
                cell = f'{c}{val:>{col_w - 1}.2f}{RESET} '
            row += cell
        print(row)


def print_pairs(pairs):
    print(f"\n  {'TICKER A':<10} {'TICKER B':<10} {'CORRELATION':>12}")
    print("  " + "-" * 34)
    for _, row in pairs.iterrows():
        val = row['correlation']
        c = _color(val)
        print(f"  {row['ticker_a']:<10} {row['ticker_b']:<10} {c}{val:>12.4f}{RESET}")


def main():
    args = parse_args()
    tickers = [t.upper() for t in args.tickers]

    if len(tickers) < 2:
        raise SystemExit("At least 2 tickers required.")

    print(f"\nLoading returns for: {' '.join(tickers)}")
    print(f"Period: {args.start} → {args.end}  |  interval={args.interval}"
          f"  |  method={args.method}  |  source={args.source}\n")

    returns = load_aligned_returns(
        tickers=tickers,
        start_date=args.start,
        end_date=args.end,
        interval=args.interval,
        source=args.source,
    )

    if returns.empty:
        raise SystemExit("No return data loaded — check tickers and date range.")

    actual_tickers = returns.columns.tolist()
    n_days = len(returns)
    print(f"Aligned on {n_days} common periods across {len(actual_tickers)} tickers.\n")

    corr = calculate_correlation_matrix(returns, method=args.method)

    print(f"Correlation Matrix ({args.method.capitalize()}):\n")
    print_matrix(corr)

    if args.pairs:
        pairs = summarize_correlations(corr)
        print_pairs(pairs)

    if args.plot:
        from visualization.plot_correlation import plot_correlation_heatmap
        date_range = f"{args.start} to {args.end}"
        plot_correlation_heatmap(
            corr,
            title=f"{args.method.capitalize()} Return Correlation — {date_range} ({args.interval})",
        )

    print()


if __name__ == '__main__':
    main()
