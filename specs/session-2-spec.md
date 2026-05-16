# projectAlgo — Session 2 Handoff Spec: Cockpit Skeleton + Home Screen

## Role and context

You are Claude Sonnet 4.6 acting as the executor for Session 2 of a planned multi-session build of `projectAlgo`. The architectural design has been hashed out with the project owner in a separate planning conversation using Claude Opus 4.7. Your job is **execution only**, not design. If you encounter genuine ambiguity not resolved by this spec, **stop and ask** rather than guessing — but the spec is intended to be complete enough that this should rarely be necessary.

The project owner is on a Claude Pro plan with a hard $5/month overage budget. Token efficiency matters. Work directly from this spec; do not re-derive decisions. If the spec contradicts itself somewhere, surface that immediately.

## Required reading before starting

1. `CLAUDE.md` (updated in Session 1 — reflects current architecture)
2. `notes/session-1-debrief.md` (Session 1 outcomes and open questions)
3. `cockpit.toml` (current config)
4. `config/settings.py` (how settings are loaded)
5. `marketdata/service.py` (the DataService — you'll wire to it in Session 3, but understand it now)
6. `core/quote.py` (Quote dataclass)
7. `requirements.txt` (you will add `textual` to this)

Run `python --version` to confirm — the project is on Python 3.14.5. You can use modern type syntax (`str | None`, `list[int]`, etc.) without `from __future__ import annotations`.

## What this session is

Session 2 builds a **visually complete, navigable shell** of the cockpit TUI using mock data. After Session 2:

- `python -m scripts.cockpit` launches the TUI
- The home screen displays with full layout: header, panels, footer
- All visual elements present and styled per the Bloomberg-density + Claude-warm-palette aesthetic
- Keyboard navigation works (`q`, `r`, `?`, `t`, `Tab`, `Esc`)
- Two themes selectable (`claude-warm`, `blue-orange`)
- Theme cycling via `t` previews both
- Help screen accessible via `?`
- Every number on screen is mock data — looks realistic, doesn't actually refresh
- The cockpit is ready for Session 3 to wire in real data

**What Session 2 does NOT build:**
- No real data wiring — DataService is not called this session
- No watchlist YAML loading
- No auto-refresh polling loop (the `r` key triggers a mock data regeneration, that's all)
- No sector / correlation / ticker drill-down screens
- No account panel content (placeholder only — Schwab is not connected)

If you find yourself wiring real data or building sub-screens beyond home + help, you have left the scope of this session. Stop.

## Aesthetic direction

Two design traditions in tension, intentionally reconciled:

**From Bloomberg terminals:**
- High information density (minimal padding, no empty rows between table entries)
- All caps for tickers, headers, labels
- Decimal alignment for prices
- Single-line box-drawing borders (`┌ ┐ └ ┘ ─ │`)
- Section titles integrated into the top border: `┌─ MARKET PULSE ─────────────`
- 8-level Unicode sparklines (▁▂▃▄▅▆▇█)
- Triangle arrows (▲ ▼) for directional indicators
- Compact volume notation (42.1M, 1.2B)
- Em dash (—) for missing/empty data, never "N/A" or blank
- Color-flash on cell update (inverse video flash, then settle to directional color)

**From Claude Code warm palette:**
- Warm orange/cream on near-black background, not Bloomberg amber
- The reconciliation is: Bloomberg's *behavior and layout*, Claude Code's *colors*

## Color themes

Two themes are required this session. Both are defined in `cockpit/themes.py` as Python dicts. The theme system is structured so that adding a third theme in the future means adding a single dict entry — nothing else changes.

### Theme 1: `claude-warm` (default)

```python
"claude-warm": {
    "background":      "#0d0d0d",
    "surface":         "#1a1612",
    "border":          "#3d3528",
    "border_active":   "#d97757",
    "primary":         "#d97757",   # Claude orange — headers, emphasis
    "secondary":       "#c8b896",   # warm cream — data text
    "text_primary":    "#f5e9d6",   # high-contrast cream
    "text_dim":        "#8a8275",   # warm gray — labels, secondary info
    "positive":        "#87a96b",   # warm sage green — ups
    "negative":        "#c75450",   # warm red — downs
    "neutral":         "#8a8275",
    "flash_up_bg":     "#87a96b",
    "flash_down_bg":   "#c75450",
    "flash_text":      "#0d0d0d",
}
```

### Theme 2: `blue-orange` (colorblind-friendly)

```python
"blue-orange": {
    "background":      "#0d0d0d",
    "surface":         "#15171a",
    "border":          "#2a3540",
    "border_active":   "#4a9eff",
    "primary":         "#4a9eff",   # blue — headers, emphasis
    "secondary":       "#c8b896",   # warm cream — data text (kept same)
    "text_primary":    "#e6eef5",
    "text_dim":        "#7a8290",
    "positive":        "#4a9eff",   # BLUE = UP (this is the whole point)
    "negative":        "#e89143",   # ORANGE = DOWN
    "neutral":         "#7a8290",
    "flash_up_bg":     "#4a9eff",
    "flash_down_bg":   "#e89143",
    "flash_text":      "#0d0d0d",
}
```

The active theme is read from `cockpit.toml` (`theme.default`) at startup. The `t` key cycles through available themes in the order they appear in the THEMES dict. Cycling is purely a Session 2 preview/dev feature — it's useful and harmless to keep.

The owner mentioned a long-term goal of per-room theme assignment. The theme system should be structured to make this easy later (e.g. a `screen.theme_name` attribute or a registry), but **do not implement per-room themes this session**. Just design the API so it's possible.

## Layout

Target terminal sizes:
- **Minimum:** 120 columns × 30 rows
- **Ideal:** 160 columns × 50 rows
- **Below minimum:** show a friendly "Please resize your terminal to at least 120×30" message

The layout adapts:
- At minimum size: tighter panels, compact watchlist (maybe 5 tickers visible), smaller sparklines
- At ideal size: full layout with more watchlist rows, wider correlation matrix, taller sector heatmap

Textual's grid/dock layout handles this natively. Use Textual's responsive features rather than implementing manual sizing logic.

### Home screen layout (target appearance at ~160 cols)

```
┌─ projectAlgo cockpit ─────────────── 09:47:23 ET │ MKT OPEN │ [DELAYED] ────────────────┐
│                                                                                          │
│ ┌─ ACCOUNT ───────────────┐ ┌─ MARKET PULSE ──────────────────────────────────────────┐ │
│ │                         │ │ SPY    582.43  +0.42% ▲   ▁▂▃▅▆▇▆▅▆▇                   │ │
│ │  Schwab not connected.  │ │ QQQ    512.18  +0.61% ▲   ▁▂▄▆▇▇▆▇▇▇                   │ │
│ │                         │ │ IWM    228.41  -0.18% ▼   ▇▆▅▄▃▂▃▃▂▁                   │ │
│ │  Run:                   │ │ VIX     14.20  -2.10% ▼   ▇▆▅▄▃▃▄▃▂▂                   │ │
│ │   python -m             │ │ 10Y     4.18%  +0.02  ▲   ▂▃▄▄▅▆▆▇▇▇                   │ │
│ │   scripts.schwab_auth   │ │ DXY    103.42  +0.05  —   ▅▅▆▅▅▆▅▅▆▅                   │ │
│ │                         │ │                                                          │ │
│ │  See CLAUDE.md          │ │                                                          │ │
│ │  for setup.             │ │                                                          │ │
│ └─────────────────────────┘ └──────────────────────────────────────────────────────────┘ │
│                                                                                          │
│ ┌─ WATCHLIST: HOLDINGS ─────────────────────────────────────────────────────────────────┐│
│ │ TICKER  LAST      CHG      CHG%      VOL     5D      30D     SPARK         RSI       ││
│ │ AAPL    187.42   +1.23    +0.66%   42.1M   +2.1%   +5.4%    ▁▂▃▅▆          58       ││
│ │ MSFT    412.18   +3.81    +0.93%   28.4M   +1.8%   +7.2%    ▂▃▄▅▆          62       ││
│ │ NVDA    132.91   -2.14    -1.58%   98.2M   -4.3%  +12.1%    ▆▅▄▃▂          47       ││
│ │ ISRG    487.55   +0.21    +0.04%    1.2M   +0.8%   +3.1%    ▄▅▅▄▅          52       ││
│ │ GOOGL   178.92   +2.41    +1.37%   18.7M   +3.2%   +8.9%    ▂▃▄▅▇          64       ││
│ └────────────────────────────────────────────────────────────────────────────────────────┘│
│                                                                                          │
│ ┌─ SECTOR HEATMAP ──────────────┐ ┌─ CORRELATIONS (30D, HOLDINGS) ────────────────────┐ │
│ │ XLK  TECH       +0.82% ████   │ │         AAPL   MSFT   NVDA   ISRG   GOOGL          │ │
│ │ XLC  COMM       +0.61% ███    │ │ AAPL    1.00   0.72   0.51   0.18   0.68           │ │
│ │ XLY  CONS.DISC  +0.43% ██     │ │ MSFT    0.72   1.00   0.68   0.22   0.81           │ │
│ │ XLF  FINANC.    +0.21% █      │ │ NVDA    0.51   0.68   1.00   0.15   0.59           │ │
│ │ XLI  INDUST.    +0.12% ▏      │ │ ISRG    0.18   0.22   0.15   1.00   0.21           │ │
│ │ XLP  CONS.STAP  -0.08% ▏      │ │ GOOGL   0.68   0.81   0.59   0.21   1.00           │ │
│ │ XLU  UTILITIES  -0.31% █      │ │                                                    │ │
│ │ XLE  ENERGY     -0.82% ███    │ │                                                    │ │
│ │ XLV  HEALTH     -0.41% █      │ │                                                    │ │
│ │ XLB  MATERIALS  -0.18% ▏      │ │                                                    │ │
│ │ XLRE REAL EST   -0.71% ██     │ │                                                    │ │
│ └───────────────────────────────┘ └────────────────────────────────────────────────────┘ │
│                                                                                          │
└─ [Q]UIT  [R]EFRESH  [?]HELP  [T]HEME  [TAB]NAV ─────────────────────────────────────────┘
```

### Panel arrangement

The home screen uses Textual's grid layout, conceptually:

- **Row 1 (header):** spans full width, height 1
- **Row 2 (account + market pulse):** account ~28 cols, market pulse fills remainder
- **Row 3 (watchlist):** spans full width
- **Row 4 (sectors + correlations):** sectors ~33 cols, correlations fills remainder
- **Row 5 (footer):** spans full width, height 1

Vertical proportions adapt to terminal height. Use Textual's `fr` units or grid sizing — don't hardcode pixel/character counts.

### Numeric formatting rules

These are universal across the cockpit:

| Type | Format | Example |
|---|---|---|
| Tickers | All caps | `AAPL`, never `aapl` |
| Prices | 2 decimal places always | `187.42`, never `187.4` or `187` |
| Percentages | 2 decimals, signed, % suffix | `+0.66%`, `-1.58%` |
| Volume | Compact notation | `42.1M`, `1.2B`, `987K` |
| Change (absolute) | 2 decimals, signed | `+1.23`, `-2.14` |
| Yields | 2 decimals, % suffix | `4.18%` |
| Missing data | Em dash | `—` (single character) |
| Sparklines | 8 levels: `▁▂▃▄▅▆▇█` | (10 chars wide typical) |
| Direction | `▲` (up), `▼` (down), `—` (flat) | single character |

Implement these as helper functions in `cockpit/format.py`. Examples:

```python
def fmt_price(value: float | None) -> str: ...
def fmt_pct(value: float | None) -> str: ...   # auto-signed
def fmt_volume(value: int | None) -> str: ...  # compact
def fmt_change(value: float | None) -> str: ... # signed
def fmt_arrow(value: float | None) -> str: ... # ▲ ▼ —
def fmt_ticker(value: str) -> str: ...          # uppercase
```

All of these return em dash `"—"` for None.

## Widget specifications

Six reusable widgets in `cockpit/widgets/`. Build these first — the home screen composes them.

### `Sparkline`

Renders a numeric sequence as Unicode block characters.

```python
class Sparkline(Static):
    """A compact text-based sparkline using Unicode block characters."""
    
    def __init__(self, values: list[float], width: int = 10):
        # Implementation: bin values into 8 levels (▁ to █)
        # If width < len(values), downsample by averaging or stride
        # If width > len(values), left-pad with spaces
        ...
```

The 8 levels in order: `▁▂▃▄▅▆▇█`. Min value of the input maps to `▁`, max to `█`, linearly interpolated.

### `PriceCell`

Displays a price with directional color. Supports flash animation.

```python
class PriceCell(Static):
    """A price cell that flashes when updated, then settles to directional color."""
    
    value: reactive[float | None]
    previous: float | None  # tracked for direction
    
    def update_price(self, new_value: float) -> None:
        """Update the displayed value and trigger flash animation."""
        # 1. Determine direction (up/down/flat) vs previous
        # 2. Apply CSS class for flash background (300ms)
        # 3. Transition to directional text color (3s)
        # 4. Settle to neutral
```

Use Textual's `set_timer` for the flash → settle transitions. Use CSS classes for the actual styling — defined in `cockpit/styles.tcss`.

### `PctCell`

Like `PriceCell` but for percentages. Same flash behavior. Always shows sign and `%` suffix.

### `PanelFrame`

A bordered container with the title integrated into the top border.

```python
class PanelFrame(Container):
    """A panel with title in top border, Bloomberg-style."""
    
    def __init__(self, title: str, *children):
        # Border characters: ┌ ┐ └ ┘ ─ │
        # Title appears in top border: ┌─ TITLE ─────────────
        # Title is uppercased automatically
        ...
```

Textual handles borders via CSS. The trick is rendering the title *within* the top border. Common pattern: a border with a `border_title` property. Use Textual's built-in `border_title` if available; otherwise implement via custom rendering.

### `ClockHeader`

Top header bar showing project name, time, market state, data source indicator.

```python
class ClockHeader(Static):
    """Top header: app name | time ET | market state | data status."""
    
    # Renders: "projectAlgo cockpit   09:47:23 ET │ MKT OPEN │ [DELAYED]"
    # Updates time every second via set_interval
    # Market state determined by current ET time:
    #   - PRE-MKT:    04:00-09:30 ET
    #   - MKT OPEN:   09:30-16:00 ET (weekdays only)
    #   - AFTER-HRS:  16:00-20:00 ET
    #   - MKT CLOSED: otherwise
    # Data status: [DELAYED] when active source is yfinance, [REAL-TIME] when schwab
    #   - For Session 2: hardcode to [DELAYED] (we're on yfinance only)
```

Time is always shown in ET regardless of user's local timezone. Use `zoneinfo.ZoneInfo("America/New_York")` (stdlib in 3.14).

The `[DELAYED]` indicator is dim text (text_dim color), positioned at the right end of the header.

### `CommandFooter`

Bottom bar showing available keyboard commands.

```python
class CommandFooter(Static):
    """Bottom bar: [Q]UIT  [R]EFRESH  [?]HELP  [T]HEME  [TAB]NAV"""
    
    def __init__(self, commands: list[tuple[str, str]]):
        # commands = [("Q", "QUIT"), ("R", "REFRESH"), ...]
        # Renders with the keyboard key in primary color, label in dim color
```

Each screen can pass its own command list. For Session 2, the home screen shows the bindings above.

## Application structure

### `cockpit/app.py`

```python
from textual.app import App
from textual.binding import Binding
from cockpit.themes import THEMES, get_active_theme
from cockpit.screens.home import HomeScreen
from cockpit.screens.help import HelpScreen
from config.settings import Settings


class CockpitApp(App):
    """projectAlgo cockpit — terminal-resident market monitoring."""
    
    CSS_PATH = "styles.tcss"
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("question_mark", "help", "Help", show=False),
        Binding("t", "cycle_theme", "Theme", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("escape", "pop_screen", "Back", show=False),
    ]
    
    def __init__(self):
        super().__init__()
        self.settings = Settings.load()
        self.theme_names = list(THEMES.keys())
        self.current_theme_idx = self.theme_names.index(self.settings.theme)
    
    def on_mount(self) -> None:
        self.apply_theme(self.theme_names[self.current_theme_idx])
        self.push_screen(HomeScreen())
    
    def apply_theme(self, name: str) -> None:
        """Apply theme by setting CSS variables on the App."""
        # Implementation: Textual supports CSS variables. Set them from
        # the theme dict. All widgets reference these via $primary, $background, etc.
        ...
    
    def action_cycle_theme(self) -> None:
        self.current_theme_idx = (self.current_theme_idx + 1) % len(self.theme_names)
        self.apply_theme(self.theme_names[self.current_theme_idx])
    
    def action_help(self) -> None:
        self.push_screen(HelpScreen())
    
    def action_refresh(self) -> None:
        """For Session 2: regenerate mock data and re-render."""
        # Get current screen, call its .refresh_mock() method if it has one
        ...
```

### `scripts/cockpit.py`

```python
"""Entry point for the cockpit TUI."""
from cockpit.app import CockpitApp


def main():
    app = CockpitApp()
    app.run()


if __name__ == "__main__":
    main()
```

Invocable as `python -m scripts.cockpit`.

### `cockpit/screens/home.py`

The home screen composes the widgets per the layout above. Reads mock data from `cockpit/mock_data.py`.

On `r` press: regenerates mock data (introduces randomness so prices change), triggers `PriceCell.update_price()` and `PctCell.update_pct()` to flash. This proves the flash mechanism works.

### `cockpit/screens/help.py`

A simple screen showing all keyboard bindings in a clean table. `Esc` returns to home. Bloomberg-density styling (compact, uppercase headers).

Layout:
```
┌─ HELP ────────────────────────────────────────────────────────────────┐
│                                                                       │
│  GLOBAL                                                               │
│    Q              QUIT                                                │
│    R              REFRESH SCREEN                                      │
│    ?              SHOW THIS HELP                                      │
│    T              CYCLE THEME                                         │
│    ESC            BACK TO PREVIOUS SCREEN                             │
│    TAB / SHIFT+TAB FOCUS NEXT / PREVIOUS PANEL                        │
│                                                                       │
│  HOME SCREEN                                                          │
│    (additional bindings reserved for future sessions:                 │
│     A=ACCOUNT, S=SECTORS, C=CORRELATIONS, W=WATCHLISTS, /=FIND)       │
│                                                                       │
│  CURRENT THEME: claude-warm                                           │
│  AVAILABLE: claude-warm, blue-orange                                  │
│                                                                       │
└─ [ESC]BACK ───────────────────────────────────────────────────────────┘
```

## Mock data

Hardcoded in `cockpit/mock_data.py`. Should look realistic enough to evaluate the UI.

```python
"""Mock data for cockpit visual development.

DELETE THIS FILE IN SESSION 3 once real data is wired.
"""
import random


WATCHLIST_HOLDINGS = [
    # (ticker, last, change, change_pct, volume, change_5d_pct, change_30d_pct, sparkline_values, rsi)
    ("AAPL",  187.42, +1.23, +0.66, 42_100_000, +2.1, +5.4,  [1,2,3,5,6], 58),
    ("MSFT",  412.18, +3.81, +0.93, 28_400_000, +1.8, +7.2,  [2,3,4,5,6], 62),
    ("NVDA",  132.91, -2.14, -1.58, 98_200_000, -4.3, +12.1, [6,5,4,3,2], 47),
    ("ISRG",  487.55, +0.21, +0.04,  1_200_000, +0.8, +3.1,  [4,5,5,4,5], 52),
    ("GOOGL", 178.92, +2.41, +1.37, 18_700_000, +3.2, +8.9,  [2,3,4,5,7], 64),
]

MARKET_PULSE = [
    # (ticker, last, change_pct, sparkline_values, format_hint)
    ("SPY", 582.43, +0.42, [1,2,3,5,6,7,6,5,6,7], "price"),
    ("QQQ", 512.18, +0.61, [1,2,4,6,7,7,6,7,7,7], "price"),
    ("IWM", 228.41, -0.18, [7,6,5,4,3,2,3,3,2,1], "price"),
    ("VIX",  14.20, -2.10, [7,6,5,4,3,3,4,3,2,2], "price"),
    ("10Y",   4.18, +0.48, [2,3,4,4,5,6,6,7,7,7], "yield"),
    ("DXY", 103.42, +0.05, [5,5,6,5,5,6,5,5,6,5], "price"),
]

SECTORS = [
    # (etf, name, change_pct)
    ("XLK", "TECH",       +0.82),
    ("XLC", "COMM",       +0.61),
    ("XLY", "CONS.DISC",  +0.43),
    ("XLF", "FINANC.",    +0.21),
    ("XLI", "INDUST.",    +0.12),
    ("XLP", "CONS.STAP",  -0.08),
    ("XLU", "UTILITIES",  -0.31),
    ("XLE", "ENERGY",     -0.82),
    ("XLV", "HEALTH",     -0.41),
    ("XLB", "MATERIALS",  -0.18),
    ("XLRE", "REAL EST",  -0.71),
]

# 5x5 matrix matching the watchlist tickers
CORRELATIONS = [
    #          AAPL  MSFT  NVDA  ISRG  GOOGL
    ("AAPL",  [1.00, 0.72, 0.51, 0.18, 0.68]),
    ("MSFT",  [0.72, 1.00, 0.68, 0.22, 0.81]),
    ("NVDA",  [0.51, 0.68, 1.00, 0.15, 0.59]),
    ("ISRG",  [0.18, 0.22, 0.15, 1.00, 0.21]),
    ("GOOGL", [0.68, 0.81, 0.59, 0.21, 1.00]),
]


def regenerate_mock() -> dict:
    """Return fresh mock data with small random perturbations.
    
    Called by the home screen on `r` press to demonstrate the flash mechanism.
    Each price is perturbed by ±0.5%, change_pct is recomputed.
    """
    ...
```

The `regenerate_mock()` function is what `r` triggers. It returns a fresh dict; the home screen feeds it into the widgets, which flash on update.

## Sector heatmap rendering

The sector panel shows each ETF with a horizontal bar indicating magnitude:

```
XLK  TECH       +0.82% ████
XLY  CONS.DISC  +0.43% ██
XLP  CONS.STAP  -0.08% ▏
XLE  ENERGY     -0.82% ████
```

Bar character: `█` for full units, `▏` for partial. Scale: 1 character per 0.2% of move, capped at ~10 characters. Positive moves get bars in `positive` color, negative in `negative` color. Sort by change_pct descending. This makes the rotation visually obvious.

## Correlation matrix rendering

Simple aligned grid. Header row with tickers, then each row labeled with a ticker. Cell values:
- `1.00` diagonal — dim color (not interesting)
- Values colored on a scale: high positive (>0.7) in `primary`, medium (0.3-0.7) in `secondary`, near-zero (-0.3 to 0.3) in `text_dim`, negative in `negative`
- 2 decimal places

## Textual styling — `cockpit/styles.tcss`

Use CSS variables wired to the theme system:

```css
Screen {
    background: $background;
    color: $text_primary;
}

PanelFrame {
    border: round $border;
    border-title-color: $primary;
    border-title-style: bold;
}

PriceCell {
    color: $text_primary;
}

PriceCell.flash-up {
    background: $flash_up_bg;
    color: $flash_text;
}

PriceCell.flash-down {
    background: $flash_down_bg;
    color: $flash_text;
}

PriceCell.directional-up {
    color: $positive;
}

PriceCell.directional-down {
    color: $negative;
}

/* ... etc ... */
```

When the theme changes (via `t`), update the CSS variables via the App's theme API. Textual supports this via `App.theme` or by setting variables on the screen — pick whichever is cleaner in current Textual.

## Cleanup tasks rolled into this session

These were identified in Session 1's debrief. Do them at the start of Session 2 before any TUI work:

1. **Remove the `from __future__ import annotations` import** from `analysis/technical_analysis.py`. The project is now on Python 3.14, so native union syntax (`pd.Series | pd.DataFrame`) works natively.

2. **Remove the `--data-dir` flag** from `scripts/get_data.py`'s argparse. The data directory is now controlled exclusively by `cockpit.toml`. The flag silently does nothing, which is a bad failure mode. Remove it so a future call with the flag fails loudly.

3. **Remove the `data_dir` parameter** from `analysis/market_analysis.py`'s `load_aligned_returns()` function. It's accepted but unused. Update all call sites if any.

After these three cleanups, smoke-test that existing scripts still work:
- `python -m scripts.get_data -t AAPL -i 1d -s 2024-01-01 -e 2024-12-31`
- `python -m scripts.correlations -t AAPL MSFT NVDA`
- `python -m scripts.run_backtest -t AAPL -s 2024-01-01 -e 2024-12-31`

All three should run cleanly. Then proceed to the cockpit build.

## Dependencies

Add to `requirements.txt`:

```
textual>=0.80
```

Then `pip install -r requirements.txt`. Verify Textual installs cleanly on Python 3.14. If there's a compatibility issue (Textual lagging on 3.14 support), surface it immediately — don't try to work around it.

## File layout produced this session

```
projectAlgo/
├── cockpit.toml                          [modify - confirm theme.default = "claude-warm"]
├── requirements.txt                      [modify - add textual]
├── analysis/technical_analysis.py        [modify - remove __future__ import]
├── analysis/market_analysis.py           [modify - remove unused data_dir param]
├── scripts/get_data.py                   [modify - remove --data-dir flag]
├── scripts/cockpit.py                    [NEW - entry point]
│
├── cockpit/                              [NEW package]
│   ├── __init__.py
│   ├── app.py                            [NEW - CockpitApp]
│   ├── themes.py                         [NEW - THEMES dict + helpers]
│   ├── styles.tcss                       [NEW - Textual CSS]
│   ├── bindings.py                       [NEW - shared binding definitions]
│   ├── format.py                         [NEW - fmt_price, fmt_pct, etc.]
│   ├── mock_data.py                      [NEW - to be deleted Session 3]
│   ├── screens/
│   │   ├── __init__.py
│   │   ├── home.py                       [NEW]
│   │   └── help.py                       [NEW]
│   └── widgets/
│       ├── __init__.py
│       ├── sparkline.py                  [NEW]
│       ├── price_cell.py                 [NEW]
│       ├── pct_cell.py                   [NEW]
│       ├── panel_frame.py                [NEW]
│       ├── clock_header.py               [NEW]
│       └── command_footer.py             [NEW]
│
└── notes/
    └── session-2-debrief.md              [NEW at end of session]
```

## Acceptance criteria

The session is complete when **all** of these pass:

**Cleanup tasks:**
1. `analysis/technical_analysis.py` no longer contains `from __future__ import annotations`. Smoke test: `python -m scripts.run_backtest -t AAPL -s 2024-01-01 -e 2024-12-31` succeeds.
2. `python -m scripts.get_data --data-dir foo -t AAPL -i 1d -s 2024-01-01 -e 2024-12-31` fails with an argparse error about unrecognized `--data-dir`.
3. `load_aligned_returns` no longer accepts a `data_dir` parameter; `python -m scripts.correlations -t AAPL MSFT NVDA` still works.

**Cockpit TUI:**
4. `python -m scripts.cockpit` launches the TUI without errors.
5. Home screen renders with all five panels populated with mock data.
6. Header shows: app name, ET time updating every second, market state, `[DELAYED]` indicator.
7. Footer shows command palette: `[Q]UIT  [R]EFRESH  [?]HELP  [T]HEME  [TAB]NAV`.
8. `q` quits cleanly.
9. `?` opens help screen; `Esc` returns to home.
10. `t` cycles theme between `claude-warm` and `blue-orange` with visible color change.
11. `r` regenerates mock data; price cells visibly flash and settle to directional color.
12. Tab navigates focus between panels (Textual default focus behavior is fine).
13. Resizing the terminal window: layout adapts smoothly. At a terminal smaller than 120×30, a "please resize" message displays.
14. Numeric formatting matches the rules: prices have 2 decimals, percentages signed, volume compact (M/B/K), tickers all-caps, missing data shows em dash.
15. Sparklines render with 8-level Unicode blocks.
16. Sector heatmap bars are visible and color-coded by direction.
17. Correlation matrix is aligned and color-coded.
18. Account panel shows the "Schwab not connected" placeholder, not fake account data.
19. Setting `theme.default = "blue-orange"` in `cockpit.toml`, restarting the cockpit, launches with blue-orange as the initial theme (not claude-warm).

## CLAUDE.md update

After all acceptance criteria pass, update `CLAUDE.md` to add a "Cockpit" section near the top, describing:

- Entry point: `python -m scripts.cockpit`
- Current capabilities (home screen with mock data, navigation, themes, help)
- Current limitations (no real data wiring yet — Session 3 will add it)
- Theme system overview and how to add new themes
- File layout of `cockpit/` package

Keep it concise. Don't repeat this spec verbatim.

## Session debrief

At the end of the session, create `notes/session-2-debrief.md` with:

1. **What got built** — one-paragraph summary
2. **What surprised you** — anything in Textual that worked differently than expected, any deviation from the spec
3. **Visual notes** — anything about the layout or aesthetic that worked well or didn't (this is what the owner will react to most)
4. **Open questions for Session 3 planning** — particularly around real data wiring, watchlist YAML schema, refresh polling
5. **Anything left undone** — if you ran short, what's the smallest cleanup needed

Optional but appreciated: include 1-2 screenshots of the cockpit running (if you can save them) — `notes/session-2-screenshots/`. Or describe what each panel looks like in text if screenshots aren't feasible from your environment.

## Working style notes

- Required reading first (the 7 files at the top). Don't skip.
- Do the cleanup tasks before starting the TUI work — gets them out of the way and confirms existing functionality still works.
- Build widgets bottom-up: `format.py` → individual widgets → screens → app. Smoke-test each widget in isolation before composing.
- Use Textual's idioms — don't fight the framework. If the spec describes something one way and Textual has a native idiom for it, use the native idiom.
- Make changes in small, verifiable batches. Run the TUI early and often to see what you're building.
- If something in this spec conflicts with current Textual API conventions (Textual evolves), surface it and pick the modern idiom. Note the deviation in the debrief.
- Do not add tests beyond inline smoke checks.
- Do not touch git.

## What to do if you get stuck

- Ambiguity: stop and ask. A 30-second clarification beats 30 minutes of rework.
- Textual API quirks (e.g. border_title doesn't work as described): pick the closest idiomatic solution, document the choice.
- Running out of context: stop at a clean checkpoint. A working app with one missing widget is better than a half-broken app with all widgets.
- If something visually feels wrong even though it matches the spec: surface it in the debrief. The owner will be reacting to aesthetics — your eye is useful here.
