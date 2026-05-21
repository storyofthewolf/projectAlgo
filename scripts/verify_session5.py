"""Session 5 verification script — tests ACs 1-12, 16, 17, 25.

Run from project root:
    python3.14 -m scripts.verify_session5

Interactive ACs (13, 14, 15, 26) require manual terminal verification.
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


def test_ac1_2_snapshot_structure():
    """AC1: 12 cells returned. AC2: SPY cell is RS=0."""
    print("\n─── AC1/AC2: build_sector_snapshot() structure ───")
    from config.settings import SectorConfig
    from workflows.sector_snapshot import build_sector_snapshot, SPDR_SECTORS

    cfg = SectorConfig()
    snap = build_sector_snapshot(cfg)

    ok1 = _check("AC1: snapshot.cells has 12 entries", len(snap.cells) == 12,
                 f"got {len(snap.cells)}")
    ok2 = _check("AC2: cells[0].symbol == 'SPY'", snap.cells[0].symbol == "SPY")
    ok3 = _check("AC2: cells[0].relative_strength == 0.0",
                 snap.cells[0].relative_strength == 0.0,
                 f"got {snap.cells[0].relative_strength}")

    expected_order = ["SPY"] + [s for s, _ in SPDR_SECTORS]
    actual_order = [c.symbol for c in snap.cells]
    ok4 = _check("AC1: cell order matches expected", actual_order == expected_order,
                 f"expected {expected_order}, got {actual_order}")

    return ok1 and ok2 and ok3 and ok4


def test_ac3_sector_values():
    """AC3: Non-SPY cells have float RS and sparkline of correct length."""
    print("\n─── AC3: sector RS values and sparkline lengths ───")
    from config.settings import SectorConfig
    from workflows.sector_snapshot import build_sector_snapshot

    cfg = SectorConfig(lookback_days=20)
    snap = build_sector_snapshot(cfg)

    errors = []
    for cell in snap.cells[1:]:  # skip SPY
        if cell.error:
            continue  # skip errored cells (AC4 handles this)
        if cell.relative_strength is None:
            errors.append(f"{cell.symbol}: RS is None but no error set")
        elif not (-0.5 < cell.relative_strength < 0.5):
            errors.append(f"{cell.symbol}: RS={cell.relative_strength:.4f} out of reasonable range")
        if len(cell.sparkline_values) != cfg.lookback_days:
            errors.append(f"{cell.symbol}: sparkline len={len(cell.sparkline_values)}, want {cfg.lookback_days}")

    ok = _check("AC3: all non-error cells have valid RS and sparkline", len(errors) == 0,
                "; ".join(errors) if errors else "")
    return ok


def test_ac4_bad_sector():
    """AC4: Bad sector ticker → that cell errors; others unaffected."""
    print("\n─── AC4: bad sector ticker handled per-cell ───")
    from config.settings import SectorConfig
    from workflows.sector_snapshot import build_sector_snapshot, SPDR_SECTORS

    # Temporarily inject a bad ticker
    import workflows.sector_snapshot as ss_mod
    original = ss_mod.SPDR_SECTORS[:]
    ss_mod.SPDR_SECTORS = [("XLZZZ", "Bad")] + ss_mod.SPDR_SECTORS[1:]

    try:
        cfg = SectorConfig(lookback_days=20)
        snap = build_sector_snapshot(cfg)
    finally:
        ss_mod.SPDR_SECTORS = original

    ok1 = _check("AC4: snapshot has no panel-level error", snap.error is None,
                 snap.error or "")
    bad_cell = next((c for c in snap.cells if c.symbol == "XLZZZ"), None)
    ok2 = _check("AC4: XLZZZ cell exists", bad_cell is not None)
    ok3 = _check("AC4: XLZZZ cell has error set",
                 bad_cell is not None and bad_cell.error is not None,
                 bad_cell.error if bad_cell else "no cell")
    ok4 = _check("AC4: XLZZZ cell RS is None",
                 bad_cell is not None and bad_cell.relative_strength is None)

    # Verify other cells not affected
    good_cells = [c for c in snap.cells if c.symbol not in ("SPY", "XLZZZ") and not c.error]
    ok5 = _check("AC4: other cells render normally", len(good_cells) >= 5,
                 f"{len(good_cells)} good cells")

    return ok1 and ok2 and ok3 and ok4 and ok5


def test_ac5_bad_benchmark():
    """AC5: Bad benchmark ticker → panel-level error, cells empty."""
    print("\n─── AC5: bad benchmark triggers panel-level error ───")
    from config.settings import SectorConfig
    from workflows.sector_snapshot import build_sector_snapshot

    cfg = SectorConfig(comparison_ticker="ZZSPY", lookback_days=20)
    snap = build_sector_snapshot(cfg)

    ok1 = _check("AC5: snapshot.error is set", snap.error is not None,
                 snap.error or "no error")
    ok2 = _check("AC5: snapshot.cells is empty", len(snap.cells) == 0,
                 f"got {len(snap.cells)} cells")
    return ok1 and ok2


def test_ac6_7_calculate_rs():
    """AC6: calculate_relative_strength returns (float, list). AC7: raises on short data."""
    print("\n─── AC6/AC7: calculate_relative_strength ───")
    import pandas as pd
    import numpy as np
    from analysis.market_analysis import calculate_relative_strength

    n = 30
    lookback = 20
    dates = pd.date_range("2024-01-01", periods=n, freq="B")
    sector_r = pd.Series(np.random.normal(0.001, 0.01, n), index=dates)
    bench_r = pd.Series(np.random.normal(0.001, 0.01, n), index=dates)

    rs_val, rs_path = calculate_relative_strength(sector_r, bench_r, lookback)

    ok1 = _check("AC6: returns float rs_value", isinstance(rs_val, float))
    ok2 = _check("AC6: rs_path has lookback_days length", len(rs_path) == lookback,
                 f"got {len(rs_path)}")
    ok3 = _check("AC6: rs_path[-1] == rs_value",
                 abs(rs_path[-1] - rs_val) < 1e-10,
                 f"path end={rs_path[-1]:.8f}, val={rs_val:.8f}")

    # AC7: insufficient data raises ValueError
    short_s = pd.Series([0.01] * 5)
    short_b = pd.Series([0.01] * 5)
    raised = False
    try:
        calculate_relative_strength(short_s, short_b, lookback)
    except ValueError:
        raised = True
    ok4 = _check("AC7: raises ValueError on insufficient data", raised)

    return ok1 and ok2 and ok3 and ok4


def test_ac8_no_textual_in_workflow():
    """AC8: No Textual/asyncio imports in workflow."""
    print("\n─── AC8: no Textual/asyncio in workflow ───")
    workflow_path = Path("workflows/sector_snapshot.py")
    content = workflow_path.read_text()

    ok1 = _check("AC8: no 'textual' import", "from textual" not in content and "import textual" not in content)
    ok2 = _check("AC8: no 'asyncio' import", "import asyncio" not in content)
    ok3 = _check("AC8: no 'cockpit' import", "from cockpit" not in content and "import cockpit" not in content)
    return ok1 and ok2 and ok3


def test_ac9_no_yfinance_in_workflows_cockpit():
    """AC9: No yfinance/schwab in workflows/ or cockpit/."""
    print("\n─── AC9: no direct yfinance/schwab in workflows/ or cockpit/ ───")
    bad_patterns = ["import yfinance", "import schwab", "yf.Ticker", "schwab_client"]
    errors = []
    for folder in ["workflows", "cockpit"]:
        for py_file in Path(folder).rglob("*.py"):
            text = py_file.read_text()
            for pat in bad_patterns:
                if pat in text:
                    errors.append(f"{py_file}: contains '{pat}'")

    ok = _check("AC9: no direct yfinance/schwab in workflows/ or cockpit/",
                len(errors) == 0, "; ".join(errors) if errors else "")
    return ok


def test_ac10_11_12_settings():
    """AC10: cockpit.toml has [sectors]. AC11: Settings parses it. AC12: missing section → defaults."""
    print("\n─── AC10/AC11/AC12: Settings and cockpit.toml ───")
    from config.settings import Settings, SectorConfig

    # AC10/AC11: load real cockpit.toml
    settings = Settings.load()
    ok1 = _check("AC10/AC11: settings.sector_config is SectorConfig",
                 isinstance(settings.sector_config, SectorConfig))
    ok2 = _check("AC11: lookback_days == 20", settings.sector_config.lookback_days == 20,
                 f"got {settings.sector_config.lookback_days}")
    ok3 = _check("AC11: comparison_ticker == 'SPY'",
                 settings.sector_config.comparison_ticker == "SPY",
                 settings.sector_config.comparison_ticker)
    ok4 = _check("AC11: intensity_max_pct == 5.0",
                 settings.sector_config.intensity_max_pct == 5.0,
                 str(settings.sector_config.intensity_max_pct))
    ok5 = _check("AC11: refresh_interval_seconds == 300",
                 settings.sector_config.refresh_interval_seconds == 300,
                 str(settings.sector_config.refresh_interval_seconds))

    # AC12: minimal TOML without [sectors]
    minimal_toml = """
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
"""
    with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
        f.write(minimal_toml)
        tmp_path = Path(f.name)

    try:
        settings_minimal = Settings.load(tmp_path)
        default_cfg = SectorConfig()
        ok6 = _check("AC12: missing [sectors] → default lookback_days",
                     settings_minimal.sector_config.lookback_days == default_cfg.lookback_days,
                     str(settings_minimal.sector_config.lookback_days))
        ok7 = _check("AC12: missing [sectors] → default comparison_ticker",
                     settings_minimal.sector_config.comparison_ticker == default_cfg.comparison_ticker)
        ok8 = _check("AC12: missing [sectors] → default intensity_max_pct",
                     settings_minimal.sector_config.intensity_max_pct == default_cfg.intensity_max_pct)
    finally:
        tmp_path.unlink()

    return ok1 and ok2 and ok3 and ok4 and ok5 and ok6 and ok7 and ok8


def test_ac16_17_color():
    """AC16: relative_strength_to_color clamps and interpolates. AC17: handles None."""
    print("\n─── AC16/AC17: relative_strength_to_color ───")
    from cockpit.format import relative_strength_to_color

    POS = "#c87a1a"
    NEG = "#8b1a1a"
    NEU = "#1a1a1a"

    # Clamp positive
    result = relative_strength_to_color(0.10, 5.0, POS, NEG, NEU)
    ok1 = _check("AC16: rs=+10% with max=5% → gradient_positive", result == POS,
                 f"got {result}")

    # Clamp negative
    result = relative_strength_to_color(-0.10, 5.0, POS, NEG, NEU)
    ok2 = _check("AC16: rs=-10% with max=5% → gradient_negative", result == NEG,
                 f"got {result}")

    # Midpoint: rs=0.025, max_pct=5.0 → t=0.5 → halfway between NEU and POS
    result = relative_strength_to_color(0.025, 5.0, POS, NEG, NEU)
    # Manually compute expected halfway:
    # NEU = #1a1a1a → (26, 26, 26); POS = #c87a1a → (200, 122, 26)
    # halfway = ((26+200)//2, (26+122)//2, (26+26)//2) = (113, 74, 26)
    expected_r = round(26 + (200 - 26) * 0.5)  # 113
    expected_g = round(26 + (122 - 26) * 0.5)  # 74
    expected_b = round(26 + (26 - 26) * 0.5)   # 26
    expected_mid = f"#{expected_r:02x}{expected_g:02x}{expected_b:02x}"
    ok3 = _check("AC16: rs=+2.5% with max=5% → halfway color",
                 result == expected_mid, f"got {result}, expected {expected_mid}")

    # None → neutral
    result = relative_strength_to_color(None, 5.0, POS, NEG, NEU)
    ok4 = _check("AC17: None → gradient_neutral", result == NEU, f"got {result}")

    # Zero → neutral (not strictly required but good to verify)
    result = relative_strength_to_color(0.0, 5.0, POS, NEG, NEU)
    ok5 = _check("AC16: rs=0.0 → gradient_neutral (t=0, interpolates to neutral)",
                 result == NEU, f"got {result}")

    return ok1 and ok2 and ok3 and ok4 and ok5


def test_ac25_theme_gradient_keys():
    """AC25: Both themes have all three gradient keys."""
    print("\n─── AC25: theme gradient keys present ───")
    from cockpit.themes import THEMES_CONFIG

    required_keys = ["gradient_positive", "gradient_negative", "gradient_neutral"]
    errors = []
    for theme_name, cfg in THEMES_CONFIG.items():
        for key in required_keys:
            if key not in cfg:
                errors.append(f"{theme_name} missing {key}")
            elif not cfg[key].startswith("#"):
                errors.append(f"{theme_name}.{key} not a hex color: {cfg[key]}")

    ok = _check("AC25: both themes have all gradient keys with valid hex", len(errors) == 0,
                "; ".join(errors) if errors else "")
    return ok


def main():
    print("=" * 60)
    print("Session 5 Verification — Sector Heatmap Real-Data Wiring")
    print("=" * 60)

    results = []
    tests = [
        ("AC1/AC2", test_ac1_2_snapshot_structure),
        ("AC3", test_ac3_sector_values),
        ("AC4", test_ac4_bad_sector),
        ("AC5", test_ac5_bad_benchmark),
        ("AC6/AC7", test_ac6_7_calculate_rs),
        ("AC8", test_ac8_no_textual_in_workflow),
        ("AC9", test_ac9_no_yfinance_in_workflows_cockpit),
        ("AC10/AC11/AC12", test_ac10_11_12_settings),
        ("AC16/AC17", test_ac16_17_color),
        ("AC25", test_ac25_theme_gradient_keys),
    ]

    for name, fn in tests:
        try:
            passed = fn()
            results.append((name, passed))
        except Exception as e:
            print(f"  [ERROR] {name}: {e}")
            import traceback
            traceback.print_exc()
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
    print("  AC13: cockpit launches with 12 populated sector cells")
    print("  AC14: each cell shows symbol, label, RS%, sparkline")
    print("  AC15: cell backgrounds vary by relative strength")
    print("  AC26: theme cycling updates sector gradient colors")


if __name__ == "__main__":
    main()
