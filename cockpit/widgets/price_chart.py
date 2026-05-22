"""PriceChart widget — in-terminal close-price + SMA chart for the drill-down.

Plotext-backed line chart. Coarse by design (braille resolution); the Dash
view launched via the drill-down's P key is the precise interactive chart.
"""
from textual_plotext import PlotextPlot

from analysis.technical_analysis import calculate_sma
from cockpit.themes import THEMES_CONFIG

# SMA windows drawn as overlays, paired with a plotext color name.
_SMA_PLOT = [
    (20, "cyan"),
    (50, "orange"),
    (200, "magenta"),
]


class PriceChart(PlotextPlot):
    """Close-price line + SMA overlays from a TickerDetailSnapshot."""

    can_focus = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._snapshot = None

    def _theme(self) -> dict:
        name = getattr(self.app, "theme", "claude-warm")
        return THEMES_CONFIG.get(name, THEMES_CONFIG["claude-warm"])

    def update_snapshot(self, snapshot) -> None:
        """Receive a TickerDetailSnapshot and redraw."""
        self._snapshot = snapshot
        self._replot()

    def on_mount(self) -> None:
        self._replot()

    def _replot(self) -> None:
        plt = self.plt
        plt.clear_data()
        plt.clear_figure()

        snap = self._snapshot
        if snap is None or snap.history is None or snap.error is not None:
            plt.title("no chart data")
            self.refresh()
            return

        history = snap.history
        closes = [float(v) for v in history["Close"].tolist()]
        if not closes:
            plt.title("no chart data")
            self.refresh()
            return

        x = list(range(len(closes)))

        plt.theme("dark")
        plt.plot(x, closes, color="white", label="Close")

        for window, color in _SMA_PLOT:
            if len(closes) >= window:
                sma = calculate_sma(history["Close"], window=window)
                sma_vals = [None if v != v else float(v) for v in sma.tolist()]
                plt.plot(x, sma_vals, color=color, label=f"SMA{window}")

        # Date labels at a handful of evenly spaced ticks.
        idx = history.index
        n = len(idx)
        if n > 1:
            tick_count = min(6, n)
            positions = [round(i * (n - 1) / (tick_count - 1)) for i in range(tick_count)]
            labels = [idx[p].strftime("%m/%d") for p in positions]
            plt.xticks(positions, labels)

        plt.title(f"{snap.ticker} — {n}d close + SMA")
        self.refresh()
