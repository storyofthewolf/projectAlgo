"""Home-screen correlation panel.

Small matrix display, gradient-colored cells, lower triangle + diagonal only.
Pure renderer: receives snapshot updates, never fetches data.
"""
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cockpit.format import correlation_to_color, fmt_corr
from cockpit.themes import THEMES_CONFIG

_EM = "—"
_CELL_FG = "#f0e0c0"  # cream: readable on all gradient backgrounds


class CorrelationPanel(Widget):
    """Renders a CorrelationSnapshot as a small gradient-shaded matrix.

    Renders the lower triangle + diagonal; upper triangle is omitted (symmetric).
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="corr-grid", markup=True)

    def update_snapshot(self, snapshot) -> None:
        self._rebuild(snapshot)

    def _theme_colors(self) -> dict:
        theme_name = getattr(self.app, "theme", "claude-warm")
        return THEMES_CONFIG.get(theme_name, THEMES_CONFIG["claude-warm"])

    def _rebuild(self, snapshot) -> None:
        grid = self.query_one("#corr-grid", Static)

        if snapshot is None:
            grid.update(f"[dim]Loading…[/dim]")
            return

        if snapshot.error or snapshot.matrix is None:
            msg = snapshot.error or "no data"
            grid.update(f"[dim]{_EM} {msg}[/dim]")
            return

        cfg = self._theme_colors()
        text_dim = cfg["text_dim"]
        tickers = list(snapshot.tickers)
        matrix = snapshot.matrix
        n = len(tickers)

        lines = []

        # Header row: ticker labels, right-aligned, upper cols only (skip first)
        header = f"[{text_dim}]{'':7}" + "".join(f"{t:>7}" for t in tickers[1:]) + "[/]"
        lines.append(header)

        for i, row_t in enumerate(tickers):
            row = f"[{text_dim}]{row_t:<6}[/] "
            for j, col_t in enumerate(tickers):
                if j > i:
                    # Upper triangle: blank
                    row += f"{'':7}"
                else:
                    val = matrix.loc[row_t, col_t]
                    formatted = f"{val:>6.2f}"
                    bg = correlation_to_color(val, cfg)
                    row += f"[{_CELL_FG} on {bg}]{formatted}[/] "
            lines.append(row)

        grid.update("\n".join(lines))
