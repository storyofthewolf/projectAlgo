from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Horizontal, Vertical

from cockpit import mock_data as md
from cockpit.format import (
    fmt_price, fmt_pct, fmt_change, fmt_volume, fmt_arrow,
    fmt_yield, fmt_ticker, make_sparkline, make_sector_bar, fmt_corr,
)
from cockpit.themes import THEMES_CONFIG
from cockpit.widgets.panel_frame import PanelFrame
from cockpit.widgets.clock_header import ClockHeader
from cockpit.widgets.command_footer import CommandFooter

_COMMANDS = [("Q", "QUIT"), ("R", "REFRESH"), ("?", "HELP"), ("T", "THEME"), ("TAB", "NAV")]


def _render_market_pulse(pulse: list[tuple]) -> str:
    lines = []
    for ticker, last, chg_pct, spark, fmt in pulse:
        t = fmt_ticker(ticker)
        if fmt == "yield":
            price_str = fmt_yield(last)
        else:
            price_str = fmt_price(last)
        pct_str = fmt_pct(chg_pct)
        arrow = fmt_arrow(chg_pct)
        spark_str = make_sparkline(spark, 10)
        lines.append(f" {t:<6} {price_str:>8}  {pct_str:>8} {arrow}   {spark_str}")
    return "\n".join(lines)


def _render_watchlist(holdings: list[tuple]) -> str:
    header = (
        f" {'TICKER':<7} {'LAST':>8}  {'CHG':>7}  {'CHG%':>8}  "
        f"{'VOL':>7}  {'5D':>6}  {'30D':>7}  {'SPARK':<12}  {'RSI':>4}"
    )
    sep = " " + "─" * (len(header) - 1)
    rows = [header, sep]
    for ticker, last, chg, chg_pct, vol, c5d, c30d, spark, rsi in holdings:
        t = fmt_ticker(ticker)
        spark_str = make_sparkline(spark, 8)
        rows.append(
            f" {t:<7} {fmt_price(last):>8}  {fmt_change(chg):>7}  {fmt_pct(chg_pct):>8}  "
            f"{fmt_volume(vol):>7}  {fmt_pct(c5d):>6}  {fmt_pct(c30d):>7}  "
            f"{spark_str:<12}  {rsi:>4}"
        )
    return "\n".join(rows)


def _render_sectors(sectors: list[tuple], pos_color: str = "#87a96b", neg_color: str = "#c75450") -> str:
    lines = []
    for etf, name, chg_pct in sectors:
        bar = make_sector_bar(chg_pct)
        pct_str = fmt_pct(chg_pct)
        color = pos_color if chg_pct >= 0 else neg_color
        lines.append(f" {etf:<5} {name:<10} [{color}]{pct_str:>8} {bar}[/{color}]")
    return "\n".join(lines)


def _corr_color(v: float, cfg: dict) -> str:
    if abs(v - 1.0) < 1e-9:
        return cfg["text_dim"]
    if v >= 0.7:
        return cfg["primary"]
    if v >= 0.3:
        return cfg["secondary"]
    if v > -0.3:
        return cfg["text_dim"]
    return cfg["negative"]


def _render_correlations(
    tickers: list[str],
    corr_rows: list[tuple],
    theme_cfg: dict | None = None,
) -> str:
    header = "         " + "".join(f"{t:>7}" for t in tickers)
    rows = [header]
    for row_ticker, values in corr_rows:
        cells = []
        for v in values:
            cell_str = f"{fmt_corr(v):>7}"
            if theme_cfg:
                color = _corr_color(v, theme_cfg)
                cells.append(f"[{color}]{cell_str}[/{color}]")
            else:
                cells.append(cell_str)
        rows.append(f" {row_ticker:<7} " + "".join(cells))
    return "\n".join(rows)


class HomeScreen(Screen):
    """Main home screen with all five panels."""

    def _theme_cfg(self) -> dict:
        theme = self.app.theme if self.app.theme in THEMES_CONFIG else "claude-warm"
        return THEMES_CONFIG[theme]

    def compose(self) -> ComposeResult:
        data = md.regenerate_mock()
        self._current_data = data
        cfg = self._theme_cfg()
        pos, neg = cfg["positive"], cfg["negative"]

        yield ClockHeader(id="clock-header")

        with Horizontal(id="top-row"):
            with PanelFrame("ACCOUNT", id="panel-account"):
                yield Static(
                    "\n Schwab not connected.\n\n"
                    " Run:\n"
                    "  python -m\n"
                    "  scripts.schwab_auth\n\n"
                    " See CLAUDE.md\n"
                    " for setup.",
                    id="account-content",
                )
            with PanelFrame("MARKET PULSE", id="panel-pulse"):
                yield Static(
                    _render_market_pulse(data["pulse"]),
                    id="pulse-content",
                )

        with PanelFrame("WATCHLIST: HOLDINGS", id="panel-watchlist"):
            yield Static(
                _render_watchlist(data["holdings"]),
                id="watchlist-content",
            )

        with Horizontal(id="bottom-row"):
            with PanelFrame("SECTOR HEATMAP", id="panel-sectors"):
                yield Static(
                    _render_sectors(data["sectors"], pos, neg),
                    id="sectors-content",
                )
            with PanelFrame("CORRELATIONS (30D, HOLDINGS)", id="panel-corr"):
                yield Static(
                    _render_correlations(md.WATCHLIST_TICKERS, data["corr"], cfg),
                    id="corr-content",
                )

        yield CommandFooter(_COMMANDS, id="command-footer")
        yield Static(
            " Please resize your terminal to at least 120×30 ",
            id="resize-warning",
        )

    def refresh_mock(self) -> None:
        """Regenerate mock data and update all panel contents."""
        data = md.regenerate_mock()
        self._current_data = data
        cfg = self._theme_cfg()
        pos, neg = cfg["positive"], cfg["negative"]

        self.query_one("#pulse-content", Static).update(
            _render_market_pulse(data["pulse"])
        )
        self.query_one("#watchlist-content", Static).update(
            _render_watchlist(data["holdings"])
        )
        self.query_one("#sectors-content", Static).update(
            _render_sectors(data["sectors"], pos, neg)
        )
        self.query_one("#corr-content", Static).update(
            _render_correlations(md.WATCHLIST_TICKERS, data["corr"], cfg)
        )
