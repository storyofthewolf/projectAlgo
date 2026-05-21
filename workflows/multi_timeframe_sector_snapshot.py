"""Multi-timeframe sector snapshot workflow.

Pure data in, pure data out. No Textual, no asyncio imports.
Callable from the cockpit, a Dash app, or a plain Python script.
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence

from analysis.market_analysis import load_aligned_returns, calculate_relative_strength
from marketdata.service import get_data_service
from workflows.sector_snapshot import SPDR_SECTORS


@dataclass(frozen=True)
class TimeframeRS:
    """Relative strength result for one (sector, timeframe) pair."""
    label: str
    rs_value: float | None
    rs_path: tuple[float, ...]


@dataclass(frozen=True)
class SectorRow:
    """One row of the sector deep-dive table."""
    symbol: str
    name: str
    is_benchmark: bool
    timeframes: tuple[TimeframeRS, ...]
    error: str | None = None


@dataclass(frozen=True)
class MultiTimeframeSectorSnapshot:
    """The full sector deep-dive view."""
    rows: tuple[SectorRow, ...]
    timeframe_labels: tuple[str, ...]
    timestamp: datetime
    error: str | None = None


def _compute_fetch_start(timeframes: Sequence, now_date: date) -> date:
    """Compute the earliest start date needed to cover all configured timeframes."""
    max_trading_days = 0
    has_ytd = False

    for tf in timeframes:
        if tf.trading_days is not None:
            max_trading_days = max(max_trading_days, tf.trading_days)
        elif tf.calendar == "ytd":
            has_ytd = True

    # Calendar days buffer: trading_days * 1.6 + 10 to absorb weekends/holidays.
    # Cap at 3 years so absurdly large timeframes don't trigger massive fetches.
    _MAX_LOOKBACK = 3 * 365
    raw_days = int(max_trading_days * 1.6) + 10
    td_start = now_date - timedelta(days=min(raw_days, _MAX_LOOKBACK))

    if has_ytd:
        ytd_start = date(now_date.year, 1, 1)
        return min(td_start, ytd_start)
    return td_start


def _slice_for_timeframe(returns_series, tf, now_date: date):
    """Slice a returns Series for the given timeframe. Returns the sliced Series."""
    if tf.trading_days is not None:
        return returns_series.iloc[-tf.trading_days:]
    else:  # ytd
        year_start = date(now_date.year, 1, 1)
        mask = returns_series.index.date >= year_start
        return returns_series[mask]


def _compute_timeframe_rs(
    sector_returns,
    benchmark_returns,
    tf,
    now_date: date,
) -> TimeframeRS:
    """Compute one TimeframeRS entry. Returns None rs_value on insufficient data."""
    sliced_sector = _slice_for_timeframe(sector_returns, tf, now_date)
    sliced_bench = _slice_for_timeframe(benchmark_returns, tf, now_date)

    n = min(len(sliced_sector), len(sliced_bench))
    # For trading_days timeframes, require at least the requested number of bars.
    if tf.trading_days is not None and n < tf.trading_days:
        return TimeframeRS(label=tf.label, rs_value=None, rs_path=())
    if n < 2:
        return TimeframeRS(label=tf.label, rs_value=None, rs_path=())

    sliced_sector = sliced_sector.iloc[-n:]
    sliced_bench = sliced_bench.iloc[-n:]

    try:
        rs_value, rs_path = calculate_relative_strength(sliced_sector, sliced_bench, n)
        return TimeframeRS(label=tf.label, rs_value=rs_value, rs_path=tuple(rs_path))
    except (ValueError, Exception):
        return TimeframeRS(label=tf.label, rs_value=None, rs_path=())


def build_multi_timeframe_sector_snapshot(
    timeframes: Sequence,
    sector_config,
    data_service=None,
    now: datetime | None = None,
) -> MultiTimeframeSectorSnapshot:
    """
    Build a multi-timeframe sector deep-dive snapshot.

    One aligned fetch covers all timeframes. SPY is pinned at the top
    with rs_value=0.0. Each sector row has one TimeframeRS per configured
    timeframe.

    Failure modes:
      - Benchmark missing → snapshot with rows=(), error set
      - One sector missing → that SectorRow has error set; others render
      - One timeframe insufficient data → that TimeframeRS has rs_value=None; others render
    """
    service = data_service if data_service is not None else get_data_service()
    now = now or datetime.now()
    now_date = now.date()

    benchmark = sector_config.comparison_ticker
    sector_symbols = [s for s, _ in SPDR_SECTORS]
    all_tickers = [benchmark] + sector_symbols

    tf_labels = tuple(tf.label for tf in timeframes)
    fetch_start = _compute_fetch_start(timeframes, now_date)

    try:
        returns_df = load_aligned_returns(
            all_tickers,
            fetch_start.strftime('%Y-%m-%d'),
            now_date.strftime('%Y-%m-%d'),
            interval="1d",
            data_service=service,
        )
    except Exception as e:
        return MultiTimeframeSectorSnapshot(
            rows=(),
            timeframe_labels=tf_labels,
            timestamp=now,
            error=f"Failed to load returns: {e}",
        )

    if benchmark not in returns_df.columns:
        return MultiTimeframeSectorSnapshot(
            rows=(),
            timeframe_labels=tf_labels,
            timestamp=now,
            error=f"Benchmark {benchmark} unavailable",
        )

    benchmark_returns = returns_df[benchmark]

    # SPY pin-row: rs_value=0.0 for all timeframes, rs_path filled with zeros
    spy_tf_list = []
    for tf in timeframes:
        sliced = _slice_for_timeframe(benchmark_returns, tf, now_date)
        path_len = max(2, len(sliced))
        spy_tf_list.append(TimeframeRS(
            label=tf.label,
            rs_value=0.0,
            rs_path=tuple([0.0] * path_len),
        ))
    spy_row = SectorRow(
        symbol=benchmark,
        name="S&P 500",
        is_benchmark=True,
        timeframes=tuple(spy_tf_list),
    )

    rows = [spy_row]

    for symbol, name in SPDR_SECTORS:
        if symbol not in returns_df.columns:
            empty_tfs = tuple(
                TimeframeRS(label=tf.label, rs_value=None, rs_path=())
                for tf in timeframes
            )
            rows.append(SectorRow(
                symbol=symbol,
                name=name,
                is_benchmark=False,
                timeframes=empty_tfs,
                error=f"{symbol} unavailable",
            ))
            continue

        sector_returns = returns_df[symbol]
        tf_results = []
        for tf in timeframes:
            tf_rs = _compute_timeframe_rs(sector_returns, benchmark_returns, tf, now_date)
            tf_results.append(tf_rs)

        rows.append(SectorRow(
            symbol=symbol,
            name=name,
            is_benchmark=False,
            timeframes=tuple(tf_results),
        ))

    return MultiTimeframeSectorSnapshot(
        rows=tuple(rows),
        timeframe_labels=tf_labels,
        timestamp=now,
    )
