"""Theme definitions for the projectAlgo cockpit.

To add a new theme: add an entry to THEMES_CONFIG. Nothing else changes.
For future per-screen theme assignment, widgets carry a `theme_name` attribute
(currently unused) that the App can reference when switching screens.
"""
from textual.theme import Theme

THEMES_CONFIG: dict[str, dict[str, str]] = {
    "claude-warm": {
        "background":        "#0d0d0d",
        "surface":           "#1a1612",
        "border":            "#3d3528",
        "border_active":     "#d97757",
        "primary":           "#d97757",
        "secondary":         "#c8b896",
        "text_primary":      "#f5e9d6",
        "text_dim":          "#8a8275",
        "positive":          "#87a96b",
        "negative":          "#c75450",
        "neutral":           "#8a8275",
        "flash_up_bg":       "#87a96b",
        "flash_down_bg":     "#c75450",
        "flash_text":        "#0d0d0d",
        "gradient_positive": "#1ba5c0",
        "gradient_negative": "#d68a2e",
        "gradient_neutral":  "#3a3530",
    },
    "blue-orange": {
        "background":        "#0d0d0d",
        "surface":           "#15171a",
        "border":            "#2a3540",
        "border_active":     "#4a9eff",
        "primary":           "#4a9eff",
        "secondary":         "#c8b896",
        "text_primary":      "#e6eef5",
        "text_dim":          "#7a8290",
        "positive":          "#4a9eff",
        "negative":          "#e89143",
        "neutral":           "#7a8290",
        "flash_up_bg":       "#4a9eff",
        "flash_down_bg":     "#e89143",
        "flash_text":        "#0d0d0d",
        "gradient_positive": "#1ba5c0",
        "gradient_negative": "#d68a2e",
        "gradient_neutral":  "#2c333d",
    },
}


def _make_theme(name: str, cfg: dict[str, str]) -> Theme:
    return Theme(
        name=name,
        primary=cfg["primary"],
        secondary=cfg["secondary"],
        background=cfg["background"],
        surface=cfg["surface"],
        dark=True,
        variables={
            "border":        cfg["border"],
            "border-active": cfg["border_active"],
            "text-primary":  cfg["text_primary"],
            "text-dim":      cfg["text_dim"],
            "positive":      cfg["positive"],
            "negative":      cfg["negative"],
            "neutral":       cfg["neutral"],
            "flash-up-bg":   cfg["flash_up_bg"],
            "flash-down-bg": cfg["flash_down_bg"],
            "flash-text":    cfg["flash_text"],
        },
    )


THEMES: dict[str, Theme] = {
    name: _make_theme(name, cfg) for name, cfg in THEMES_CONFIG.items()
}

THEME_NAMES: list[str] = list(THEMES.keys())


def get_active_theme(name: str) -> Theme:
    return THEMES.get(name, THEMES["claude-warm"])
