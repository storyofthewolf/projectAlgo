"""Ranked pair list widget for the correlation deep-dive screen.

Displays correlation pairs sorted high → low with text-color from the gradient.
"""
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cockpit.format import correlation_to_color
from cockpit.themes import THEMES_CONFIG

_EM = "—"


class RankedPairList(Widget):
    """Ordered list of ticker pairs with their correlation, highest first."""

    def compose(self) -> ComposeResult:
        yield Static("", id="pair-list-body", markup=True)

    def update_snapshot(self, snapshot) -> None:
        body = self.query_one("#pair-list-body", Static)

        if snapshot is None:
            body.update("[dim]Loading…[/dim]")
            return

        if snapshot.error or not snapshot.ranked_pairs:
            msg = snapshot.error or "no pairs"
            body.update(f"[dim]{_EM}  {msg}[/dim]")
            return

        cfg = self._theme_colors()
        text_dim = cfg["text_dim"]

        lines = []
        header = f"[{text_dim}]{'TICKER A':<10} {'TICKER B':<10} {'CORR':>7}[/]"
        lines.append(header)
        lines.append(f"[{text_dim}]{'─' * 29}[/]")

        for pair in snapshot.ranked_pairs:
            color = correlation_to_color(pair.correlation, cfg)
            sign = "+" if pair.correlation >= 0 else ""
            corr_str = f"{sign}{pair.correlation:.2f}"
            lines.append(
                f"{pair.ticker_a:<10} {pair.ticker_b:<10} "
                f"[{color}]{corr_str:>7}[/]"
            )

        body.update("\n".join(lines))

    def _theme_colors(self) -> dict:
        theme_name = getattr(self.app, "theme", "claude-warm")
        return THEMES_CONFIG.get(theme_name, THEMES_CONFIG["claude-warm"])
