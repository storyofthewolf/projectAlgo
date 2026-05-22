from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import tomllib
except ImportError:
    import tomli as tomllib


_VALID_CORR_METHODS = ("pearson", "spearman", "kendall")


@dataclass(frozen=True)
class TickerDetailConfig:
    history_display_days: int
    history_lookback_days: int
    quote_refresh_seconds: int
    sma_windows: tuple
    rsi_window: int
    rsi_oversold: float
    rsi_overbought: float


_DEFAULT_TICKER_DETAIL_CONFIG = TickerDetailConfig(
    history_display_days=30,
    history_lookback_days=252,
    quote_refresh_seconds=30,
    sma_windows=(20, 50, 200),
    rsi_window=14,
    rsi_oversold=30.0,
    rsi_overbought=70.0,
)


def _parse_ticker_detail(raw: dict) -> TickerDetailConfig:
    """Parse and validate the [ticker_detail] TOML table."""
    sma_raw = raw.get("sma_windows", [20, 50, 200])
    sma_windows = tuple(int(w) for w in sma_raw)
    return TickerDetailConfig(
        history_display_days=int(raw.get("history_display_days", 30)),
        history_lookback_days=int(raw.get("history_lookback_days", 252)),
        quote_refresh_seconds=int(raw.get("quote_refresh_seconds", 30)),
        sma_windows=sma_windows,
        rsi_window=int(raw.get("rsi_window", 14)),
        rsi_oversold=float(raw.get("rsi_oversold", 30.0)),
        rsi_overbought=float(raw.get("rsi_overbought", 70.0)),
    )


@dataclass(frozen=True)
class CorrelationConfig:
    """Home-screen correlation panel config."""
    tickers: tuple[str, ...]
    lookback_days: int
    method: str
    refresh_interval_seconds: int


@dataclass(frozen=True)
class CorrelationDeepDiveConfig:
    """Correlation deep-dive screen config."""
    presets: dict[str, tuple[str, ...]]
    default_preset: str
    default_method: str
    default_lookback_days: int
    lookback_options: tuple[int, ...]
    refresh_interval_seconds: int


_DEFAULT_CORRELATION_CONFIG = CorrelationConfig(
    tickers=("SPY", "QQQ", "IWM", "TLT", "GLD", "^VIX"),
    lookback_days=60,
    method="pearson",
    refresh_interval_seconds=300,
)

_DEFAULT_CORRELATION_DEEP_DIVE_CONFIG = CorrelationDeepDiveConfig(
    presets={
        "cross_asset": ("SPY", "QQQ", "IWM", "TLT", "GLD", "^VIX", "DX-Y.NYB", "CL=F"),
        "sectors": ("XLK", "XLF", "XLV", "XLY", "XLC", "XLI", "XLP", "XLE", "XLU", "XLRE", "XLB"),
        "mega_cap": ("AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"),
    },
    default_preset="cross_asset",
    default_method="pearson",
    default_lookback_days=60,
    lookback_options=(10, 20, 60, 120, 252),
    refresh_interval_seconds=60,
)


def _parse_correlations(raw: dict) -> CorrelationConfig:
    """Parse and validate the [correlations] TOML table."""
    method = str(raw.get("method", "pearson")).lower()
    if method not in _VALID_CORR_METHODS:
        raise ValueError(
            f"[correlations] method '{method}' is not valid; "
            f"must be one of {_VALID_CORR_METHODS}"
        )
    lookback = raw.get("lookback_days", 60)
    if not isinstance(lookback, int) or lookback < 2:
        raise ValueError(
            f"[correlations] lookback_days must be an integer >= 2, got {lookback!r}"
        )
    tickers_raw = raw.get("tickers", None)
    if tickers_raw:
        tickers = tuple(str(t) for t in tickers_raw)
    else:
        tickers = _DEFAULT_CORRELATION_CONFIG.tickers
    return CorrelationConfig(
        tickers=tickers,
        lookback_days=lookback,
        method=method,
        refresh_interval_seconds=raw.get("refresh_interval_seconds", 300),
    )


def _parse_correlation_deep_dive(raw: dict) -> CorrelationDeepDiveConfig:
    """Parse and validate the [correlation_deep_dive] TOML table."""
    presets_raw = raw.get("presets", {})
    if not presets_raw:
        presets = _DEFAULT_CORRELATION_DEEP_DIVE_CONFIG.presets
    else:
        presets = {name: tuple(str(t) for t in tickers)
                   for name, tickers in presets_raw.items()}

    default_preset = raw.get("default_preset", "cross_asset")
    if default_preset not in presets:
        raise ValueError(
            f"[correlation_deep_dive] default_preset '{default_preset}' "
            f"is not among preset names {sorted(presets.keys())}"
        )

    default_method = str(raw.get("default_method", "pearson")).lower()
    if default_method not in _VALID_CORR_METHODS:
        raise ValueError(
            f"[correlation_deep_dive] default_method '{default_method}' is not valid; "
            f"must be one of {_VALID_CORR_METHODS}"
        )

    lookback_options_raw = raw.get("lookback_options", [10, 20, 60, 120, 252])
    lookback_options = tuple(int(x) for x in lookback_options_raw)

    default_lookback = raw.get("default_lookback_days", 60)
    if default_lookback not in lookback_options:
        raise ValueError(
            f"[correlation_deep_dive] default_lookback_days {default_lookback} "
            f"is not in lookback_options {lookback_options}"
        )

    return CorrelationDeepDiveConfig(
        presets=presets,
        default_preset=default_preset,
        default_method=default_method,
        default_lookback_days=default_lookback,
        lookback_options=lookback_options,
        refresh_interval_seconds=raw.get("refresh_interval_seconds", 60),
    )


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
    correlation_config: CorrelationConfig
    correlation_deep_dive_config: CorrelationDeepDiveConfig
    ticker_detail_config: TickerDetailConfig

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

        corr_raw = data.get('correlations', None)
        if corr_raw is None:
            correlation_config = _DEFAULT_CORRELATION_CONFIG
        else:
            correlation_config = _parse_correlations(corr_raw)

        corr_dd_raw = data.get('correlation_deep_dive', None)
        if corr_dd_raw is None:
            correlation_deep_dive_config = _DEFAULT_CORRELATION_DEEP_DIVE_CONFIG
        else:
            correlation_deep_dive_config = _parse_correlation_deep_dive(corr_dd_raw)

        ticker_detail_raw = data.get('ticker_detail', None)
        if ticker_detail_raw is None:
            ticker_detail_config = _DEFAULT_TICKER_DETAIL_CONFIG
        else:
            ticker_detail_config = _parse_ticker_detail(ticker_detail_raw)

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
            correlation_config=correlation_config,
            correlation_deep_dive_config=correlation_deep_dive_config,
            ticker_detail_config=ticker_detail_config,
        )
