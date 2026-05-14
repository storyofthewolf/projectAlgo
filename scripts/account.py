# projectAlgo/scripts/account.py
# Display Schwab account balances and positions from the command line.
#
# Usage:
#   python -m scripts.account                   # balances + positions
#   python -m scripts.account --balances-only   # balances only
#   python -m scripts.account --positions-only  # positions only

import argparse
from broker.schwab_client import is_authenticated
from broker.account import get_account_summary, format_balances, format_positions_table


def main():
    parser = argparse.ArgumentParser(description="Display Schwab account summary.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--balances-only', action='store_true', help="Show balances only")
    group.add_argument('--positions-only', action='store_true', help="Show positions only")
    args = parser.parse_args()

    if not is_authenticated():
        raise SystemExit(
            "Not authenticated with Schwab.\n"
            "Run 'python -m scripts.schwab_auth' to log in."
        )

    summary = get_account_summary()
    if not summary:
        raise SystemExit("Failed to retrieve account data.")

    if not args.positions_only:
        print("\nBALANCES")
        print(format_balances(summary))

    if not args.balances_only:
        print("\nPOSITIONS")
        print(format_positions_table(summary))

    print()


if __name__ == '__main__':
    main()
