"""Market pulse panel — 4×2 grid of PulseCells with real-data wiring."""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static

from cockpit.format import (
    fmt_price_display,
    fmt_index,
    fmt_yield,
    fmt_change,
    fmt_yield_change,
    fmt_pct,
)
from cockpit.widgets.price_cell import PriceCell
from cockpit.widgets.pct_cell import PctCell

_ET = ZoneInfo("America/New_York")

# Format-type → price display function
_PRICE_FMTS = {
    "price": fmt_price_display,   # $548.23
    "index": fmt_index,           # 16.42
    "yield": fmt_yield,           # 4.482%
}


class PulseCell(Widget):
    """One ticker cell in the 4×2 pulse grid.

    Layout (2 inner rows inside a bordered widget with label as title):
      Row 1:  PriceCell (price)       |  Static (absolute change, colored)
      Row 2:  PctCell (change %)

    For yield format: row 2 is blank (no % value).
    """

    DEFAULT_CSS = """
    PulseCell {
        border: round $border;
        width: 1fr;
        height: 1fr;
    }
    PulseCell .pc-row {
        height: 1;
        width: 1fr;
    }
    PulseCell .pc-price {
        width: 1fr;
        text-align: right;
    }
    PulseCell .pc-change {
        width: 9;
        text-align: right;
        color: $text-dim;
    }
    PulseCell .pc-change.pc-up {
        color: $positive;
    }
    PulseCell .pc-change.pc-down {
        color: $negative;
    }
    PulseCell .pc-pct {
        width: 1fr;
    }
    PulseCell.pc-error {
        color: $text-dim;
    }
    """

    def __init__(self, symbol: str, label: str, format_type: str, **kwargs):
        self._symbol = symbol
        self._label = label
        self._format_type = format_type
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        self.border_title = self._label
        fmt_fn = _PRICE_FMTS.get(self._format_type, fmt_price_display)
        with Horizontal(classes="pc-row"):
            yield PriceCell(format_func=fmt_fn, classes="pc-price")
            yield Static("", classes="pc-change")
        with Horizontal(classes="pc-row"):
            yield PctCell(classes="pc-pct")

    def update_from_ticker(self, ticker) -> None:
        """Update cell from a PulseTicker data object. Called on event loop."""
        if ticker.error:
            self._show_error()
            return

        self.remove_class("pc-error")

        # --- Price ---
        price_cell = self.query_one(PriceCell)
        if ticker.price is not None:
            price_cell.update_price(ticker.price)

        # --- Absolute change (colored Static) ---
        chg_widget = self.query_one(".pc-change", Static)
        change = ticker.change
        if self._format_type == "yield":
            chg_str = fmt_yield_change(change)
        else:
            chg_str = fmt_change(change)

        chg_widget.update(chg_str)
        chg_widget.remove_class("pc-up", "pc-down")
        if change is not None:
            if change > 1e-9:
                chg_widget.add_class("pc-up")
            elif change < -1e-9:
                chg_widget.add_class("pc-down")

        # --- Change percent (PctCell, skipped for yield) ---
        pct_cell = self.query_one(PctCell)
        if self._format_type != "yield" and ticker.change_pct is not None:
            pct_cell.update_pct(ticker.change_pct * 100)
        else:
            pct_cell.update("")

    def _show_error(self) -> None:
        self.add_class("pc-error")
        em = "—"
        self.query_one(PriceCell).update(em)
        self.query_one(".pc-change", Static).update(em)
        self.query_one(PctCell).update("")


class MarketPulsePanel(Widget):
    """4×2 grid of PulseCells with a 1-second clock status line.

    Accepts pulse_configs (list of settings PulseTicker) at construction;
    exposes update_snapshot(PulseSnapshot) for HomeScreen to call.
    """

    DEFAULT_CSS = """
    MarketPulsePanel {
        height: 1fr;
        width: 1fr;
    }
    MarketPulsePanel #mp-status {
        height: 1;
        color: $text-dim;
    }
    MarketPulsePanel .mp-row {
        height: 1fr;
        width: 1fr;
    }
    """

    def __init__(self, pulse_configs, **kwargs):
        super().__init__(**kwargs)
        configs = list(pulse_configs)
        self._top_configs = configs[:4]
        self._bot_configs = configs[4:8]
        self._status_prefix = "  PULSE  ·  loading…"

    def compose(self) -> ComposeResult:
        yield Static(self._status_prefix, id="mp-status")
        with Horizontal(classes="mp-row"):
            for cfg in self._top_configs:
                yield PulseCell(cfg.symbol, cfg.label, cfg.format)
        with Horizontal(classes="mp-row"):
            for cfg in self._bot_configs:
                yield PulseCell(cfg.symbol, cfg.label, cfg.format)

    def on_mount(self) -> None:
        self.set_interval(1, self._tick_clock)

    def _tick_clock(self) -> None:
        now_et = datetime.now(_ET)
        time_str = now_et.strftime("%H:%M:%S ET")
        self.query_one("#mp-status", Static).update(
            f"{self._status_prefix}  ·  {time_str}"
        )

    def update_snapshot(self, snapshot) -> None:
        """Update all cells from a PulseSnapshot. Called on the event loop."""
        self._status_prefix = f"  PULSE  ·  quotes: {snapshot.quote_source}"
        self._tick_clock()

        cells = list(self.query(PulseCell))
        for i, ticker_data in enumerate(snapshot.tickers):
            if i < len(cells):
                cells[i].update_from_ticker(ticker_data)
