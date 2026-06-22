"""Account panel widget.

Renders the Schwab account balances and positions inside a PanelFrame.
Consumed by HomeScreen. Read-only — this never places orders.

When Schwab is not authenticated it shows a short setup hint; on fetch error
it shows the error. Otherwise it shows net liquidation, cash, and a compact
positions table.
"""
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

_EM = "—"

_SETUP_HINT = (
    "\n Schwab not connected.\n\n"
    " Run:\n"
    "  python -m scripts.schwab_auth\n\n"
    " See CLAUDE.md for setup."
)


def _signed_color(value: float, text: str) -> str:
    if value > 0:
        return f"[$positive]{text}[/$positive]"
    if value < 0:
        return f"[$negative]{text}[/$negative]"
    return text


class AccountPanel(Widget):
    """Account balances + positions panel for the home screen."""

    DEFAULT_CSS = """
    AccountPanel {
        height: 1fr;
        width: 1fr;
    }
    AccountPanel Static {
        height: 1fr;
        color: $text-primary;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(_SETUP_HINT, id="account-body")

    def update_snapshot(self, snapshot) -> None:
        """Re-render the panel from an AccountSnapshot."""
        body = self.query_one("#account-body", Static)
        body.update(self._build_markup(snapshot))

    def _build_markup(self, snapshot) -> str:
        if not snapshot.connected:
            return _SETUP_HINT

        if snapshot.error:
            return f"[$negative]{snapshot.error}[/$negative]"

        net = snapshot.net_liquidation
        cash = snapshot.cash_balance
        net_str = f"${net:,.2f}" if net is not None else _EM
        cash_str = f"${cash:,.2f}" if cash is not None else _EM
        acct_str = snapshot.account_id or _EM

        lines = [
            f"[bold $text-dim]ACCOUNT[/bold $text-dim]  {acct_str}",
            f"[bold $text-dim]NET LIQ[/bold $text-dim]  {net_str}",
            f"[bold $text-dim]CASH   [/bold $text-dim]  {cash_str}",
            "",
        ]

        if not snapshot.positions:
            lines.append("[$text-dim] No open positions.[/$text-dim]")
        else:
            lines.append(
                "[bold $text-dim]"
                f"{'TICKER':<7}{'QTY':>6}{'MKT VAL':>12}{'P/L':>11}"
                "[/bold $text-dim]"
            )
            for p in snapshot.positions:
                mv = f"{p.market_value:,.0f}"
                # Pad the plain P/L string first so column width is correct,
                # then wrap the already-padded text in color markup.
                pl_plain = f"{p.unrealized_pl:+,.0f}".rjust(11)
                pl = _signed_color(p.unrealized_pl, pl_plain)
                lines.append(
                    f"{p.ticker:<7}{p.qty:>6.0f}{mv:>12}{pl}"
                )

        ts = snapshot.timestamp.strftime("%H:%M:%S")
        lines.append("")
        lines.append(f"[dim]as of {ts}[/dim]")
        return "\n".join(lines)
