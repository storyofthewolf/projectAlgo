"""Sector deep-dive table — sortable multi-timeframe RS table."""
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from cockpit.format import (
    relative_strength_to_color,
    fmt_rs_pct,
    make_sparkline_percentile,
)
from cockpit.themes import THEMES_CONFIG

# Cream text — readable on all gradient backgrounds (dark amber, dark red, near-black)
_CELL_FG = "#f0e0c0"

# Sort-direction arrow convention (matches Bloomberg / TradingView):
#   ▼ = descending  (biggest value at top)
#   ▲ = ascending   (smallest value at top)
_ARROW_DESC = "▼"
_ARROW_ASC  = "▲"

_COL_SYMBOL = 7    # "XLK    " (6 + 1 space)
_COL_NAME   = 15   # "Technology     " (14 + 1 space)
_COL_TF     = 9    # "  +7.78% " (8 right-aligned + 1 space)
_COL_SPARK  = 12   # sparkline chars


class SectorTable(Widget):
    """Sortable multi-timeframe sector RS table. Passive renderer — screen handles keys."""

    can_focus = False

    snapshot: reactive = reactive(None)
    sort_column: reactive[str] = reactive("")
    sort_direction: reactive[str] = reactive("desc")
    focused_column: reactive[str] = reactive("")

    def __init__(self, initial_sort_column: str, initial_sort_direction: str, **kwargs):
        super().__init__(**kwargs)
        self._initial_sort_column = initial_sort_column
        self._initial_sort_direction = initial_sort_direction

    def compose(self) -> ComposeResult:
        yield Static("", id="table-body", markup=True)

    def on_mount(self) -> None:
        self.sort_column = self._initial_sort_column
        self.sort_direction = self._initial_sort_direction
        self.focused_column = self._initial_sort_column

    # ── Watchers — any change triggers full redraw ────────────────────────

    def watch_snapshot(self, _) -> None:
        self._redraw()

    def watch_sort_column(self, _) -> None:
        self._redraw()

    def watch_sort_direction(self, _) -> None:
        self._redraw()

    def watch_focused_column(self, _) -> None:
        self._redraw()

    # ── Public API (called by SectorDeepDiveScreen) ───────────────────────

    def focus_prev_column(self) -> None:
        if self.snapshot is None:
            return
        labels = list(self.snapshot.timeframe_labels)
        if not labels:
            return
        cur = self.focused_column if self.focused_column in labels else labels[0]
        self.focused_column = labels[(labels.index(cur) - 1) % len(labels)]

    def focus_next_column(self) -> None:
        if self.snapshot is None:
            return
        labels = list(self.snapshot.timeframe_labels)
        if not labels:
            return
        cur = self.focused_column if self.focused_column in labels else labels[0]
        self.focused_column = labels[(labels.index(cur) + 1) % len(labels)]

    def apply_sort(self) -> None:
        if not self.focused_column:
            return
        if self.focused_column == self.sort_column:
            self.sort_direction = "asc" if self.sort_direction == "desc" else "desc"
        else:
            self.sort_column = self.focused_column
            self.sort_direction = "desc"

    # ── Rendering ─────────────────────────────────────────────────────────

    def _redraw(self) -> None:
        try:
            body = self.query_one("#table-body", Static)
        except Exception:
            return
        if self.snapshot is None:
            body.update("[dim]Loading…[/dim]")
            return
        body.update(self._build_table())

    def _theme_colors(self) -> dict:
        theme_name = getattr(self.app, 'theme', 'claude-warm')
        cfg = THEMES_CONFIG.get(theme_name, THEMES_CONFIG['claude-warm'])
        return cfg

    def _build_table(self) -> str:
        snap = self.snapshot
        if snap.error:
            return f"[red]Error: {snap.error}[/red]"

        cfg = self._theme_colors()
        grad_pos  = cfg['gradient_positive']
        grad_neg  = cfg['gradient_negative']
        grad_neu  = cfg['gradient_neutral']
        text_dim  = cfg['text_dim']
        border_c  = cfg['border']
        intensity = self.app.settings.sector_config.intensity_max_pct

        labels = list(snap.timeframe_labels)
        sort_col = self.sort_column
        sort_dir = self.sort_direction
        focus_col = self.focused_column

        # Sync focused_column if snapshot labels changed
        if focus_col not in labels and labels:
            focus_col = labels[0]

        # ── Header ────────────────────────────────────────────────────────
        header = f"[{text_dim}]{'SYMBOL':<7}{'NAME':<15}[/]"
        for lbl in labels:
            arrow = (_ARROW_DESC if sort_dir == "desc" else _ARROW_ASC) if lbl == sort_col else ""
            col_text = f"{lbl}{arrow}"
            padded = f"{col_text:>8}"
            if lbl == focus_col:
                header += f"[bold][underline]{padded}[/underline][/bold] "
            elif lbl == sort_col:
                header += f"[bold]{padded}[/bold] "
            else:
                header += f"[{text_dim}]{padded}[/] "
        header += f"[{text_dim}]{'SPARK':>12}[/]"

        # ── Separator ─────────────────────────────────────────────────────
        total_width = _COL_SYMBOL + _COL_NAME + len(labels) * _COL_TF + _COL_SPARK
        sep = f"[{border_c}]{'─' * total_width}[/]"

        # ── Sort rows (SPY pinned, sectors sorted below) ───────────────────
        spy_rows = [r for r in snap.rows if r.is_benchmark]
        sec_rows = [r for r in snap.rows if not r.is_benchmark]

        def sort_key(row):
            tf_map = {tf.label: tf.rs_value for tf in row.timeframes}
            val = tf_map.get(sort_col)
            if val is None:
                return (1, row.symbol)
            return (0, -val if sort_dir == "desc" else val)

        sorted_sectors = sorted(sec_rows, key=sort_key)

        # ── Build lines ───────────────────────────────────────────────────
        lines = [header, sep]
        for row in spy_rows:
            lines.append(self._render_row(
                row, labels, intensity, sort_col,
                grad_pos, grad_neg, grad_neu, text_dim,
            ))
        lines.append(sep)
        for row in sorted_sectors:
            lines.append(self._render_row(
                row, labels, intensity, sort_col,
                grad_pos, grad_neg, grad_neu, text_dim,
            ))

        return "\n".join(lines)

    def _render_row(
        self, row, labels, intensity_max_pct, sort_col,
        grad_pos, grad_neg, grad_neu, text_dim,
    ) -> str:
        sym = row.symbol[:6]
        name = (row.name[:13] + "…") if len(row.name) > 14 else row.name

        line = f"[bold]{sym:<6}[/bold] {name:<14} "

        tf_map = {tf.label: tf for tf in row.timeframes}

        if row.error:
            for _ in labels:
                line += f"[{text_dim}]{'—':>8}[/] "
            line += f"[{text_dim}]{'—' * _COL_SPARK}[/]"
            return line

        for lbl in labels:
            tf = tf_map.get(lbl)
            rs_value = tf.rs_value if tf else None

            if row.is_benchmark:
                rs_str = f"{'+0.00%':>8}"
                cell = f"[{text_dim} on {grad_neu}]{rs_str}[/]"
            elif rs_value is None:
                rs_str = f"{'—':>8}"
                cell = f"[{text_dim} on {grad_neu}]{rs_str}[/]"
            else:
                raw = fmt_rs_pct(rs_value)
                rs_str = f"{raw:>8}"
                bg = relative_strength_to_color(
                    rs_value, intensity_max_pct, grad_pos, grad_neg, grad_neu
                )
                cell = f"[{_CELL_FG} on {bg}]{rs_str}[/]"
            line += cell + " "

        # Sparkline uses the currently-sorted timeframe's rs_path
        sort_tf = tf_map.get(sort_col)
        if row.is_benchmark:
            spark_values = [0.0] * 20
        elif sort_tf and sort_tf.rs_path:
            spark_values = list(sort_tf.rs_path)
        else:
            spark_values = []

        if spark_values:
            sparkline = make_sparkline_percentile(spark_values, _COL_SPARK)
        else:
            sparkline = " " * _COL_SPARK

        line += f"[{text_dim}]{sparkline}[/]"
        return line
