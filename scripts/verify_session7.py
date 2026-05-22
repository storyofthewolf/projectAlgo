"""Session 7 verification script — tests ACs 1-31 where automatable.

Run from project root:
    python -m scripts.verify_session7

Interactive ACs (32-39) require manual terminal verification.
"""
import sys
import tempfile
from pathlib import Path

_PASS = "PASS"
_FAIL = "FAIL"


def _check(label: str, cond: bool, detail: str = "") -> bool:
    status = _PASS if cond else _FAIL
    suffix = f"  [{detail}]" if detail else ""
    print(f"  [{status}] {label}{suffix}")
    return cond


# ── AC1-3: exports ────────────────────────────────────────────────────────────

def test_ac1_exports():
    print("\n─── AC1: workflow exports ───")
    from workflows.correlation_snapshot import (
        CorrelationSnapshot, RankedPair, build_correlation_snapshot
    )
    ok1 = _check("AC1: CorrelationSnapshot exported", True)
    ok2 = _check("AC1: RankedPair exported", True)
    ok3 = _check("AC1: build_correlation_snapshot exported", True)
    return ok1 and ok2 and ok3


def test_ac2_snapshot_fields():
    print("\n─── AC2: CorrelationSnapshot is frozen dataclass with required fields ───")
    from workflows.correlation_snapshot import CorrelationSnapshot
    import dataclasses
    ok1 = _check("AC2: is dataclass", dataclasses.is_dataclass(CorrelationSnapshot))
    fields = {f.name for f in dataclasses.fields(CorrelationSnapshot)}
    required = {"tickers","requested_tickers","failed_tickers","method","lookback_days",
                "matrix","ranked_pairs","as_of","error"}
    missing = required - fields
    ok2 = _check("AC2: all required fields present", len(missing) == 0, str(missing))
    return ok1 and ok2


def test_ac3_ranked_pair_fields():
    print("\n─── AC3: RankedPair is frozen dataclass ───")
    from workflows.correlation_snapshot import RankedPair
    import dataclasses
    ok1 = _check("AC3: is dataclass", dataclasses.is_dataclass(RankedPair))
    fields = {f.name for f in dataclasses.fields(RankedPair)}
    ok2 = _check("AC3: ticker_a, ticker_b, correlation fields",
                 {"ticker_a","ticker_b","correlation"} <= fields)
    return ok1 and ok2


# ── AC4-12: workflow correctness ──────────────────────────────────────────────

def test_ac4_basic_matrix():
    print("\n─── AC4: 3-ticker snapshot → 3×3 matrix, diagonal=1, symmetric ───")
    from workflows.correlation_snapshot import build_correlation_snapshot
    snap = build_correlation_snapshot(["SPY","QQQ","IWM"], 30)
    ok1 = _check("AC4: matrix is 3×3", snap.matrix is not None and snap.matrix.shape == (3,3),
                 str(snap.matrix.shape if snap.matrix is not None else None))
    diag = [round(snap.matrix.loc[t,t], 6) for t in snap.tickers] if snap.matrix is not None else []
    ok2 = _check("AC4: diagonal == 1.0", all(d == 1.0 for d in diag), str(diag))
    sym = True
    if snap.matrix is not None:
        m = snap.matrix
        for a in snap.tickers:
            for b in snap.tickers:
                if abs(m.loc[a,b] - m.loc[b,a]) > 1e-9:
                    sym = False
    ok3 = _check("AC4: matrix is symmetric", sym)
    return ok1 and ok2 and ok3


def test_ac5_method_propagated():
    print("\n─── AC5: method='spearman' produces different matrix ───")
    from workflows.correlation_snapshot import build_correlation_snapshot
    snap_p = build_correlation_snapshot(["SPY","QQQ","IWM"], 30, method="pearson")
    snap_s = build_correlation_snapshot(["SPY","QQQ","IWM"], 30, method="spearman")
    if snap_p.matrix is None or snap_s.matrix is None:
        return _check("AC5: both matrices computed", False, "one is None")
    diff = abs(snap_p.matrix.loc["SPY","QQQ"] - snap_s.matrix.loc["SPY","QQQ"])
    ok = _check("AC5: pearson != spearman for SPY-QQQ", diff > 1e-9,
                f"diff={diff:.6f}")
    return ok


def test_ac6_bad_ticker_dropped():
    print("\n─── AC6: bad ticker → dropped, 2×2 matrix, failed_tickers set ───")
    from workflows.correlation_snapshot import build_correlation_snapshot
    snap = build_correlation_snapshot(["SPY","NOT_A_REAL_TICKER_XYZ","QQQ"], 30)
    ok1 = _check("AC6: matrix is 2×2", snap.matrix is not None and snap.matrix.shape == (2,2),
                 str(snap.matrix.shape if snap.matrix is not None else None))
    ok2 = _check("AC6: failed_tickers contains bad ticker",
                 "NOT_A_REAL_TICKER_XYZ" in snap.failed_tickers, str(snap.failed_tickers))
    return ok1 and ok2


def test_ac7_all_bad_tickers():
    print("\n─── AC7: all bad tickers → matrix=None, error set ───")
    from workflows.correlation_snapshot import build_correlation_snapshot
    snap = build_correlation_snapshot(["NOT_A_TICKER_1","NOT_A_TICKER_2"], 30)
    ok1 = _check("AC7: matrix is None", snap.matrix is None)
    ok2 = _check("AC7: error is non-empty string",
                 isinstance(snap.error, str) and len(snap.error) > 0, snap.error or "")
    return ok1 and ok2


def test_ac8_lookback_too_small():
    print("\n─── AC8: lookback_days=1 raises ValueError ───")
    from workflows.correlation_snapshot import build_correlation_snapshot
    raised = False
    try:
        build_correlation_snapshot(["SPY","QQQ"], 1)
    except ValueError as e:
        raised = True
        _check("AC8: ValueError raised", True, str(e)[:60])
    if not raised:
        _check("AC8: ValueError raised", False, "no error")
    return raised


def test_ac9_bad_method():
    print("\n─── AC9: method='kentucky' raises ValueError ───")
    from workflows.correlation_snapshot import build_correlation_snapshot
    raised = False
    try:
        build_correlation_snapshot(["SPY","QQQ"], 30, method="kentucky")
    except ValueError as e:
        raised = True
        _check("AC9: ValueError raised", True, str(e)[:60])
    if not raised:
        _check("AC9: ValueError raised", False, "no error")
    return raised


def test_ac10_summarize_imported():
    print("\n─── AC10: summarize_correlations imported, not reimplemented ───")
    content = Path("workflows/correlation_snapshot.py").read_text()
    ok = _check("AC10: summarize_correlations imported from analysis",
                "from analysis.market_analysis import" in content and
                "summarize_correlations" in content)
    return ok


def test_ac11_load_and_calc_imported():
    print("\n─── AC11: load_aligned_returns + calculate_correlation_matrix imported ───")
    content = Path("workflows/correlation_snapshot.py").read_text()
    ok1 = _check("AC11: load_aligned_returns imported", "load_aligned_returns" in content)
    ok2 = _check("AC11: calculate_correlation_matrix imported",
                 "calculate_correlation_matrix" in content)
    return ok1 and ok2


def test_ac12_pairs_sorted():
    print("\n─── AC12: ranked pairs sorted high → low ───")
    from workflows.correlation_snapshot import build_correlation_snapshot
    snap = build_correlation_snapshot(["SPY","QQQ","IWM","TLT"], 30)
    if not snap.ranked_pairs:
        return _check("AC12: pairs exist", False, "no pairs")
    monotone = all(
        snap.ranked_pairs[i].correlation >= snap.ranked_pairs[i+1].correlation
        for i in range(len(snap.ranked_pairs)-1)
    )
    ok = _check("AC12: pairs monotonically non-increasing", monotone,
                str([(p.ticker_a,p.ticker_b,round(p.correlation,3)) for p in snap.ranked_pairs[:3]]))
    return ok


# ── AC13-17: format helpers ───────────────────────────────────────────────────

def test_ac13_correlation_to_color_exported():
    print("\n─── AC13: cockpit/format.py exports correlation_to_color ───")
    from cockpit.format import correlation_to_color
    ok = _check("AC13: correlation_to_color importable", True)
    return ok


def test_ac14_rho_zero():
    print("\n─── AC14: correlation_to_color(0.0) == gradient_neutral ───")
    from cockpit.format import correlation_to_color
    from cockpit.themes import THEMES_CONFIG
    theme = THEMES_CONFIG["claude-warm"]
    result = correlation_to_color(0.0, theme)
    ok = _check("AC14: rho=0 → neutral", result == theme["gradient_neutral"],
                f"{result} vs {theme['gradient_neutral']}")
    return ok


def test_ac15_rho_one():
    print("\n─── AC15: correlation_to_color(1.0) == gradient_positive ───")
    from cockpit.format import correlation_to_color
    from cockpit.themes import THEMES_CONFIG
    theme = THEMES_CONFIG["claude-warm"]
    result = correlation_to_color(1.0, theme)
    ok = _check("AC15: rho=1 → positive", result == theme["gradient_positive"],
                f"{result} vs {theme['gradient_positive']}")
    return ok


def test_ac16_rho_minus_one():
    print("\n─── AC16: correlation_to_color(-1.0) == gradient_negative ───")
    from cockpit.format import correlation_to_color
    from cockpit.themes import THEMES_CONFIG
    theme = THEMES_CONFIG["claude-warm"]
    result = correlation_to_color(-1.0, theme)
    ok = _check("AC16: rho=-1 → negative", result == theme["gradient_negative"],
                f"{result} vs {theme['gradient_negative']}")
    return ok


def test_ac17_rs_color_regression():
    print("\n─── AC17: relative_strength_to_color still works (Session 5 regression) ───")
    from cockpit.format import relative_strength_to_color
    from cockpit.themes import THEMES_CONFIG
    t = THEMES_CONFIG["claude-warm"]
    pos = t["gradient_positive"]; neg = t["gradient_negative"]; neu = t["gradient_neutral"]
    ok1 = _check("AC17: None → neutral", relative_strength_to_color(None, 5.0, pos, neg, neu) == neu)
    ok2 = _check("AC17: 0.05 at max → positive",
                 relative_strength_to_color(0.05, 5.0, pos, neg, neu) == pos)
    ok3 = _check("AC17: -0.05 at max → negative",
                 relative_strength_to_color(-0.05, 5.0, pos, neg, neu) == neg)
    return ok1 and ok2 and ok3


# ── AC18-22: config ───────────────────────────────────────────────────────────

def test_ac18_config_exports():
    print("\n─── AC18: config/settings.py exports CorrelationConfig + DeepDiveConfig ───")
    from config.settings import CorrelationConfig, CorrelationDeepDiveConfig
    ok = _check("AC18: both config classes exported", True)
    return ok


def test_ac19_settings_load():
    print("\n─── AC19: Settings.load() populates both correlation config fields ───")
    from config.settings import Settings
    s = Settings.load()
    ok1 = _check("AC19: correlation_config present",
                 hasattr(s, "correlation_config") and s.correlation_config is not None)
    ok2 = _check("AC19: correlation_deep_dive_config present",
                 hasattr(s, "correlation_deep_dive_config") and s.correlation_deep_dive_config is not None)
    ok3 = _check("AC19: method=pearson", s.correlation_config.method == "pearson")
    ok4 = _check("AC19: 3 presets", len(s.correlation_deep_dive_config.presets) == 3)
    return ok1 and ok2 and ok3 and ok4


def test_ac20_invalid_method():
    print("\n─── AC20: method='invalid' in [correlations] raises ValueError ───")
    from config.settings import Settings
    toml = """
[data]
preferred_source = "yfinance"
data_dir = "data/historical_data"
backtest_results_dir = "data/backtest_results"
[refresh]
interval_seconds = 30
[theme]
default = "claude-warm"
[logging]
level = "INFO"
[correlations]
tickers = ["SPY","QQQ"]
lookback_days = 60
method = "invalid"
refresh_interval_seconds = 300
"""
    raised = False
    with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
        f.write(toml); tmp = Path(f.name)
    try:
        Settings.load(tmp)
    except ValueError as e:
        raised = True
        _check("AC20: ValueError raised", True, str(e)[:60])
    finally:
        tmp.unlink()
    if not raised:
        _check("AC20: ValueError raised", False)
    return raised


def test_ac21_invalid_preset():
    print("\n─── AC21: default_preset='missing' in [correlation_deep_dive] raises ValueError ───")
    from config.settings import Settings
    toml = """
[data]
preferred_source = "yfinance"
data_dir = "data/historical_data"
backtest_results_dir = "data/backtest_results"
[refresh]
interval_seconds = 30
[theme]
default = "claude-warm"
[logging]
level = "INFO"
[correlation_deep_dive]
default_preset = "missing"
default_method = "pearson"
default_lookback_days = 60
lookback_options = [10, 20, 60, 120, 252]
refresh_interval_seconds = 60
[correlation_deep_dive.presets]
cross_asset = ["SPY","QQQ"]
"""
    raised = False
    with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
        f.write(toml); tmp = Path(f.name)
    try:
        Settings.load(tmp)
    except ValueError as e:
        raised = True
        _check("AC21: ValueError raised", True, str(e)[:60])
    finally:
        tmp.unlink()
    if not raised:
        _check("AC21: ValueError raised", False)
    return raised


def test_ac22_toml_sections():
    print("\n─── AC22: cockpit.toml has [correlations] and [correlation_deep_dive] ───")
    content = Path("cockpit.toml").read_text()
    ok1 = _check("AC22: [correlations] section", "[correlations]" in content)
    ok2 = _check("AC22: [correlation_deep_dive] section", "[correlation_deep_dive]" in content)
    return ok1 and ok2


# ── AC23-26: widgets and screen ───────────────────────────────────────────────

def test_ac23_correlation_panel():
    print("\n─── AC23: CorrelationPanel defined ───")
    content = Path("cockpit/widgets/correlation_panel.py").read_text()
    ok = _check("AC23: CorrelationPanel(Widget) defined", "class CorrelationPanel" in content)
    return ok


def test_ac24_correlation_table():
    print("\n─── AC24: CorrelationTable defined ───")
    content = Path("cockpit/widgets/correlation_table.py").read_text()
    ok = _check("AC24: CorrelationTable(Widget) defined", "class CorrelationTable" in content)
    return ok


def test_ac25_ranked_pair_list():
    print("\n─── AC25: RankedPairList defined ───")
    content = Path("cockpit/widgets/ranked_pair_list.py").read_text()
    ok = _check("AC25: RankedPairList(Widget) defined", "class RankedPairList" in content)
    return ok


def test_ac26_screen_bindings():
    print("\n─── AC26: CorrelationDeepDiveScreen has required bindings ───")
    content = Path("cockpit/screens/correlations.py").read_text()
    ok1 = _check("AC26: 'm' binding", '"m"' in content or "'m'" in content)
    ok2 = _check("AC26: '[' binding", '"["' in content or "'['" in content)
    ok3 = _check("AC26: ']' binding", '"]"' in content or "']'" in content)
    ok4 = _check("AC26: 'p' binding", '"p"' in content or "'p'" in content)
    ok5 = _check("AC26: 'r' binding", '"r"' in content or "'r'" in content)
    ok6 = _check("AC26: 'escape' binding", "escape" in content)
    return ok1 and ok2 and ok3 and ok4 and ok5 and ok6


# ── AC27-30: home.py wiring ───────────────────────────────────────────────────

def test_ac27_mock_panels_gone():
    print("\n─── AC27: _refresh_mock_panels deleted from home.py ───")
    content = Path("cockpit/screens/home.py").read_text()
    ok = _check("AC27: _refresh_mock_panels absent", "_refresh_mock_panels" not in content)
    return ok


def test_ac28_c_binding():
    print("\n─── AC28: 'c' binding on HomeScreen ───")
    content = Path("cockpit/screens/home.py").read_text()
    ok = _check("AC28: 'c' binding in home.py", "open_correlation_deep_dive" in content)
    return ok


def test_ac29_correlation_reactive_worker():
    print("\n─── AC29: correlation_snapshot reactive + refresh_correlations worker ───")
    content = Path("cockpit/screens/home.py").read_text()
    ok1 = _check("AC29: correlation_snapshot reactive", "correlation_snapshot" in content)
    ok2 = _check("AC29: refresh_correlations worker", "refresh_correlations" in content)
    return ok1 and ok2


def test_ac30_help_updated():
    print("\n─── AC30: help.py mentions 'c' key and deep-dive bindings ───")
    content = Path("cockpit/screens/help.py").read_text()
    ok1 = _check("AC30: 'c' key in help", "C" in content and "CORRELATION" in content.upper())
    ok2 = _check("AC30: 'm' cycle method in help", "M" in content and "METHOD" in content.upper())
    ok3 = _check("AC30: '[' / ']' lookback in help", "[" in content and "]" in content)
    ok4 = _check("AC30: 'p' preset in help", "P" in content and "PRESET" in content.upper())
    return ok1 and ok2 and ok3 and ok4


# ── AC31: Session 6 regression ────────────────────────────────────────────────

def test_ac31_session6_regression():
    print("\n─── AC31: Session 6 ACs still pass (key checks) ───")
    # Spot-check: sector deep-dive workflow still works
    from config.settings import Settings
    from workflows.multi_timeframe_sector_snapshot import build_multi_timeframe_sector_snapshot
    s = Settings.load()
    ok1 = _check("AC31: sector_deep_dive_config still loads",
                 s.sector_deep_dive_config is not None)
    # Spot-check: 's' binding still on HomeScreen
    home_content = Path("cockpit/screens/home.py").read_text()
    ok2 = _check("AC31: 's' binding still in home.py", "open_sector_deep_dive" in home_content)
    # Spot-check: sector_config.refresh_interval_seconds still used
    ok3 = _check("AC31: sector_config.refresh_interval_seconds in home.py",
                 "sector_config.refresh_interval_seconds" in home_content)
    return ok1 and ok2 and ok3


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Session 7 Verification — Correlation Panel + Deep-Dive")
    print("=" * 60)

    tests = [
        ("AC1",  test_ac1_exports),
        ("AC2",  test_ac2_snapshot_fields),
        ("AC3",  test_ac3_ranked_pair_fields),
        ("AC4",  test_ac4_basic_matrix),
        ("AC5",  test_ac5_method_propagated),
        ("AC6",  test_ac6_bad_ticker_dropped),
        ("AC7",  test_ac7_all_bad_tickers),
        ("AC8",  test_ac8_lookback_too_small),
        ("AC9",  test_ac9_bad_method),
        ("AC10", test_ac10_summarize_imported),
        ("AC11", test_ac11_load_and_calc_imported),
        ("AC12", test_ac12_pairs_sorted),
        ("AC13", test_ac13_correlation_to_color_exported),
        ("AC14", test_ac14_rho_zero),
        ("AC15", test_ac15_rho_one),
        ("AC16", test_ac16_rho_minus_one),
        ("AC17", test_ac17_rs_color_regression),
        ("AC18", test_ac18_config_exports),
        ("AC19", test_ac19_settings_load),
        ("AC20", test_ac20_invalid_method),
        ("AC21", test_ac21_invalid_preset),
        ("AC22", test_ac22_toml_sections),
        ("AC23", test_ac23_correlation_panel),
        ("AC24", test_ac24_correlation_table),
        ("AC25", test_ac25_ranked_pair_list),
        ("AC26", test_ac26_screen_bindings),
        ("AC27", test_ac27_mock_panels_gone),
        ("AC28", test_ac28_c_binding),
        ("AC29", test_ac29_correlation_reactive_worker),
        ("AC30", test_ac30_help_updated),
        ("AC31", test_ac31_session6_regression),
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
    print("  AC32: home correlation panel shows real gradient-colored values")
    print("  AC33: 'c' → deep-dive screen, Esc → home")
    print("  AC34: 'm' cycles Pearson→Spearman→Kendall, matrix values change")
    print("  AC35: ']' increases lookback, '[' decreases, out-of-range is no-op")
    print("  AC36: 'p' cycles ticker presets, matrix dimensions change")
    print("  AC37: ranked pair list updates and is sorted high→low")
    print("  AC38: theme cycle updates colors on next refresh")
    print("  AC39: no panel falls back to mock data")
    print()
    print("Regression checks (manual):")
    print("  AC40: watchlist panel still polls (Session 3)")
    print("  AC41: pulse panel still polls (Session 4)")
    print("  AC42: sector heatmap still polls (Session 5)")
    print("  AC43: sector deep-dive 's' still works (Session 6)")
    print("  AC44: python -m scripts.correlations -t AAPL MSFT NVDA still works")
    print("  AC45: get_data / run_backtest / view_backtest still work")


if __name__ == "__main__":
    main()
