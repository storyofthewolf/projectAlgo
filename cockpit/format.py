"""Formatting helpers for the cockpit TUI.

All functions return an em dash (—) for None inputs.
"""

_EM = "—"
_SPARK_CHARS = "▁▂▃▄▅▆▇█"


def fmt_price(value: float | None) -> str:
    if value is None:
        return _EM
    return f"{value:,.2f}"


def fmt_pct(value: float | None) -> str:
    """Signed percentage, e.g. +0.66% or -1.58%."""
    if value is None:
        return _EM
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}%"


def fmt_change(value: float | None) -> str:
    """Signed absolute change, e.g. +1.23 or -2.14."""
    if value is None:
        return _EM
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.2f}"


def fmt_volume(value: int | None) -> str:
    """Compact volume: 42100000 → 42.1M."""
    if value is None:
        return _EM
    v = float(value)
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.1f}K"
    return str(int(v))


def fmt_arrow(value: float | None) -> str:
    """Directional indicator: ▲, ▼, or —."""
    if value is None:
        return _EM
    if value > 0:
        return "▲"
    if value < 0:
        return "▼"
    return "—"


def fmt_ticker(value: str) -> str:
    return value.upper()


def fmt_yield(value: float | None) -> str:
    """Yield formatted as e.g. 4.18%."""
    if value is None:
        return _EM
    return f"{value:.2f}%"


def make_sparkline(values: list[float], width: int = 10) -> str:
    """Render a list of floats as a Unicode sparkline string."""
    if not values:
        return " " * width

    lo, hi = min(values), max(values)
    span = hi - lo

    chars: list[str] = []
    for v in values:
        if span == 0:
            level = 4
        else:
            level = round((v - lo) / span * 7)
        chars.append(_SPARK_CHARS[level])

    result = "".join(chars)

    # Downsample or pad to requested width
    if len(result) > width:
        # stride-based downsample: pick evenly spaced characters
        step = len(result) / width
        result = "".join(result[round(i * step)] for i in range(width))
    elif len(result) < width:
        result = " " * (width - len(result)) + result

    return result


def make_sector_bar(change_pct: float, scale: float = 0.2, max_chars: int = 10) -> str:
    """Render a horizontal bar for sector heatmap.

    1 character per `scale` percentage points, capped at `max_chars`.
    Uses █ for full characters, ▏ for small magnitudes.
    """
    mag = abs(change_pct)
    n = min(round(mag / scale), max_chars)
    if n == 0:
        return "▏"
    return "█" * n


def fmt_corr(value: float) -> str:
    """Format a correlation value to 2 decimal places."""
    return f"{value:.2f}"
