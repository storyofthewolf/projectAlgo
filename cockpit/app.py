from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding

from cockpit.themes import THEMES, THEME_NAMES, THEMES_CONFIG, get_active_theme
from cockpit.screens.home import HomeScreen
from cockpit.screens.help import HelpScreen
from cockpit.watchlists.yaml_provider import YamlWatchlistProvider
from cockpit.watchlists.schwab_provider import SchwabWatchlistProvider
from cockpit.watchlists.registry import WatchlistRegistry
from config.settings import Settings


class CockpitApp(App):
    """projectAlgo cockpit — terminal-resident market monitoring."""

    CSS_PATH = Path(__file__).parent / "styles.tcss"

    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("question_mark", "help", "Help", show=False),
        Binding("t", "cycle_theme", "Theme", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("w", "cycle_watchlist", "Watchlist", show=False),
        Binding("escape", "pop_screen", "Back", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.settings = Settings.load()
        self.theme_names: list[str] = THEME_NAMES
        initial = self.settings.theme
        self.current_theme_idx: int = (
            self.theme_names.index(initial)
            if initial in self.theme_names
            else 0
        )
        # Register themes early so they're available for CSS variable resolution
        for t in THEMES.values():
            self.register_theme(t)

        project_root = Path(__file__).resolve().parent.parent
        self.watchlist_registry = WatchlistRegistry(providers=(
            YamlWatchlistProvider(path=project_root / "watchlists.yaml"),
            SchwabWatchlistProvider(),
        ))

    def get_css_variables(self) -> dict[str, str]:
        """Override to inject our custom theme variables into the CSS variable pool."""
        variables = super().get_css_variables()
        theme_name = self.theme if self.theme in THEMES_CONFIG else "claude-warm"
        cfg = THEMES_CONFIG[theme_name]
        variables.update({
            "text-dim":          cfg["text_dim"],
            "positive":          cfg["positive"],
            "negative":          cfg["negative"],
            "neutral":           cfg["neutral"],
            "border":            cfg["border"],
            "border-active":     cfg["border_active"],
            "text-primary":      cfg["text_primary"],
            "flash-up-bg":       cfg["flash_up_bg"],
            "flash-down-bg":     cfg["flash_down_bg"],
            "flash-text":        cfg["flash_text"],
            "gradient-positive": cfg["gradient_positive"],
            "gradient-negative": cfg["gradient_negative"],
            "gradient-neutral":  cfg["gradient_neutral"],
        })
        return variables

    def on_mount(self) -> None:
        self.theme = self.theme_names[self.current_theme_idx]
        self.push_screen(HomeScreen())
        self._check_terminal_size()

    def on_resize(self) -> None:
        self._check_terminal_size()

    def _check_terminal_size(self) -> None:
        size = self.size
        if size.width < 120 or size.height < 30:
            self.screen.add_class("too-small")
        else:
            self.screen.remove_class("too-small")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_cycle_theme(self) -> None:
        self.current_theme_idx = (self.current_theme_idx + 1) % len(self.theme_names)
        self.theme = self.theme_names[self.current_theme_idx]

    def action_refresh(self) -> None:
        """Delegate to the active screen's refresh handler."""
        screen = self.screen
        if hasattr(screen, "action_refresh"):
            screen.action_refresh()
        elif hasattr(screen, "refresh_mock"):
            screen.refresh_mock()

    def action_cycle_watchlist(self) -> None:
        """Delegate to HomeScreen's watchlist cycling."""
        screen = self.screen
        if hasattr(screen, "action_cycle_watchlist"):
            screen.action_cycle_watchlist()
