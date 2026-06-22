"""Account snapshot workflow.

Pure data in, pure data out. No Textual, no asyncio imports.
Wraps broker/account.py so the cockpit (and any other caller) gets a typed,
immutable snapshot instead of a raw dict.

The Schwab account is read-only here — this never places orders.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from broker import schwab_client
from broker.account import get_account_summary


@dataclass(frozen=True)
class PositionRow:
    """One equity/ETF position in the account."""
    ticker: str
    qty: float
    avg_cost: float
    market_value: float
    unrealized_pl: float


@dataclass(frozen=True)
class AccountSnapshot:
    """Result of fetching the account at a point in time.

    `connected` is False when Schwab is not authenticated (no token / no
    credentials) — the panel renders a setup hint in that case. `error` is set
    when authenticated but the fetch failed for some other reason.
    """
    connected: bool
    timestamp: datetime
    account_id: Optional[str] = None
    net_liquidation: Optional[float] = None
    cash_balance: Optional[float] = None
    positions: tuple[PositionRow, ...] = field(default_factory=tuple)
    error: Optional[str] = None


def build_account_snapshot() -> AccountSnapshot:
    """Build an account snapshot.

    Never raises: an unauthenticated or failed fetch is reported via the
    `connected`/`error` fields so the panel can render a graceful message.
    """
    timestamp = datetime.now()

    if not schwab_client.is_authenticated():
        return AccountSnapshot(connected=False, timestamp=timestamp)

    try:
        summary = get_account_summary()
    except Exception as exc:  # defensive — get_account_summary already guards
        return AccountSnapshot(
            connected=True,
            timestamp=timestamp,
            error=str(exc),
        )

    if not summary:
        return AccountSnapshot(
            connected=True,
            timestamp=timestamp,
            error="No account data returned from Schwab.",
        )

    positions = tuple(
        PositionRow(
            ticker=p.get("ticker", "N/A"),
            qty=float(p.get("qty", 0.0)),
            avg_cost=float(p.get("avg_cost", 0.0)),
            market_value=float(p.get("market_value", 0.0)),
            unrealized_pl=float(p.get("unrealized_pl", 0.0)),
        )
        for p in summary.get("positions", [])
    )

    return AccountSnapshot(
        connected=True,
        timestamp=timestamp,
        account_id=summary.get("account_id"),
        net_liquidation=summary.get("net_liquidation"),
        cash_balance=summary.get("cash_balance"),
        positions=positions,
    )
