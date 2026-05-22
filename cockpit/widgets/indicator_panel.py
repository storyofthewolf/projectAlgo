"""IndicatorPanel widget — SMA + RSI readout for the ticker drill-down screen."""
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cockpit.themes import THEMES_CONFIG

_EM = "—"


class IndicatorPanel(Widget):
    """Right-column panel rendering SMA and RSI values with regime labels."""

    can_focus = False

    def compose(self) -> ComposeResult:
        yield Static("", id="ind-body", markup=True)

    def update_snapshot(self, snapshot) -> None:
        try:
            body = self.query_one("#ind-body", Static)
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

        if snap.error is not None:
            return f"[{dim}]  —[/]"

        if snap.indicators is None:
            return f"[{dim}]  loading…[/]"

        ind = snap.indicators
        lines = []

        # SMA rows
        cfg_td = self.app.settings.ticker_detail_config
        for w in cfg_td.sma_windows:
            sma_val = ind.sma_values.get(w)
            vs_pct = ind.sma_vs_price_pct.get(w)

            sma_str = f"{sma_val:.2f}" if sma_val is not None else _EM
            lines.append(f"  [bold]SMA({w})[/bold]   {sma_str:>8}")

            if vs_pct is not None:
                sign = "+" if vs_pct >= 0 else ""
                pct_str = f"{sign}{vs_pct:.2f}%"
                color = pos if vs_pct >= 0 else neg
                lines.append(f"  [{dim}]vs px:[/]   [{color}]{pct_str:>8}[/]")
            else:
                lines.append(f"  [{dim}]vs px:[/]   {_EM:>8}")

            lines.append("")

        # RSI row
        rsi_str = f"{ind.rsi:.1f}" if ind.rsi is not None else _EM
        lines.append(f"  [bold]RSI({cfg_td.rsi_window})[/bold]   {rsi_str:>8}")

        regime = ind.rsi_regime
        if regime == "oversold":
            regime_colored = f"[{pos}]{regime}[/]"
        elif regime == "overbought":
            regime_colored = f"[{neg}]{regime}[/]"
        elif regime == "neutral":
            regime_colored = f"[{dim}]{regime}[/]"
        else:
            regime_colored = f"[{dim}]{_EM}[/]"

        lines.append(f"  [{dim}]regime:[/]  {regime_colored}")

        return "\n".join(lines)
