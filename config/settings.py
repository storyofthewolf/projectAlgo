from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib


@dataclass(frozen=True)
class Settings:
    preferred_source: str
    data_dir: Path
    backtest_results_dir: Path
    refresh_interval_seconds: int
    theme: str
    log_level: str

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Settings":
        """Load settings from cockpit.toml at project root."""
        project_root = Path(__file__).resolve().parent.parent
        if path is None:
            path = project_root / "cockpit.toml"

        with open(path, 'rb') as f:
            data = tomllib.load(f)

        return cls(
            preferred_source=data['data']['preferred_source'],
            data_dir=project_root / data['data']['data_dir'],
            backtest_results_dir=project_root / data['data']['backtest_results_dir'],
            refresh_interval_seconds=data['refresh']['interval_seconds'],
            theme=data['theme']['default'],
            log_level=data['logging']['level'],
        )
