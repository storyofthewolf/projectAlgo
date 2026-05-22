"""Cross-sectional scan CLI.

Scan a universe of tickers, filter with a pandas-style query, rank, and
print a table. Built for cheap hypothesis testing — type a condition,
see which tickers survive.

Usage:
    python -m scripts.scan <universe> [-q "<query>"] [options]
    python -m scripts.scan -t AAPL MSFT NVDA [-q "<query>"] [options]

  <universe>   an index universe (universes/<name>.txt, e.g. "sp500") or a
               watchlist name from watchlists.yaml. Index universes win on
               a name collision.
  -q QUERY     a filter expression over metric columns, e.g.
                 "rsi < 30 and close > sma200"
                 "close > sma50 * 1.02 and ret_1m > ret_3m"
               omit to keep every ticker.

Options:
    -t, --tickers SYM ...   ad-hoc universe instead of a named universe
    -q, --query "EXPR"      filter expression over metric columns
    --rank COL[ desc|asc]   sort by a column (default: descending)
    --columns COL ...       only show these metric columns
    --limit N               show at most N rows
    --list-metrics          print the available metric columns and exit

Examples:
    python -m scripts.scan default -q "rsi < 35"
    python -m scripts.scan sp500 -q "rsi < 30 and close > sma200" --rank rs_spy_1m
    python -m scripts.scan sp500 -q "vol_ratio > 2" --rank vol_ratio --limit 20
    python -m scripts.scan -t AAPL MSFT NVDA GOOGL -q "close > sma200" --rank "ret_1m desc"

Note: scanning a full index (~500 tickers) makes ~500 data fetches and can
take several minutes on a cold cache.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from analysis.screener import scan_universe

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WATCHLISTS_PATH = _PROJECT_ROOT / "watchlists.yaml"
_UNIVERSES_DIR = _PROJECT_ROOT / "universes"

# Columns shown when --columns is not given (the at-a-glance set).
_DEFAULT_COLUMNS = [
    "close", "rsi", "rsi_regime", "ret_5d", "ret_1m", "ret_3m",
    "pct_sma50", "pct_sma200", "vol_ratio", "rs_spy_1m",
]

_ALL_METRICS = [
    "close", "sma20", "sma50", "sma200",
    "pct_sma20", "pct_sma50", "pct_sma200",
    "rsi", "rsi_regime",
    "ret_5d", "ret_1m", "ret_3m", "ret_ytd",
    "volume", "avg_vol", "vol_ratio", "rs_spy_1m",
]


def _load_universe_file(path: Path) -> list[str]:
    """Read a universes/*.txt file: one ticker per line, # comments and blanks ignored."""
    tickers: list[str] = []
    seen: set[str] = set()
    for raw in path.read_text().splitlines():
        line = raw.split("#", 1)[0].strip().upper()
        if line and line not in seen:
            seen.add(line)
            tickers.append(line)
    return tickers


def _index_universes() -> dict[str, Path]:
    """Map universe name -> file path for every universes/*.txt file."""
    if not _UNIVERSES_DIR.is_dir():
        return {}
    return {p.stem: p for p in sorted(_UNIVERSES_DIR.glob("*.txt"))}


def _resolve_universe(name: str) -> list[str]:
    """Resolve a universe name to its ticker list.

    Index universes (universes/<name>.txt) are checked first, then watchlists
    from watchlists.yaml. Exits with a clear error if the name matches neither.
    """
    indexes = _index_universes()
    if name in indexes:
        tickers = _load_universe_file(indexes[name])
        if not tickers:
            sys.exit(f"error: universe file '{indexes[name].name}' has no tickers.")
        return tickers

    from cockpit.watchlists.yaml_provider import YamlWatchlistProvider

    provider = YamlWatchlistProvider(path=_WATCHLISTS_PATH)
    try:
        return list(provider.get_tickers(name))
    except KeyError:
        index_names = ", ".join(indexes) or "(none)"
        watchlist_names = ", ".join(provider.list_watchlists())
        sys.exit(
            f"error: universe '{name}' not found.\n"
            f"index universes: {index_names}\n"
            f"watchlists: {watchlist_names}\n"
            f"(or pass an ad-hoc universe with -t SYM SYM ...)"
        )


def _apply_query(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Filter df with a pandas query string; exit with a clear message on error."""
    query = query.strip()
    if not query:
        return df
    try:
        return df.query(query)
    except Exception as exc:
        sys.exit(
            f"error: could not evaluate query {query!r}: {exc}\n"
            f"available columns: {', '.join(_ALL_METRICS)}"
        )


def _apply_rank(df: pd.DataFrame, rank: str) -> pd.DataFrame:
    """Sort df by '<col> [desc|asc]'. Default direction is descending."""
    parts = rank.split()
    col = parts[0]
    ascending = len(parts) > 1 and parts[1].lower() == "asc"
    if col not in df.columns:
        sys.exit(
            f"error: cannot rank by '{col}' — not a column.\n"
            f"available columns: {', '.join(df.columns)}"
        )
    return df.sort_values(col, ascending=ascending, na_position="last")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="scan",
        description="Cross-sectional ticker scan.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("universe", nargs="?", default=None,
                        help="index universe (e.g. sp500) or watchlist name (omit if using -t)")
    parser.add_argument("-t", "--tickers", nargs="+", metavar="SYM",
                        help="ad-hoc universe instead of a named universe")
    parser.add_argument("-q", "--query", default="",
                        help="filter expression over metric columns")
    parser.add_argument("--rank", metavar="COL[ desc|asc]", default=None,
                        help="sort by a column (default direction: desc)")
    parser.add_argument("--columns", nargs="+", metavar="COL", default=None,
                        help="only show these metric columns")
    parser.add_argument("--limit", type=int, default=None,
                        help="show at most N rows")
    parser.add_argument("--list-metrics", action="store_true",
                        help="print available metric columns and exit")
    args = parser.parse_args()

    if args.list_metrics:
        print("available metric columns:")
        for m in _ALL_METRICS:
            print(f"  {m}")
        return

    # Resolve the universe: -t wins; otherwise the positional names a universe.
    if args.tickers:
        tickers = [t.upper() for t in args.tickers]
        universe_label = f"{len(tickers)} ad-hoc tickers"
    elif args.universe:
        tickers = _resolve_universe(args.universe)
        kind = "index" if args.universe in _index_universes() else "watchlist"
        universe_label = f"{kind} '{args.universe}' ({len(tickers)} tickers)"
    else:
        parser.error("provide a universe name or -t SYM SYM ...")

    print(f"scanning {universe_label}…", file=sys.stderr)
    result = scan_universe(tickers)

    if result.failed:
        print(f"  {len(result.failed)} ticker(s) excluded:", file=sys.stderr)
        for tk, reason in result.failed.items():
            print(f"    {tk}: {reason}", file=sys.stderr)

    metrics = result.metrics
    if metrics.empty:
        sys.exit("no tickers produced metrics — nothing to scan.")

    filtered = _apply_query(metrics, args.query)
    if args.rank:
        filtered = _apply_rank(filtered, args.rank)

    # Column selection
    if args.columns:
        bad = [c for c in args.columns if c not in metrics.columns]
        if bad:
            sys.exit(f"error: unknown column(s): {', '.join(bad)}")
        show_cols = args.columns
    else:
        show_cols = [c for c in _DEFAULT_COLUMNS if c in filtered.columns]

    if args.limit is not None:
        filtered = filtered.head(args.limit)

    matched = len(filtered)
    print(
        f"\n{matched} of {len(metrics)} ticker(s) matched"
        + (f"  ·  query: {args.query.strip()}" if args.query.strip() else "")
        + (f"  ·  ranked by {args.rank}" if args.rank else ""),
        file=sys.stderr,
    )

    if matched == 0:
        return

    with pd.option_context(
        "display.max_rows", None,
        "display.width", 240,
        "display.float_format", lambda v: f"{v:,.2f}",
    ):
        print(filtered[show_cols].to_string())


if __name__ == "__main__":
    main()
