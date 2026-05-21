"""Sector heatmap snapshot workflow.

Pure data in, pure data out. No Textual, no asyncio imports.
Callable from the cockpit, a Dash app, or a plain Python script.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from analysis.market_analysis import load_aligned_returns, calculate_relative_strength
from marketdata.service import get_data_service


SPDR_SECTORS: list = [
    ("XLK",  "Tech"),
    ("XLF",  "Financials"),
    ("XLV",  "Health"),
    ("XLY",  "Cons Disc"),
    ("XLC",  "Comm Svcs"),
    ("XLI",  "Industrial"),
    ("XLP",  "Cons Stap"),
    ("XLE",  "Energy"),
    ("XLU",  "Utilities"),
    ("XLRE", "RealEstate"),
    ("XLB",  "Materials"),
]


@dataclass
class SectorCell:
    """One cell in the sector heatmap."""
    symbol: str
    label: str
    relative_strength: Optional[float]
    sparkline_values: list = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class SectorSnapshot:
    """Complete sector heatmap snapshot."""
    cells: list
    benchmark_symbol: str
    lookback_days: int
    intensity_max_pct: float
    fetched_at: datetime
    error: Optional[str] = None


def build_sector_snapshot(
    sector_config,
    data_service=None,
    now: Optional[datetime] = None,
) -> SectorSnapshot:
    """
    Build a sector heatmap snapshot.

    Fetches OHLCV history for SPY + 11 sector ETFs over lookback_days * 2 calendar
    days, computes relative strength vs SPY, and packages cells in display order.

    Failure modes:
      - SPY fetch fails → SectorSnapshot(cells=[], error="Benchmark SPY unavailable")
      - One sector fails → that cell has relative_strength=None, error set; others OK
    """
    service = data_service if data_service is not None else get_data_service()
    now = now or datetime.now()

    benchmark = sector_config.comparison_ticker
    sector_symbols = [s for s, _ in SPDR_SECTORS]
    all_tickers = [benchmark] + sector_symbols

    end_date = now.date()
    start_date = end_date - timedelta(days=sector_config.lookback_days * 2 + 10)

    try:
        returns_df = load_aligned_returns(
            all_tickers,
            start_date.strftime('%Y-%m-%d'),
            end_date.strftime('%Y-%m-%d'),
            interval="1d",
            data_service=service,
        )
    except Exception as e:
        return SectorSnapshot(
            cells=[],
            benchmark_symbol=benchmark,
            lookback_days=sector_config.lookback_days,
            intensity_max_pct=sector_config.intensity_max_pct,
            fetched_at=now,
            error=f"Failed to load aligned returns: {e}",
        )

    if benchmark not in returns_df.columns:
        return SectorSnapshot(
            cells=[],
            benchmark_symbol=benchmark,
            lookback_days=sector_config.lookback_days,
            intensity_max_pct=sector_config.intensity_max_pct,
            fetched_at=now,
            error=f"Benchmark {benchmark} unavailable",
        )

    benchmark_returns = returns_df[benchmark]

    cells = []

    # SPY reference cell — RS is always 0 by definition
    cells.append(SectorCell(
        symbol=benchmark,
        label="S&P 500",
        relative_strength=0.0,
        sparkline_values=[0.0] * sector_config.lookback_days,
    ))

    for symbol, label in SPDR_SECTORS:
        if symbol not in returns_df.columns:
            cells.append(SectorCell(
                symbol=symbol,
                label=label,
                relative_strength=None,
                sparkline_values=[],
                error=f"{symbol} unavailable",
            ))
            continue
        try:
            rs_value, rs_path = calculate_relative_strength(
                returns_df[symbol],
                benchmark_returns,
                sector_config.lookback_days,
            )
            cells.append(SectorCell(
                symbol=symbol,
                label=label,
                relative_strength=rs_value,
                sparkline_values=rs_path,
            ))
        except Exception as e:
            cells.append(SectorCell(
                symbol=symbol,
                label=label,
                relative_strength=None,
                sparkline_values=[],
                error=str(e),
            ))

    return SectorSnapshot(
        cells=cells,
        benchmark_symbol=benchmark,
        lookback_days=sector_config.lookback_days,
        intensity_max_pct=sector_config.intensity_max_pct,
        fetched_at=now,
    )
