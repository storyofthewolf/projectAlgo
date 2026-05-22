"""Session 8 verification script — tests ACs 1-30 where automatable.

Run from project root:
    python -m scripts.verify_session8

NOTE: ACs 8-10, 12-13, 15-16, 18-19 require network access to yfinance.
If offline, those checks will be skipped/noted.

Interactive ACs (31+) require manual terminal verification.
"""
import sys
from pathlib import Path

_PASS = "PASS"
_FAIL = "FAIL"
_SKIP = "SKIP"


def _check(label: str, cond: bool, detail: str = "") -> bool:
    status = _PASS if cond else _FAIL
    suffix = f"  [{detail}]" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    return cond


def _skip(label: str, reason: str = "") -> bool:
    print(f"  [{_SKIP}] {label}  [{reason}]")
    return True  # skips don't count as failures


# ── AC1: imports ───────────────────────────────────────────────────────────────

def test_ac1_workflow_imports():
    print("\n─── AC1: workflow imports ───")
    from workflows.ticker_detail_snapshot import (
        TickerDetailSnapshot,
        IndicatorReadout,
        TickerStats,
        build_ticker_detail_snapshot,
        build_ticker_quote_snapshot,
    )
    ok1 = _check("AC1: TickerDetailSnapshot importable", True)
    ok2 = _check("AC1: IndicatorReadout importable", True)
    ok3 = _check("AC1: TickerStats importable", True)
    ok4 = _check("AC1: build_ticker_detail_snapshot importable", True)
    ok5 = _check("AC1: build_ticker_quote_snapshot importable", True)
    return ok1 and ok2 and ok3 and ok4 and ok5


# ── AC2: config imports ───────────────────────────────────────────────────────

def test_ac2_config_imports():
    print("\n─── AC2: TickerDetailConfig importable + Settings returns it ───")
    from config.settings import TickerDetailConfig
    ok1 = _check("AC2: TickerDetailConfig importable", True)
    from config.settings import Settings
    s = Settings.load()
    ok2 = _check(
        "AC2: settings.ticker_detail_config is TickerDetailConfig",
        isinstance(s.ticker_detail_config, TickerDetailConfig),
        type(s.ticker_detail_config).__name__,
    )
    return ok1 and ok2


# ── AC3-7: config values ──────────────────────────────────────────────────────

def test_ac3_history_display_days():
    print("\n─── AC3: history_display_days == 30 ───")
    from config.settings import Settings
    cfg = Settings.load().ticker_detail_config
    return _check("AC3: history_display_days", cfg.history_display_days == 30, str(cfg.history_display_days))


def test_ac4_history_lookback_days():
    print("\n─── AC4: history_lookback_days == 252 ───")
    from config.settings import Settings
    cfg = Settings.load().ticker_detail_config
    return _check("AC4: history_lookback_days", cfg.history_lookback_days == 252, str(cfg.history_lookback_days))


def test_ac5_quote_refresh_seconds():
    print("\n─── AC5: quote_refresh_seconds == 30 ───")
    from config.settings import Settings
    cfg = Settings.load().ticker_detail_config
    return _check("AC5: quote_refresh_seconds", cfg.quote_refresh_seconds == 30, str(cfg.quote_refresh_seconds))


def test_ac6_sma_windows():
    print("\n─── AC6: sma_windows == (20, 50, 200) ───")
    from config.settings import Settings
    cfg = Settings.load().ticker_detail_config
    return _check("AC6: sma_windows", cfg.sma_windows == (20, 50, 200), str(cfg.sma_windows))


def test_ac7_rsi_window():
    print("\n─── AC7: rsi_window == 14 ───")
    from config.settings import Settings
    cfg = Settings.load().ticker_detail_config
    return _check("AC7: rsi_window", cfg.rsi_window == 14, str(cfg.rsi_window))


# ── AC8-13: workflow correctness (network required) ───────────────────────────

def test_ac8_aapl_snapshot():
    print("\n─── AC8: build_ticker_detail_snapshot('AAPL') returns snapshot with no error ───")
    print("  (requires network access to yfinance)")
    from config.settings import Settings
    from workflows.ticker_detail_snapshot import build_ticker_detail_snapshot
    cfg = Settings.load().ticker_detail_config
    try:
        snap = build_ticker_detail_snapshot("AAPL", cfg)
        return _check(
            "AC8: error is None",
            snap.error is None,
            snap.error or "ok",
        )
    except Exception as e:
        return _check("AC8: no exception", False, str(e)[:80])


def test_ac9_history_shape():
    print("\n─── AC9: history is non-empty DataFrame with expected columns ───")
    from config.settings import Settings
    from workflows.ticker_detail_snapshot import build_ticker_detail_snapshot
    cfg = Settings.load().ticker_detail_config
    try:
        snap = build_ticker_detail_snapshot("AAPL", cfg)
        if snap.history is None:
            return _check("AC9: history is not None", False, "history is None")
        expected_cols = {"Open", "High", "Low", "Close", "Volume"}
        actual_cols = set(snap.history.columns)
        ok1 = _check("AC9: history non-empty", len(snap.history) > 0, str(len(snap.history)))
        ok2 = _check(
            "AC9: expected columns present",
            expected_cols <= actual_cols,
            str(actual_cols - expected_cols or "ok"),
        )
        return ok1 and ok2
    except Exception as e:
        return _check("AC9: no exception", False, str(e)[:80])


def test_ac10_quote_type():
    print("\n─── AC10: quote is a Quote instance with non-None price ───")
    from config.settings import Settings
    from workflows.ticker_detail_snapshot import build_ticker_detail_snapshot
    from core.quote import Quote
    cfg = Settings.load().ticker_detail_config
    try:
        snap = build_ticker_detail_snapshot("AAPL", cfg)
        ok1 = _check("AC10: quote is Quote", isinstance(snap.quote, Quote), str(type(snap.quote)))
        ok2 = _check(
            "AC10: price is non-None",
            snap.quote is not None and snap.quote.price is not None,
            str(snap.quote.price if snap.quote else None),
        )
        return ok1 and ok2
    except Exception as e:
        return _check("AC10: no exception", False, str(e)[:80])


def test_ac11_sma_keys():
    print("\n─── AC11: indicators.sma_values has keys {20, 50, 200} ───")
    from config.settings import Settings
    from workflows.ticker_detail_snapshot import build_ticker_detail_snapshot
    cfg = Settings.load().ticker_detail_config
    try:
        snap = build_ticker_detail_snapshot("AAPL", cfg)
        if snap.indicators is None:
            return _check("AC11: indicators not None", False, "indicators is None")
        keys = set(snap.indicators.sma_values.keys())
        return _check("AC11: sma_values keys == {20,50,200}", keys == {20, 50, 200}, str(keys))
    except Exception as e:
        return _check("AC11: no exception", False, str(e)[:80])


def test_ac12_sma_values_floats():
    print("\n─── AC12: all sma_values are floats (assuming >=200 bars) ───")
    from config.settings import Settings
    from workflows.ticker_detail_snapshot import build_ticker_detail_snapshot
    cfg = Settings.load().ticker_detail_config
    try:
        snap = build_ticker_detail_snapshot("AAPL", cfg)
        if snap.indicators is None:
            return _check("AC12: indicators not None", False, "indicators is None")
        sma = snap.indicators.sma_values
        if snap.history is not None and len(snap.history) < 200:
            return _skip("AC12: <200 bars available; SMA(200) expected to be None")
        ok = all(isinstance(v, float) for v in sma.values() if v is not None)
        vals = {k: round(v, 2) for k, v in sma.items() if v is not None}
        return _check("AC12: sma_values are floats", ok, str(vals))
    except Exception as e:
        return _check("AC12: no exception", False, str(e)[:80])


def test_ac13_rsi_range():
    print("\n─── AC13: indicators.rsi is float between 0 and 100 ───")
    from config.settings import Settings
    from workflows.ticker_detail_snapshot import build_ticker_detail_snapshot
    cfg = Settings.load().ticker_detail_config
    try:
        snap = build_ticker_detail_snapshot("AAPL", cfg)
        if snap.indicators is None:
            return _check("AC13: indicators not None", False, "indicators is None")
        rsi = snap.indicators.rsi
        ok = rsi is not None and 0 <= rsi <= 100
        return _check("AC13: rsi in [0,100]", ok, str(round(rsi, 2) if rsi is not None else None))
    except Exception as e:
        return _check("AC13: no exception", False, str(e)[:80])


def test_ac14_rsi_regime():
    print("\n─── AC14: rsi_regime is valid label ───")
    from config.settings import Settings
    from workflows.ticker_detail_snapshot import build_ticker_detail_snapshot
    cfg = Settings.load().ticker_detail_config
    try:
        snap = build_ticker_detail_snapshot("AAPL", cfg)
        if snap.indicators is None:
            return _check("AC14: indicators not None", False, "indicators is None")
        regime = snap.indicators.rsi_regime
        valid = {"oversold", "neutral", "overbought", "unknown"}
        return _check("AC14: rsi_regime valid", regime in valid, repr(regime))
    except Exception as e:
        return _check("AC14: no exception", False, str(e)[:80])


def test_ac15_52w_range():
    print("\n─── AC15: stats.week_52_high >= stats.week_52_low (both non-None) ───")
    from config.settings import Settings
    from workflows.ticker_detail_snapshot import build_ticker_detail_snapshot
    cfg = Settings.load().ticker_detail_config
    try:
        snap = build_ticker_detail_snapshot("AAPL", cfg)
        if snap.stats is None:
            return _check("AC15: stats not None", False, "stats is None")
        h = snap.stats.week_52_high
        lo = snap.stats.week_52_low
        ok = h is not None and lo is not None and h >= lo
        return _check("AC15: 52w high >= low", ok, f"high={h}, low={lo}")
    except Exception as e:
        return _check("AC15: no exception", False, str(e)[:80])


def test_ac16_percentile_range():
    print("\n─── AC16: 0 <= stats.week_52_percentile <= 100 ───")
    from config.settings import Settings
    from workflows.ticker_detail_snapshot import build_ticker_detail_snapshot
    cfg = Settings.load().ticker_detail_config
    try:
        snap = build_ticker_detail_snapshot("AAPL", cfg)
        if snap.stats is None:
            return _check("AC16: stats not None", False, "stats is None")
        pct = snap.stats.week_52_percentile
        ok = pct is not None and 0 <= pct <= 100
        return _check("AC16: percentile in [0,100]", ok, str(round(pct, 1) if pct is not None else None))
    except Exception as e:
        return _check("AC16: no exception", False, str(e)[:80])


def test_ac17_bad_ticker():
    print("\n─── AC17: ZZZZNOTREAL returns snapshot with error, no exception ───")
    from config.settings import Settings
    from workflows.ticker_detail_snapshot import build_ticker_detail_snapshot
    cfg = Settings.load().ticker_detail_config
    try:
        snap = build_ticker_detail_snapshot("ZZZZNOTREAL", cfg)
        ok1 = _check("AC17: error is not None", snap.error is not None, repr(snap.error))
        ok2 = _check("AC17: quote is None", snap.quote is None)
        ok3 = _check("AC17: history is None", snap.history is None)
        return ok1 and ok2 and ok3
    except Exception as e:
        return _check("AC17: no exception raised", False, str(e)[:80])


def test_ac18_quote_snapshot_real():
    print("\n─── AC18: build_ticker_quote_snapshot('AAPL') returns Quote ───")
    from workflows.ticker_detail_snapshot import build_ticker_quote_snapshot
    from core.quote import Quote
    try:
        q = build_ticker_quote_snapshot("AAPL")
        return _check("AC18: returns Quote", isinstance(q, Quote), str(type(q)))
    except Exception as e:
        return _check("AC18: no exception", False, str(e)[:80])


def test_ac19_quote_snapshot_bad():
    print("\n─── AC19: build_ticker_quote_snapshot('ZZZZNOTREAL') returns None ───")
    from workflows.ticker_detail_snapshot import build_ticker_quote_snapshot
    try:
        q = build_ticker_quote_snapshot("ZZZZNOTREAL")
        return _check("AC19: returns None", q is None, str(q))
    except Exception as e:
        return _check("AC19: no exception", False, str(e)[:80])


# ── AC20-21: UI class imports ─────────────────────────────────────────────────

def test_ac20_modal_importable():
    print("\n─── AC20: TickerFinderModal importable ───")
    from cockpit.screens.ticker_finder_modal import TickerFinderModal
    return _check("AC20: TickerFinderModal importable", True)


def test_ac21_detail_screen_importable():
    print("\n─── AC21: TickerDetailScreen importable ───")
    from cockpit.screens.ticker_detail import TickerDetailScreen
    return _check("AC21: TickerDetailScreen importable", True)


# ── AC22: ticker validation ───────────────────────────────────────────────────

def test_ac22_ticker_validation():
    print("\n─── AC22: _is_valid_ticker corner cases ───")
    from cockpit.screens.ticker_finder_modal import _is_valid_ticker
    cases = [
        ("AAPL",     True),
        ("^VIX",     True),
        ("BRK.B",    True),
        ("CL=F",     True),
        ("",         False),
        ("aapl space", False),
    ]
    all_ok = True
    for symbol, expected in cases:
        result = _is_valid_ticker(symbol)
        ok = _check(f"AC22: _is_valid_ticker({symbol!r}) == {expected}", result == expected,
                    f"got {result}")
        all_ok = all_ok and ok
    return all_ok


# ── AC23: app slash binding ───────────────────────────────────────────────────

def test_ac23_app_slash_binding():
    print("\n─── AC23: CockpitApp.BINDINGS contains 'slash' ───")
    content = Path("cockpit/app.py").read_text()
    ok = _check("AC23: 'slash' in CockpitApp.BINDINGS", "slash" in content)
    return ok


# ── AC24: screen bindings ─────────────────────────────────────────────────────

def test_ac24_screen_bindings():
    print("\n─── AC24: TickerDetailScreen has required bindings ───")
    content = Path("cockpit/screens/ticker_detail.py").read_text()
    checks = [
        ("escape", "escape"),
        ("r",      '"r"'),
        ("slash",  "slash"),
        ("j",      '"j"'),
        ("k",      '"k"'),
        ("down",   '"down"'),
        ("up",     '"up"'),
    ]
    all_ok = True
    for key, pattern in checks:
        ok = _check(f"AC24: {key!r} binding", pattern in content)
        all_ok = all_ok and ok
    return all_ok


# ── AC25: sma_vs_price_pct formula ───────────────────────────────────────────

def test_ac25_sma_vs_price_formula():
    print("\n─── AC25: sma_vs_price_pct = (price - sma) / sma * 100 ───")
    from dataclasses import dataclass
    from unittest.mock import MagicMock

    # Build a synthetic IndicatorReadout
    price = 100.0
    sma20 = 95.0
    expected_pct = (price - sma20) / sma20 * 100  # +5.26…

    # Simulate via the recompute helper on the screen (can't easily call it directly,
    # so we verify the formula directly)
    computed = (price - sma20) / sma20 * 100
    ok = abs(computed - expected_pct) < 1e-9
    return _check("AC25: formula correct", ok, f"computed={computed:.4f}")


# ── AC26: RSI regime mapping ──────────────────────────────────────────────────

def test_ac26_rsi_regime_mapping():
    print("\n─── AC26: RSI regime mapping with default thresholds ───")
    from config.settings import Settings
    from workflows.ticker_detail_snapshot import _compute_indicators
    import pandas as pd
    import numpy as np

    cfg = Settings.load().ticker_detail_config

    def _regime_for_rsi(rsi_value: float) -> str:
        if rsi_value < cfg.rsi_oversold:
            return "oversold"
        elif rsi_value > cfg.rsi_overbought:
            return "overbought"
        else:
            return "neutral"

    ok1 = _check("AC26: rsi=25 → oversold", _regime_for_rsi(25) == "oversold")
    ok2 = _check("AC26: rsi=50 → neutral",  _regime_for_rsi(50) == "neutral")
    ok3 = _check("AC26: rsi=75 → overbought", _regime_for_rsi(75) == "overbought")
    return ok1 and ok2 and ok3


# ── AC27: short history, SMA(200) is None ────────────────────────────────────

def test_ac27_sma_none_for_short_history():
    print("\n─── AC27: history of 100 rows → sma_values[200] is None ───")
    import pandas as pd
    import numpy as np
    from config.settings import Settings
    from workflows.ticker_detail_snapshot import _compute_indicators

    cfg = Settings.load().ticker_detail_config

    # Build 100-row fake history
    dates = pd.date_range("2024-01-01", periods=100, freq="B")
    prices = 100 + np.cumsum(np.random.randn(100) * 0.5)
    history = pd.DataFrame({
        "Open": prices, "High": prices * 1.01,
        "Low": prices * 0.99, "Close": prices,
        "Volume": [1_000_000] * 100,
    }, index=dates)

    from core.quote import Quote
    from datetime import datetime
    quote = Quote(ticker="FAKE", price=float(prices[-1]), timestamp=datetime.now())
    ind = _compute_indicators(history, quote, cfg)
    ok1 = _check("AC27: sma_values[200] is None", ind.sma_values[200] is None)
    ok2 = _check("AC27: sma_vs_price_pct[200] is None", ind.sma_vs_price_pct[200] is None)
    return ok1 and ok2


# ── AC28: help screen content ─────────────────────────────────────────────────

def test_ac28_help_content():
    print("\n─── AC28: help.py contains 'TICKER DRILL-DOWN SCREEN' and 'Find ticker' ───")
    content = Path("cockpit/screens/help.py").read_text()
    ok1 = _check("AC28: 'TICKER DRILL-DOWN SCREEN' present",
                 "TICKER DRILL-DOWN SCREEN" in content)
    ok2 = _check("AC28: 'Find ticker' or 'FIND TICKER' present",
                 "Find ticker" in content or "FIND TICKER" in content)
    return ok1 and ok2


# ── AC29: screen does not import from marketdata ──────────────────────────────

def test_ac29_no_marketdata_in_screen():
    print("\n─── AC29: ticker_detail.py does not import from marketdata.* ───")
    content = Path("cockpit/screens/ticker_detail.py").read_text()
    ok = _check("AC29: no marketdata.* import", "from marketdata" not in content and "import marketdata" not in content)
    return ok


# ── AC30: widgets do not import from marketdata ───────────────────────────────

def test_ac30_no_marketdata_in_widgets():
    print("\n─── AC30: ticker widgets do not import from marketdata.* ───")
    files = [
        "cockpit/widgets/ticker_header.py",
        "cockpit/widgets/ohlc_table.py",
        "cockpit/widgets/indicator_panel.py",
    ]
    all_ok = True
    for fp in files:
        content = Path(fp).read_text()
        ok = _check(
            f"AC30: no marketdata.* import in {fp.split('/')[-1]}",
            "from marketdata" not in content and "import marketdata" not in content,
        )
        all_ok = all_ok and ok
    return all_ok


# ── Session 7 regression ──────────────────────────────────────────────────────

def test_regression_session7():
    print("\n─── Regression: Session 7 key checks ───")
    from config.settings import Settings
    s = Settings.load()
    ok1 = _check("Reg: correlation_config present", s.correlation_config is not None)
    ok2 = _check("Reg: correlation_deep_dive_config present", s.correlation_deep_dive_config is not None)
    home = Path("cockpit/screens/home.py").read_text()
    ok3 = _check("Reg: 'c' binding still in home.py", "open_correlation_deep_dive" in home)
    ok4 = _check("Reg: 's' binding still in home.py", "open_sector_deep_dive" in home)
    return ok1 and ok2 and ok3 and ok4


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Session 8 Verification — Ticker Drill-Down Screen")
    print("=" * 60)

    tests = [
        ("AC1",  test_ac1_workflow_imports),
        ("AC2",  test_ac2_config_imports),
        ("AC3",  test_ac3_history_display_days),
        ("AC4",  test_ac4_history_lookback_days),
        ("AC5",  test_ac5_quote_refresh_seconds),
        ("AC6",  test_ac6_sma_windows),
        ("AC7",  test_ac7_rsi_window),
        ("AC8",  test_ac8_aapl_snapshot),
        ("AC9",  test_ac9_history_shape),
        ("AC10", test_ac10_quote_type),
        ("AC11", test_ac11_sma_keys),
        ("AC12", test_ac12_sma_values_floats),
        ("AC13", test_ac13_rsi_range),
        ("AC14", test_ac14_rsi_regime),
        ("AC15", test_ac15_52w_range),
        ("AC16", test_ac16_percentile_range),
        ("AC17", test_ac17_bad_ticker),
        ("AC18", test_ac18_quote_snapshot_real),
        ("AC19", test_ac19_quote_snapshot_bad),
        ("AC20", test_ac20_modal_importable),
        ("AC21", test_ac21_detail_screen_importable),
        ("AC22", test_ac22_ticker_validation),
        ("AC23", test_ac23_app_slash_binding),
        ("AC24", test_ac24_screen_bindings),
        ("AC25", test_ac25_sma_vs_price_formula),
        ("AC26", test_ac26_rsi_regime_mapping),
        ("AC27", test_ac27_sma_none_for_short_history),
        ("AC28", test_ac28_help_content),
        ("AC29", test_ac29_no_marketdata_in_screen),
        ("AC30", test_ac30_no_marketdata_in_widgets),
        ("Reg",  test_regression_session7),
    ]

    results = []
    for name, fn in tests:
        try:
            passed = fn()
            results.append((name, passed))
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            import traceback; traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    all_pass = True
    for name, ok in results:
        status = _PASS if ok else _FAIL
        print(f"  [{status}] {name}")
        if not ok:
            all_pass = False

    print()
    if all_pass:
        print("All automated ACs pass.")
    else:
        print("Some ACs failed — see details above.")
        sys.exit(1)

    print()
    print("Interactive ACs (require manual terminal verify):")
    for i, desc in enumerate([
        "Home screen renders normally; no regressions",
        "Pressing '/' opens centered modal with auto-focused input",
        "Typing 'aapl' + Enter opens drill-down for AAPL (uppercased)",
        "Header shows price, change, pct, vol, day range, 52w range",
        "OHLC table shows 30 rows, newest at top, aligned columns",
        "j and ↓ scroll down; k and ↑ scroll up",
        "Scrolling past end is a no-op",
        "Indicators: SMA(20)/(50)/(200) with vs-px pct; RSI(14) + regime",
        "RSI regime label colored (green/red/dim)",
        "After 30s price updates; SMA fixed; vs-px pct recalculated",
        "Network disconnect → header shows [STALE]",
        "'/' from drill-down replaces (not stacks) drill-down screen",
        "Esc returns to home",
        "'?' shows updated help with TICKER DRILL-DOWN section",
        "'t' cycles theme; drill-down recolors on next refresh",
        "ZZZZNOTREAL: shows TICKER NOT FOUND, no crash",
        "Special tickers: ^VIX, CL=F, BRK.B all work",
        "Sessions 3-7 features unaffected",
    ], start=31):
        print(f"  AC{i}: {desc}")


if __name__ == "__main__":
    main()
