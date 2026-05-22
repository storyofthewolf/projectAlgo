"""TickerHeader widget — header strip for the ticker drill-down screen."""
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cockpit.format import (
    fmt_arrow,
    fmt_change,
    fmt_pct,
    fmt_price,
    fmt_volume,
)
from cockpit.themes import THEMES_CONFIG


class TickerHeader(Widget):
    """Three-row header: ticker/name, price/change, day range / 52w range."""

    can_focus = False

    def compose(self) -> ComposeResult:
        yield Static("", id="th-body", markup=True)

    def update_snapshot(self, snapshot) -> None:
        try:
            body = self.query_one("#th-body", Static)
        except Exception:
            return
        body.update(self._build(snapshot))

    def _theme(self) -> dict:
        name = getattr(self.app, "theme", "claude-warm")
        return THEMES_CONFIG.get(name, THEMES_CONFIG["claude-warm"])

    def _build(self, snap) -> str:
        cfg = self._theme()
        pos = cfg["positive"]
        neg = cfg["negative"]
        dim = cfg["text_dim"]

        # Error state
        if snap.error is not None:
            return f"[bold red]  TICKER NOT FOUND: {snap.ticker}[/bold red]"

        # Row 1: ticker + name + timestamp
        name_part = f" — {snap.name}" if snap.name else ""
        ts_str = snap.timestamp.strftime("%H:%M:%S")
        stale_part = f" [dim][STALE][/dim]" if snap.quote_stale else ""
        row1 = f"[bold]{snap.ticker}[/bold]{name_part}   [dim]{ts_str}[/dim]{stale_part}"

        # Row 2: price, change, volume
        if snap.quote is not None:
            q = snap.quote
            price_str = f"${fmt_price(q.price)}"
            arrow = fmt_arrow(q.change)
            chg = fmt_change(q.change)
            pct = fmt_pct(q.change_pct * 100 if q.change_pct is not None else None)
            color = pos if (q.change or 0) >= 0 else neg
            vol_str = fmt_volume(q.volume) if q.volume else "—"
            row2 = (
                f"  [bold]{price_str}[/bold]  "
                f"[{color}]{arrow} {chg}  {pct}[/]"
                f"   [{dim}]Vol {vol_str}[/]"
            )
        else:
            row2 = f"  [{dim}]— —  —[/]"

        # Row 3: day range + 52w range with percentile
        if snap.stats is not None and snap.quote is not None:
            st = snap.stats
            day_range = (
                f"{fmt_price(st.day_low)} – {fmt_price(st.day_high)}"
                if st.day_high is not None else "—"
            )
            w52_range = (
                f"{fmt_price(st.week_52_low)} – {fmt_price(st.week_52_high)}"
                if st.week_52_high is not None else "—"
            )
            pct_52 = (
                f"  ({st.week_52_percentile:.0f}% of range)"
                if st.week_52_percentile is not None else ""
            )
            row3 = (
                f"  [{dim}]Day  {day_range}     52W  {w52_range}{pct_52}[/]"
            )
        else:
            row3 = f"  [{dim}]—[/]"

        return "\n".join([row1, row2, row3])
