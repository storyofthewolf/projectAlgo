"""Sector heatmap panel — 3×4 grid of SectorCells with gradient backgrounds."""
from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Static

from cockpit.format import relative_strength_to_color, fmt_rs_pct, make_sparkline_percentile
from cockpit.themes import THEMES_CONFIG

# Display order: SPY first, then 11 SPDR sectors in SPY-weight order
_SECTOR_ORDER = [
    ("SPY",  "S&P 500"),
    ("XLK",  "Tech"),
    ("XLF",  "Financials"),
    ("XLV",  "Health"),
    ("XLY",  "Cons Disc"),
    ("XLC",  "Comm Svcs"),
    ("XLI",  "Industrial"),
    ("XLP",  "Cons Stap"),
    ("XLE",  "Energy"),
    ("XLU",  "Utilities"),
    ("XLRE", "RealEstate"),
    ("XLB",  "Materials"),
]

_SPARK_W = 6
_CELL_TEXT_COLOR = "#f0e0c0"  # cream: readable across all gradient backgrounds


class SectorCell(Widget):
    """Single sector cell with gradient background, label, RS value, and sparkline."""

    DEFAULT_CSS = f"""
    SectorCell {{
        width: 1fr;
        height: 1fr;
        border: round $border;
        border-title-color: $text-dim;
    }}
    SectorCell .sc-label {{
        height: 1;
        color: $text-dim;
    }}
    SectorCell .sc-data {{
        height: 1;
    }}
    SectorCell .sc-rs {{
        width: 1fr;
        color: {_CELL_TEXT_COLOR};
    }}
    SectorCell .sc-spark {{
        width: {_SPARK_W + 1};
        color: {_CELL_TEXT_COLOR};
        text-align: right;
    }}
    """

    def __init__(self, symbol: str, label: str, **kwargs):
        super().__init__(**kwargs)
        self.symbol = symbol
        self.label = label
        self._rs_value: Optional[float] = None
        self._sparkline_values: list = []
        self._is_error: bool = False

    def compose(self) -> ComposeResult:
        self.border_title = self.symbol
        yield Static(self.label, classes="sc-label")
        with Horizontal(classes="sc-data"):
            yield Static("", classes="sc-rs")
            yield Static("", classes="sc-spark")

    def update_cell(
        self,
        rs_value: Optional[float],
        sparkline_values: list,
        intensity_max_pct: float,
        is_error: bool,
        theme_colors: dict,
    ) -> None:
        """Update displayed values and apply gradient background."""
        self._rs_value = rs_value
        self._sparkline_values = sparkline_values
        self._is_error = is_error

        bg_hex = relative_strength_to_color(
            rs_value,
            intensity_max_pct,
            theme_colors["gradient_positive"],
            theme_colors["gradient_negative"],
            theme_colors["gradient_neutral"],
        )
        self.styles.background = bg_hex

        rs_widget = self.query_one(".sc-rs", Static)
        spark_widget = self.query_one(".sc-spark", Static)

        if is_error:
            rs_widget.update("—")
            spark_widget.update("")
        else:
            rs_widget.update(fmt_rs_pct(rs_value))
            if sparkline_values:
                spark_widget.update(make_sparkline_percentile(sparkline_values, _SPARK_W))
            else:
                spark_widget.update("")


class SectorPanel(Widget):
    """3×4 grid of sector cells."""

    DEFAULT_CSS = """
    SectorPanel {
        width: 1fr;
        height: 1fr;
    }
    SectorPanel .sp-grid {
        layout: vertical;
        height: 1fr;
    }
    SectorPanel .sp-row {
        layout: horizontal;
        height: 1fr;
    }
    SectorPanel .sp-error {
        color: $negative;
        align: center middle;
        height: 1fr;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cells: dict = {}

    def compose(self) -> ComposeResult:
        rows = [_SECTOR_ORDER[i:i + 3] for i in range(0, 12, 3)]
        with Vertical(classes="sp-grid"):
            for row_data in rows:
                with Horizontal(classes="sp-row"):
                    for symbol, label in row_data:
                        cell = SectorCell(symbol, label, id=f"sc-{symbol.lower()}")
                        self._cells[symbol] = cell
                        yield cell

    def _get_theme_colors(self) -> dict:
        theme_name = getattr(self.app, 'theme', 'claude-warm')
        cfg = THEMES_CONFIG.get(theme_name, THEMES_CONFIG["claude-warm"])
        return {
            "gradient_positive": cfg.get("gradient_positive", "#c87a1a"),
            "gradient_negative": cfg.get("gradient_negative", "#8b1a1a"),
            "gradient_neutral":  cfg.get("gradient_neutral",  "#1a1a1a"),
        }

    def update_snapshot(self, snapshot) -> None:
        """Update all cells from the snapshot."""
        if snapshot.error:
            # Panel-level error: set all cells to neutral/error state
            theme_colors = self._get_theme_colors()
            for cell in self._cells.values():
                cell.update_cell(
                    rs_value=None,
                    sparkline_values=[],
                    intensity_max_pct=snapshot.intensity_max_pct,
                    is_error=True,
                    theme_colors=theme_colors,
                )
            return

        cells_by_symbol = {c.symbol: c for c in snapshot.cells}
        theme_colors = self._get_theme_colors()

        for symbol, cell_widget in self._cells.items():
            if symbol in cells_by_symbol:
                cell_data = cells_by_symbol[symbol]
                cell_widget.update_cell(
                    rs_value=cell_data.relative_strength,
                    sparkline_values=cell_data.sparkline_values,
                    intensity_max_pct=snapshot.intensity_max_pct,
                    is_error=cell_data.error is not None,
                    theme_colors=theme_colors,
                )
