# projectAlgo/scripts/quote.py
# Fetch live quotes for one or more tickers from Schwab.
#
# Usage:
#   python -m scripts.quote AAPL
#   python -m scripts.quote AAPL MSFT ISRG NVDA

import argparse
from broker.schwab_client import is_authenticated
from broker.market_data import get_live_quotes


def main():
    parser = argparse.ArgumentParser(description="Fetch live quotes from Schwab.")
    parser.add_argument('tickers', nargs='+', help="One or more ticker symbols")
    args = parser.parse_args()

    if not is_authenticated():
        raise SystemExit(
            "Not authenticated with Schwab.\n"
            "Run 'python -m scripts.schwab_auth' to log in."
        )

    tickers = [t.upper() for t in args.tickers]
    df = get_live_quotes(tickers)

    if df.empty:
        raise SystemExit("No quote data returned.")

    print()
    header = f"  {'TICKER':<8} {'LAST':>10} {'BID':>10} {'ASK':>10} {'VOLUME':>12} {'CHANGE':>10} {'CHG %':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for _, row in df.iterrows():
        chg_str = f"{row['change']:>+.2f}"
        pct_str = f"{row['change_pct']:>+.2f}%"
        print(
            f"  {row['ticker']:<8} {row['last_price']:>10.2f} {row['bid']:>10.2f} "
            f"{row['ask']:>10.2f} {int(row['volume']):>12,} {chg_str:>10} {pct_str:>8}"
        )
    print()


if __name__ == '__main__':
    main()
