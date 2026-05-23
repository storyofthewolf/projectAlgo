"""Ticker metrics panel widget.

Renders scalar metrics for a single ticker in a two-column label/value layout
inside a PanelFrame. Consumed by TickerDetailScreen.
"""
from typing import Optional

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cockpit.format import fmt_change, fmt_price, fmt_pct, fmt_volume
from cockpit.widgets.panel_frame import PanelFrame

_EM = "—"


def _colored(text: str, css_var: str) -> str:
    return f"[{css_var}]{text}[/{css_var}]"


def _signed_color(value: Optional[float], text: str) -> str:
    if value is None:
        return text
    if value > 0:
        return _colored(text, "$positive")
    if value < 0:
        return _colored(text, "$negative")
    return text


class TickerMetricsPanel(Widget):
    """Two-column scalar metrics panel for the ticker drill-down screen."""

    DEFAULT_CSS = """
    TickerMetricsPanel {
        height: 1fr;
        width: 1fr;
    }
    TickerMetricsPanel Static {
        height: 1fr;
        color: $text-primary;
        padding: 0 1;
    }
    """

    def __init__(self, ticker: str = "", **kwargs) -> None:
        super().__init__(**kwargs)
        self._ticker = ticker

    def compose(self) -> ComposeResult:
        with PanelFrame(title=f"{self._ticker} — METRICS", id="metrics-frame"):
            yield Static(id="metrics-body")

    def update_metrics(self, metrics) -> None:
        """Re-render the panel from a TickerMetrics snapshot."""
        from workflows.ticker_metrics_snapshot import TickerMetrics
        self._ticker = metrics.ticker
        try:
            frame = self.query_one("#metrics-frame", PanelFrame)
            frame.border_title = f"{metrics.ticker} — METRICS"
        except Exception:
            pass

        body = self.query_one("#metrics-body", Static)
        body.update(self._build_markup(metrics))

    def _build_markup(self, metrics) -> str:
        if metrics.error:
            return f"[red]{metrics.error}[/red]"

        q = metrics.quote
        price_str = f"${fmt_price(q.price)}" if q else _EM
        change_str = _EM
        if q and q.change is not None and q.change_pct is not None:
            ch = fmt_change(q.change)
            cp = fmt_pct(q.change_pct)
            change_str = _signed_color(q.change, f"{ch}  {cp}")
        volume_str = fmt_volume(q.volume) if q else _EM

        high_str = f"${fmt_price(metrics.high_52w)}" if metrics.high_52w is not None else _EM
        low_str = f"${fmt_price(metrics.low_52w)}" if metrics.low_52w is not None else _EM
        range_str = (
            f"{metrics.range_position_pct:.0f}%"
            if metrics.range_position_pct is not None
            else _EM
        )

        def sma_str(sma_val, pct_val) -> str:
            if sma_val is None:
                return _EM
            base = f"${fmt_price(sma_val)}"
            if pct_val is not None:
                pct = fmt_pct(pct_val)
                pct_colored = _signed_color(pct_val, f"({pct})")
                return f"{base}  {pct_colored}"
            return base

        sma20_str = sma_str(metrics.sma_20, metrics.pct_vs_sma_20)
        sma50_str = sma_str(metrics.sma_50, metrics.pct_vs_sma_50)
        sma200_str = sma_str(metrics.sma_200, metrics.pct_vs_sma_200)

        rsi_str = _EM
        if metrics.rsi_14 is not None:
            rval = f"{metrics.rsi_14:.1f}"
            regime = metrics.rsi_regime or ""
            if regime == "overbought":
                regime_colored = _colored(regime.upper(), "$negative")
            elif regime == "oversold":
                regime_colored = _colored(regime.upper(), "$positive")
            else:
                regime_colored = _colored(regime.upper(), "$text-dim")
            rsi_str = f"{rval}  {regime_colored}"

        rs_str = _EM
        if metrics.rs_spy_1m is not None:
            rs_str = _signed_color(metrics.rs_spy_1m, fmt_pct(metrics.rs_spy_1m))

        rows = [
            ("PRICE",         price_str),
            ("CHANGE",        change_str),
            ("VOLUME",        volume_str),
            ("52W HIGH",      high_str),
            ("52W LOW",       low_str),
            ("52W RANGE",     range_str),
            ("SMA 20",        sma20_str),
            ("SMA 50",        sma50_str),
            ("SMA 200",       sma200_str),
            ("RSI(14)",       rsi_str),
            ("RS vs SPY 1M",  rs_str),
        ]

        label_width = 14
        lines = []
        for label, value in rows:
            padded = label.ljust(label_width)
            lines.append(f"[bold $text-dim]{padded}[/bold $text-dim]  {value}")

        ts = metrics.as_of.strftime("%H:%M:%S")
        lines.append("")
        lines.append(f"[dim]as of {ts}[/dim]")
        return "\n".join(lines)
