"""Full N×N correlation matrix widget for the deep-dive screen.

Renders the complete symmetric matrix with gradient-colored cells.
Same approach as SectorTable: Rich markup string in a single Static widget.
"""
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cockpit.format import correlation_to_color
from cockpit.themes import THEMES_CONFIG

_EM = "—"
_CELL_FG = "#f0e0c0"
_COL_W = 8  # width per cell (including label alignment)


class CorrelationTable(Widget):
    """Full correlation matrix renderer. Passive — updated via update_snapshot()."""

    def compose(self) -> ComposeResult:
        yield Static("", id="corr-table-body", markup=True)

    def update_snapshot(self, snapshot) -> None:
        body = self.query_one("#corr-table-body", Static)

        if snapshot is None:
            body.update("[dim]Loading…[/dim]")
            return

        if snapshot.error or snapshot.matrix is None:
            msg = snapshot.error or "no data"
            body.update(f"[dim]{_EM}  {msg}[/dim]")
            return

        cfg = self._theme_colors()
        text_dim = cfg["text_dim"]
        tickers = list(snapshot.tickers)
        matrix = snapshot.matrix

        lines = []

        # Header row
        header = f"[{text_dim}]{'':8}" + "".join(f"{t:>{_COL_W}}" for t in tickers) + "[/]"
        lines.append(header)

        sep_width = 8 + len(tickers) * _COL_W
        lines.append(f"[{text_dim}]{'─' * sep_width}[/]")

        for row_t in tickers:
            row = f"[{text_dim}]{row_t:<7}[/] "
            for col_t in tickers:
                val = matrix.loc[row_t, col_t]
                formatted = f"{val:>6.2f} "
                bg = correlation_to_color(val, cfg)
                row += f"[{_CELL_FG} on {bg}]{formatted}[/]"
            lines.append(row)

        body.update("\n".join(lines))

    def _theme_colors(self) -> dict:
        theme_name = getattr(self.app, "theme", "claude-warm")
        return THEMES_CONFIG.get(theme_name, THEMES_CONFIG["claude-warm"])
