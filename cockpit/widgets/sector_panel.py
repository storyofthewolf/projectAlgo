"""Sector strip panel — single horizontal row of 12 gradient cells."""
from typing import Optional

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from cockpit.format import relative_strength_to_color
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

_CELL_TEXT_COLOR = "#f5e9d6"  # light: readable across all gradient backgrounds


class SectorCell(Static):
    """One cell in the sector strip: gradient background, ticker + RS%."""

    DEFAULT_CSS = f"""
    SectorCell {{
        width: 1fr;
        height: 1;
        content-align: center middle;
        text-style: bold;
        color: {_CELL_TEXT_COLOR};
    }}
    """

    def __init__(self, symbol: str, label: str, **kwargs):
        super().__init__("", **kwargs)
        self.symbol = symbol
        self.label = label
        self._rs_value: Optional[float] = None
        self._is_error: bool = False

    def update_cell(
        self,
        rs_value: Optional[float],
        intensity_max_pct: float,
        is_error: bool,
        theme_colors: dict,
    ) -> None:
        """Update displayed value and apply gradient background."""
        self._rs_value = rs_value
        self._is_error = is_error

        bg_hex = relative_strength_to_color(
            rs_value,
            intensity_max_pct,
            theme_colors["gradient_positive"],
            theme_colors["gradient_negative"],
            theme_colors["gradient_neutral"],
        )
        self.styles.background = bg_hex

        if is_error:
            self.update(f"{self.symbol} —")
        elif rs_value is None:
            self.update(f"{self.symbol} —")
        else:
            pct = rs_value * 100
            sign = "+" if pct >= 0 else ""
            self.update(f"{self.symbol} {sign}{pct:.1f}")


class SectorPanel(Widget):
    """3×4 grid of sector cells."""

    DEFAULT_CSS = """
    SectorPanel {
        layout: horizontal;
        width: 1fr;
        height: 1;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cells: dict = {}

    def compose(self) -> ComposeResult:
        for symbol, label in _SECTOR_ORDER:
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
                    intensity_max_pct=snapshot.intensity_max_pct,
                    is_error=cell_data.error is not None,
                    theme_colors=theme_colors,
                )
