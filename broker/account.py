# projectAlgo/broker/account.py
# Fetches account balances, positions, and open orders from Schwab
# and formats them for CLI display.

from broker.schwab_client import get_client


def get_account_summary() -> dict:
    """
    Returns a dict with keys:
        account_id       - masked account identifier
        net_liquidation  - total account value
        cash_balance     - available cash
        positions        - list of dicts: ticker, qty, avg_cost, market_value, unrealized_pl
    Returns an empty dict on failure.
    """
    try:
        client = get_client()
    except Exception as e:
        print(f"Schwab authentication error: {e}")
        return {}

    try:
        import schwab
        resp = client.get_accounts(fields=[schwab.client.Client.Account.Fields.POSITIONS])
        resp.raise_for_status()
        accounts = resp.json()

        if not accounts:
            print("No accounts found.")
            return {}

        # Use the first account if multiple exist
        acct = accounts[0]
        acct_id = acct.get('securitiesAccount', {}).get('accountNumber', 'N/A')
        balances = acct.get('securitiesAccount', {}).get('currentBalances', {})

        positions_raw = acct.get('securitiesAccount', {}).get('positions', [])
        positions = []
        for p in positions_raw:
            instrument = p.get('instrument', {})
            symbol = instrument.get('symbol', 'N/A')
            if instrument.get('assetType') not in ('EQUITY', 'ETF', None):
                continue
            positions.append({
                'ticker':        symbol,
                'qty':           p.get('longQuantity', 0.0),
                'avg_cost':      p.get('averagePrice', 0.0),
                'market_value':  p.get('marketValue', 0.0),
                'unrealized_pl': p.get('unrealizedProfitLoss', 0.0),
            })

        return {
            'account_id':      acct_id,
            'net_liquidation': balances.get('liquidationValue', 0.0),
            'cash_balance':    balances.get('cashBalance', 0.0),
            'positions':       positions,
        }

    except Exception as e:
        print(f"Error fetching account data from Schwab: {e}")
        return {}


def format_positions_table(summary: dict) -> str:
    """Formats the positions list as a fixed-width CLI table."""
    positions = summary.get('positions', [])
    if not positions:
        return "  No open positions."

    header = f"  {'TICKER':<8} {'QTY':>8} {'AVG COST':>10} {'MKT VALUE':>12} {'UNREALIZED P/L':>16}"
    sep = "  " + "-" * (len(header) - 2)
    rows = [header, sep]
    for p in positions:
        pl_str = f"{p['unrealized_pl']:>+.2f}"
        rows.append(
            f"  {p['ticker']:<8} {p['qty']:>8.2f} {p['avg_cost']:>10.2f} "
            f"{p['market_value']:>12.2f} {pl_str:>16}"
        )
    return "\n".join(rows)


def format_balances(summary: dict) -> str:
    """Formats account balances as a CLI-friendly string."""
    if not summary:
        return "  No account data available."
    return (
        f"  Account:          {summary.get('account_id', 'N/A')}\n"
        f"  Net Liquidation:  ${summary.get('net_liquidation', 0.0):>12,.2f}\n"
        f"  Cash Balance:     ${summary.get('cash_balance', 0.0):>12,.2f}"
    )
