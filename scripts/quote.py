# projectAlgo/scripts/quote.py
# Fetch live quotes for one or more tickers.
#
# Usage:
#   python -m scripts.quote AAPL
#   python -m scripts.quote AAPL MSFT ISRG NVDA

import argparse
from broker.schwab_client import is_authenticated
from marketdata.service import get_data_service


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
    service = get_data_service()
    quotes = service.get_live_quotes(tickers, source='schwab')

    if not quotes:
        raise SystemExit("No quote data returned.")

    print()
    header = f"  {'TICKER':<8} {'LAST':>10} {'BID':>10} {'ASK':>10} {'VOLUME':>12} {'CHANGE':>10} {'CHG %':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for ticker, q in quotes.items():
        change = q.change or 0.0
        change_pct = (q.change_pct or 0.0) * 100
        chg_str = f"{change:>+.2f}"
        pct_str = f"{change_pct:>+.2f}%"
        print(
            f"  {q.ticker:<8} {q.price:>10.2f} {q.bid or 0.0:>10.2f} "
            f"{q.ask or 0.0:>10.2f} {q.volume or 0:>12,} {chg_str:>10} {pct_str:>8}"
        )
    print()


if __name__ == '__main__':
    main()
