"""Watchlist panel widget — scrollable, focusable, per-cell flash."""
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widget import Widget
from textual.widgets import Static

_ET = ZoneInfo("America/New_York")

from cockpit.format import (
    fmt_price, fmt_pct, fmt_change, fmt_volume,
    make_sparkline_percentile,
)
from cockpit.widgets.price_cell import PriceCell
from cockpit.widgets.pct_cell import PctCell

# Column widths (characters) — must sum to fit in panel
_W_TICKER = 6
_W_PRICE  = 10
_W_CHG    = 9
_W_PCT    = 9
_W_SPARK  = 12
_W_VOL    = 8


def _col_header() -> str:
    return (
        f" {'TICKER':<{_W_TICKER}}"
        f" {'PRICE':>{_W_PRICE}}"
        f" {'CHG':>{_W_CHG}}"
        f" {'CHG%':>{_W_PCT}}"
        f" {'SPARK':<{_W_SPARK}}"
        f" {'VOL':>{_W_VOL}}"
    )


class WatchlistRow(Horizontal):
    """One data row in the watchlist panel."""

    DEFAULT_CSS = """
    WatchlistRow {
        height: 1;
        width: 1fr;
    }
    .wl-ticker  { width: 7;  color: $text-primary; }
    .wl-price   { width: 11; text-align: right; }
    .wl-chg     { width: 10; color: $text-primary; text-align: right; }
    .wl-pct     { width: 10; text-align: right; }
    .wl-spark   { width: 13; color: $text-primary; }
    .wl-vol     { width: 9;  color: $text-dim; text-align: right; }
    """

    def __init__(self, ticker: str, **kwargs):
        super().__init__(**kwargs)
        self.ticker_symbol = ticker

    def compose(self) -> ComposeResult:
        yield Static(f" {self.ticker_symbol:<{_W_TICKER}}", classes="wl-ticker")
        yield PriceCell(classes="wl-price")
        yield Static("", classes="wl-chg")
        yield PctCell(classes="wl-pct")
        yield Static("", classes="wl-spark")
        yield Static("", classes="wl-vol")

    def update_data(
        self,
        price: float,
        change: Optional[float],
        change_pct: Optional[float],
        sparkline_closes: tuple[float, ...],
        volume: Optional[int],
    ) -> None:
        self.query_one(PriceCell).update_price(price)
        chg_str = f" {fmt_change(change):>{_W_CHG}}"
        self.query_one(".wl-chg", Static).update(chg_str)
        pct_cell = self.query_one(PctCell)
        if change_pct is not None:
            pct_cell.update_pct(change_pct * 100)
        else:
            pct_cell.update(f" {'—':>{_W_PCT}}")
        spark_str = f" {make_sparkline_percentile(list(sparkline_closes), _W_SPARK):<{_W_SPARK}}"
        self.query_one(".wl-spark", Static).update(spark_str)
        vol_str = f" {fmt_volume(volume):>{_W_VOL}}"
        self.query_one(".wl-vol", Static).update(vol_str)

    def mark_error(self, message: str) -> None:
        """Render this row as a dimmed error row."""
        em = "—"
        self.add_class("wl-error-row")
        self.query_one(PriceCell).update(f" {em:>{_W_PRICE}}")
        self.query_one(".wl-chg", Static).update(f" {em:>{_W_CHG}}")
        self.query_one(PctCell).update(f" {em:>{_W_PCT}}")
        # Truncate error message to fit
        max_msg = _W_SPARK + _W_VOL
        short = message[:max_msg - 1] if len(message) > max_msg - 1 else message
        self.query_one(".wl-spark", Static).update(f" [ERR] {short}")
        self.query_one(".wl-vol", Static).update("")


class WatchlistErrorRow(Horizontal):
    """A row showing a failed ticker with error info."""

    DEFAULT_CSS = """
    WatchlistErrorRow {
        height: 1;
        width: 1fr;
        color: $text-dim;
    }
    """

    def __init__(self, ticker: str, message: str, **kwargs):
        super().__init__(**kwargs)
        self.ticker_symbol = ticker
        self._message = message

    def compose(self) -> ComposeResult:
        em = "—"
        max_msg = _W_SPARK + _W_VOL + 2
        short = self._message[:max_msg - 1] if len(self._message) > max_msg - 1 else self._message
        text = (
            f" ⚠ {self.ticker_symbol:<{_W_TICKER - 2}}"
            f" {em:>{_W_PRICE}}"
            f" {em:>{_W_CHG}}"
            f" {em:>{_W_PCT}}"
            f"  [ERR] {short}"
        )
        yield Static(text)


class _WatchlistScroll(VerticalScroll):
    """VerticalScroll that cedes Tab focus to WatchlistPanel."""
    can_focus = False


class WatchlistPanel(Widget):
    """Watchlist panel with column header and focusable scrollable rows.

    Exposes update_from_snapshot() to wire into the polling loop.
    """

    can_focus = True

    BINDINGS = [
        Binding("j", "scroll_down_row", show=False),
        Binding("down", "scroll_down_row", show=False),
        Binding("k", "scroll_up_row", show=False),
        Binding("up", "scroll_up_row", show=False),
        Binding("g", "scroll_top", show=False),
        Binding("shift+g", "scroll_bottom", show=False),
    ]

    DEFAULT_CSS = """
    WatchlistPanel {
        height: 1fr;
        width: 1fr;
    }
    WatchlistPanel #wl-col-header {
        color: $text-dim;
        height: 1;
    }
    WatchlistPanel #wl-sep {
        color: $text-dim;
        height: 1;
    }
    WatchlistPanel #wl-status {
        color: $text-dim;
        height: 1;
    }
    WatchlistPanel #wl-scroll {
        height: 1fr;
    }
    WatchlistPanel .wl-error-row {
        color: $text-dim;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._rows: dict[str, WatchlistRow | WatchlistErrorRow] = {}
        self._current_tickers: list[str] = []
        self._status_prefix: str = "  WATCHLIST: loading…"

    def on_mount(self) -> None:
        self.set_interval(1, self._tick_clock)

    def _tick_clock(self) -> None:
        now_et = datetime.now(_ET)
        time_str = now_et.strftime("%H:%M:%S ET")
        self.query_one("#wl-status", Static).update(
            f"{self._status_prefix}  ·  {time_str}"
        )

    def compose(self) -> ComposeResult:
        yield Static(_col_header(), id="wl-col-header")
        yield Static(" " + "─" * 68, id="wl-sep")
        yield Static("  Loading…", id="wl-status")
        yield _WatchlistScroll(id="wl-scroll")

    def update_from_snapshot(self, snapshot) -> None:
        """Update panel from a WatchlistSnapshot. Called on the event loop."""
        from workflows.watchlist_snapshot import WatchlistSnapshot

        # Update status prefix; clock timer writes the full line with time
        sources = snapshot.quote_sources
        src_label = next(iter(sources)) if len(sources) == 1 else "mixed"
        self._status_prefix = (
            f"  WATCHLIST: {snapshot.provider_name}/{snapshot.watchlist_name}"
            f"  ·  quotes: {src_label}"
        )
        self._tick_clock()

        scroll = self.query_one(_WatchlistScroll)
        new_tickers = [r.ticker for r in snapshot.rows] + [e.ticker for e in snapshot.errors]

        # Remove rows that are no longer in the snapshot
        gone = [t for t in self._current_tickers if t not in new_tickers]
        for ticker in gone:
            if ticker in self._rows:
                self._rows[ticker].remove()
                del self._rows[ticker]

        # Update or add successful rows
        for row_data in snapshot.rows:
            ticker = row_data.ticker
            if ticker in self._rows and isinstance(self._rows[ticker], WatchlistRow):
                # Update in-place — preserves PriceCell._previous for flash
                self._rows[ticker].update_data(
                    price=row_data.quote.price,
                    change=row_data.quote.change,
                    change_pct=row_data.quote.change_pct,
                    sparkline_closes=row_data.sparkline_closes,
                    volume=row_data.last_volume,
                )
            else:
                # New ticker or previously errored — mount a fresh row
                if ticker in self._rows:
                    self._rows[ticker].remove()
                new_row = WatchlistRow(ticker)
                scroll.mount(new_row)
                self._rows[ticker] = new_row
                new_row.update_data(
                    price=row_data.quote.price,
                    change=row_data.quote.change,
                    change_pct=row_data.quote.change_pct,
                    sparkline_closes=row_data.sparkline_closes,
                    volume=row_data.last_volume,
                )

        # Update or add error rows
        for err in snapshot.errors:
            ticker = err.ticker
            if ticker in self._rows and isinstance(self._rows[ticker], WatchlistErrorRow):
                # Error row doesn't change; skip rebuild unless message changed
                pass
            else:
                if ticker in self._rows:
                    self._rows[ticker].remove()
                err_row = WatchlistErrorRow(ticker, err.error_message)
                scroll.mount(err_row)
                self._rows[ticker] = err_row

        self._current_tickers = new_tickers

    def action_scroll_down_row(self) -> None:
        self.query_one(_WatchlistScroll).scroll_down()

    def action_scroll_up_row(self) -> None:
        self.query_one(_WatchlistScroll).scroll_up()

    def action_scroll_top(self) -> None:
        self.query_one(_WatchlistScroll).scroll_home()

    def action_scroll_bottom(self) -> None:
        self.query_one(_WatchlistScroll).scroll_end()
