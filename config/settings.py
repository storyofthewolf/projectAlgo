from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib


@dataclass(frozen=True)
class SectorConfig:
    lookback_days: int = 20
    comparison_ticker: str = "SPY"
    intensity_max_pct: float = 5.0
    refresh_interval_seconds: int = 300


@dataclass(frozen=True)
class Timeframe:
    label: str
    trading_days: int | None = None
    calendar: str | None = None    # only "ytd" supported


@dataclass(frozen=True)
class SectorDeepDiveConfig:
    refresh_interval_seconds: int
    default_sort_column: str
    default_sort_direction: str    # "asc" or "desc"
    timeframes: tuple[Timeframe, ...]


_DEFAULT_SECTOR_DEEP_DIVE_CONFIG = SectorDeepDiveConfig(
    refresh_interval_seconds=60,
    default_sort_column="1M",
    default_sort_direction="desc",
    timeframes=(
        Timeframe("5D",  trading_days=5),
        Timeframe("1M",  trading_days=21),
        Timeframe("3M",  trading_days=63),
        Timeframe("YTD", calendar="ytd"),
    ),
)


@dataclass(frozen=True)
class PulseTicker:
    symbol: str
    label: str
    format: str   # "price", "index", or "yield"


_DEFAULT_PULSE_TICKERS: tuple[PulseTicker, ...] = (
    PulseTicker("SPY",       "S&P 500",   "price"),
    PulseTicker("QQQ",       "NASDAQ",    "price"),
    PulseTicker("IWM",       "Russell 2K","price"),
    PulseTicker("^VIX",      "VIX",       "index"),
    PulseTicker("^TNX",      "10Y Yield", "yield"),
    PulseTicker("DX-Y.NYB",  "Dollar",    "index"),
    PulseTicker("CL=F",      "Oil",       "price"),
    PulseTicker("GC=F",      "Gold",      "price"),
)


def _parse_sector_deep_dive(raw: dict) -> SectorDeepDiveConfig:
    """Parse and validate the [sector_deep_dive] TOML table."""
    tf_raw = raw.get('timeframes', None)

    if tf_raw is None:
        timeframes = _DEFAULT_SECTOR_DEEP_DIVE_CONFIG.timeframes
    else:
        if len(tf_raw) < 2:
            raise ValueError(
                f"[sector_deep_dive] timeframes must have at least 2 entries, got {len(tf_raw)}"
            )
        if len(tf_raw) > 6:
            raise ValueError(
                f"[sector_deep_dive] timeframes must have at most 6 entries, got {len(tf_raw)}"
            )
        labels_seen: set[str] = set()
        parsed: list[Timeframe] = []
        for i, entry in enumerate(tf_raw):
            if 'label' not in entry:
                raise ValueError(
                    f"[sector_deep_dive] timeframes[{i}] is missing 'label'"
                )
            label = entry['label']
            if label in labels_seen:
                raise ValueError(
                    f"[sector_deep_dive] duplicate timeframe label '{label}'"
                )
            labels_seen.add(label)

            has_td = 'trading_days' in entry
            has_cal = 'calendar' in entry
            if has_td and has_cal:
                raise ValueError(
                    f"[sector_deep_dive] timeframe '{label}' has both 'trading_days' "
                    f"and 'calendar' — use exactly one"
                )
            if not has_td and not has_cal:
                raise ValueError(
                    f"[sector_deep_dive] timeframe '{label}' has neither 'trading_days' "
                    f"nor 'calendar' — use exactly one"
                )
            if has_td:
                td = entry['trading_days']
                if not isinstance(td, int) or td < 1:
                    raise ValueError(
                        f"[sector_deep_dive] timeframe '{label}' trading_days must be a "
                        f"positive integer, got {td!r}"
                    )
                parsed.append(Timeframe(label=label, trading_days=td))
            else:
                cal = str(entry['calendar']).lower()
                if cal != 'ytd':
                    raise ValueError(
                        f"[sector_deep_dive] timeframe '{label}' calendar='{cal}' is not "
                        f"supported; only 'ytd' is supported"
                    )
                parsed.append(Timeframe(label=label, calendar=cal))
        timeframes = tuple(parsed)

    refresh = raw.get('refresh_interval_seconds', 60)
    sort_col = raw.get(
        'default_sort_column', _DEFAULT_SECTOR_DEEP_DIVE_CONFIG.default_sort_column
    )
    sort_dir = str(raw.get('default_sort_direction', 'desc')).lower()

    if sort_dir not in ('asc', 'desc'):
        raise ValueError(
            f"[sector_deep_dive] default_sort_direction must be 'asc' or 'desc', got '{sort_dir}'"
        )

    tf_labels = {tf.label for tf in timeframes}
    if sort_col not in tf_labels:
        raise ValueError(
            f"[sector_deep_dive] default_sort_column '{sort_col}' is not among "
            f"timeframe labels {sorted(tf_labels)}"
        )

    return SectorDeepDiveConfig(
        refresh_interval_seconds=refresh,
        default_sort_column=sort_col,
        default_sort_direction=sort_dir,
        timeframes=timeframes,
    )


@dataclass(frozen=True)
class Settings:
    preferred_source: str
    data_dir: Path
    backtest_results_dir: Path
    refresh_interval_seconds: int
    theme: str
    log_level: str
    pulse_tickers: tuple[PulseTicker, ...]
    sector_config: SectorConfig
    sector_deep_dive_config: SectorDeepDiveConfig

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Settings":
        """Load settings from cockpit.toml at project root."""
        project_root = Path(__file__).resolve().parent.parent
        if path is None:
            path = project_root / "cockpit.toml"

        with open(path, 'rb') as f:
            data = tomllib.load(f)

        pulse_raw = data.get('pulse', {}).get('tickers', None)
        if pulse_raw:
            pulse_tickers = tuple(
                PulseTicker(
                    symbol=t['symbol'],
                    label=t['label'],
                    format=t['format'],
                )
                for t in pulse_raw
            )
        else:
            pulse_tickers = _DEFAULT_PULSE_TICKERS

        sectors_raw = data.get('sectors', {})
        sector_config = SectorConfig(
            lookback_days=sectors_raw.get('lookback_days', 20),
            comparison_ticker=sectors_raw.get('comparison_ticker', 'SPY'),
            intensity_max_pct=sectors_raw.get('intensity_max_pct', 5.0),
            refresh_interval_seconds=sectors_raw.get('refresh_interval_seconds', 300),
        )

        deep_dive_raw = data.get('sector_deep_dive', None)
        if deep_dive_raw is None:
            sector_deep_dive_config = _DEFAULT_SECTOR_DEEP_DIVE_CONFIG
        else:
            sector_deep_dive_config = _parse_sector_deep_dive(deep_dive_raw)

        return cls(
            preferred_source=data['data']['preferred_source'],
            data_dir=project_root / data['data']['data_dir'],
            backtest_results_dir=project_root / data['data']['backtest_results_dir'],
            refresh_interval_seconds=data['refresh']['interval_seconds'],
            theme=data['theme']['default'],
            log_level=data['logging']['level'],
            pulse_tickers=pulse_tickers,
            sector_config=sector_config,
            sector_deep_dive_config=sector_deep_dive_config,
        )
