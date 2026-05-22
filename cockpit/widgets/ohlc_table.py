"""OHLCTable widget — scrollable OHLC history for the ticker drill-down screen."""
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cockpit.format import fmt_price
from cockpit.themes import THEMES_CONFIG


class OHLCTable(Widget):
    """Renders a Rich-markup OHLC table. Receives (snapshot, scroll_offset) from screen."""

    can_focus = False

    def compose(self) -> ComposeResult:
        yield Static("", id="ohlc-body", markup=True)

    def update_snapshot(self, snapshot, scroll_offset: int = 0) -> None:
        try:
            body = self.query_one("#ohlc-body", Static)
        except Exception:
            return
        body.update(self._build(snapshot, scroll_offset))

    def _theme(self) -> dict:
        name = getattr(self.app, "theme", "claude-warm")
        return THEMES_CONFIG.get(name, THEMES_CONFIG["claude-warm"])

    def _build(self, snap, scroll_offset: int) -> str:
        cfg = self._theme()
        dim = cfg["text_dim"]

        if snap.error is not None:
            return f"[{dim}]  TICKER NOT FOUND — no history to display[/]"

        if snap.history is None:
            return f"[{dim}]  data unavailable[/]"

        history = snap.history
        display_days = self.app.settings.ticker_detail_config.history_display_days
        total_rows = len(history)

        # Slice: newest-first, with scroll support
        # scroll_offset=0 → most recent display_days rows
        # scroll_offset=N → go N bars earlier
        if scroll_offset > 0:
            end_idx = total_rows - scroll_offset
        else:
            end_idx = total_rows

        start_idx = max(0, end_idx - display_days)
        sliced = history.iloc[start_idx:end_idx]

        # Reverse for newest-first display
        sliced = sliced.iloc[::-1]

        # Header
        header = (
            f"[bold {dim}]{'DATE':<12}{'OPEN':>10}{'HIGH':>10}"
            f"{'LOW':>10}{'CLOSE':>10}[/]"
        )
        sep = f"[{dim}]{'─' * 52}[/]"

        lines = [header, sep]
        for idx, row in sliced.iterrows():
            date_str = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
            o = fmt_price(row.get("Open"))
            h = fmt_price(row.get("High"))
            lo = fmt_price(row.get("Low"))
            c = fmt_price(row.get("Close"))
            lines.append(
                f"{date_str:<12}{o:>10}{h:>10}{lo:>10}{c:>10}"
            )

        # Scroll indicator
        if total_rows > display_days:
            shown_start = scroll_offset
            if scroll_offset > 0:
                scroll_hint = f"  ↑↓ j/k  [+{scroll_offset} earlier bars]"
            else:
                scroll_hint = "  ↑↓ j/k to scroll"
            lines.append(f"\n[{dim}]{scroll_hint}[/]")

        return "\n".join(lines)
