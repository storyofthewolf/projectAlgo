"""Formatting helpers for the cockpit TUI.

All functions return an em dash (—) for None inputs.
"""
from typing import Optional

_EM = "—"
_SPARK_CHARS = "▁▂▃▄▅▆▇█"


def _parse_hex(h: str) -> tuple:
    h = h.lstrip('#')
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _interpolate_hex(color_a: str, color_b: str, t: float) -> str:
    """Linear RGB interpolation: color_a at t=0, color_b at t=1."""
    r1, g1, b1 = _parse_hex(color_a)
    r2, g2, b2 = _parse_hex(color_b)
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def relative_strength_to_color(
    rs_value: Optional[float],
    intensity_max_pct: float,
    gradient_positive: str,
    gradient_negative: str,
    gradient_neutral: str,
) -> str:
    """
    Map a relative-strength decimal to a hex color via linear RGB interpolation.

    rs_value is a signed decimal (0.023 = +2.3%). intensity_max_pct is in percent
    units (5.0 = clamp at ±5%). None and zero both return gradient_neutral.
    """
    if rs_value is None:
        return gradient_neutral

    max_rs = intensity_max_pct / 100.0

    if rs_value >= max_rs:
        return gradient_positive
    if rs_value <= -max_rs:
        return gradient_negative

    if rs_value >= 0:
        t = rs_value / max_rs
        return _interpolate_hex(gradient_neutral, gradient_positive, t)
    else:
        t = -rs_value / max_rs
        return _interpolate_hex(gradient_neutral, gradient_negative, t)


def fmt_rs_pct(value: Optional[float]) -> str:
    """Format a relative-strength decimal as a signed percentage with 2 decimals.

    0.023 → "+2.30%", -0.0156 → "-1.56%", None → "—", 0.0 → "+0.00%".
    """
    if value is None:
        return _EM
    return fmt_pct(value * 100)


def _percentile(values: list[float], p: float) -> float:
    """Linear-interpolation percentile of a sorted or unsorted list."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n == 1:
        return s[0]
    idx = p / 100.0 * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return s[lo] * (1.0 - frac) + s[hi] * frac


def make_sparkline_percentile(values: list[float], width: int = 12) -> str:
    """Render a sparkline with percentile-based normalization.

    Uses 5th/95th percentiles as the visual range so a single outlier
    day doesn't compress all other bars into a narrow band.
    Downsamples by stride (not averaging) to preserve visible movement.
    Left-pads with ▁ when input is shorter than requested width.
    Flat input renders a row of middle blocks (▄).
    """
    if not values:
        return "▁" * width

    n = len(values)

    # Downsample to width by stride — preserves shape, doesn't smooth
    if n > width:
        step = n / width
        sampled = [values[min(round(i * step), n - 1)] for i in range(width)]
    else:
        sampled = list(values)

    lo_p = _percentile(sampled, 5)
    hi_p = _percentile(sampled, 95)

    if abs(hi_p - lo_p) < 1e-9:
        return "▄" * width

    chars: list[str] = []
    for v in sampled:
        clipped = max(lo_p, min(hi_p, v))
        level = round((clipped - lo_p) / (hi_p - lo_p) * 7)
        chars.append(_SPARK_CHARS[level])

    result = "".join(chars)

    # Left-pad when fewer samples than requested width (right-aligned to "now")
    if len(result) < width:
        result = "▁" * (width - len(result)) + result

    return result


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


def fmt_price_display(value: float | None) -> str:
    """Price with dollar sign, e.g. $548.23."""
    if value is None:
        return _EM
    return f"${value:,.2f}"


def fmt_index(value: float | None) -> str:
    """Index value without currency prefix, e.g. 16.42."""
    if value is None:
        return _EM
    return f"{value:,.2f}"


def fmt_yield(value: float | None) -> str:
    """Yield formatted to 3 decimal places, e.g. 4.482%."""
    if value is None:
        return _EM
    return f"{value:.3f}%"


def fmt_yield_change(change: float | None) -> str:
    """Signed absolute yield change, e.g. '+0.031' or '-0.042'."""
    if change is None:
        return _EM
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.3f}"


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
