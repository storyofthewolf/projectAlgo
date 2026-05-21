"""Session 6 verification script — tests ACs 1-28 where automatable.

Run from project root:
    python3.14 -m scripts.verify_session6

Interactive ACs (29-39) require manual terminal verification.
Regression ACs (40-41) are noted separately.
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


# ── Configuration ACs (1-10) ──────────────────────────────────────────────

def test_ac1_defaults():
    """AC1: No [sector_deep_dive] → correct defaults."""
    print("\n─── AC1: default SectorDeepDiveConfig ───")
    from config.settings import Settings, SectorDeepDiveConfig

    minimal = """
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
        f.write(minimal)
        tmp = Path(f.name)
    try:
        s = Settings.load(tmp)
        cfg = s.sector_deep_dive_config
        ok1 = _check("AC1: refresh=60s", cfg.refresh_interval_seconds == 60,
                     str(cfg.refresh_interval_seconds))
        ok2 = _check("AC1: sort_column='1M'", cfg.default_sort_column == "1M",
                     cfg.default_sort_column)
        ok3 = _check("AC1: sort_direction='desc'", cfg.default_sort_direction == "desc",
                     cfg.default_sort_direction)
        ok4 = _check("AC1: 4 timeframes", len(cfg.timeframes) == 4,
                     str(len(cfg.timeframes)))
        labels = [tf.label for tf in cfg.timeframes]
        ok5 = _check("AC1: timeframe labels are 5D/1M/3M/YTD",
                     labels == ["5D", "1M", "3M", "YTD"], str(labels))
        return ok1 and ok2 and ok3 and ok4 and ok5
    finally:
        tmp.unlink()


def test_ac2_full_parse():
    """AC2: Full [sector_deep_dive] section parses correctly."""
    print("\n─── AC2: full sector_deep_dive parse ───")
    from config.settings import Settings

    s = Settings.load()
    cfg = s.sector_deep_dive_config
    ok1 = _check("AC2: refresh_interval_seconds == 60", cfg.refresh_interval_seconds == 60)
    ok2 = _check("AC2: default_sort_column == '1M'", cfg.default_sort_column == "1M")
    ok3 = _check("AC2: default_sort_direction == 'desc'", cfg.default_sort_direction == "desc")
    ok4 = _check("AC2: 4 timeframes", len(cfg.timeframes) == 4)
    return ok1 and ok2 and ok3 and ok4


def _load_with_toml(toml_str: str):
    from config.settings import Settings
    with tempfile.NamedTemporaryFile(suffix=".toml", mode="w", delete=False) as f:
        f.write(toml_str)
        tmp = Path(f.name)
    try:
        return Settings.load(tmp)
    finally:
        tmp.unlink()


_BASE_TOML = """
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


def _expect_valueerror(label: str, toml_extra: str) -> bool:
    raised = False
    try:
        _load_with_toml(_BASE_TOML + toml_extra)
    except ValueError as e:
        raised = True
        _check(label, True, str(e)[:80])
    if not raised:
        _check(label, False, "no ValueError raised")
    return raised


def test_ac3_empty_timeframes():
    """AC3: timeframes=[] raises ValueError."""
    print("\n─── AC3: empty timeframes → ValueError ───")
    return _expect_valueerror(
        "AC3: timeframes=[] raises ValueError",
        '[sector_deep_dive]\nrefresh_interval_seconds = 60\ndefault_sort_column = "5D"\n'
        'timeframes = []\n',
    )


def test_ac4_both_fields():
    """AC4: trading_days AND calendar both set → ValueError."""
    print("\n─── AC4: both trading_days+calendar → ValueError ───")
    return _expect_valueerror(
        "AC4: both fields raises ValueError",
        '[sector_deep_dive]\ndefault_sort_column = "5D"\n'
        'timeframes = [{ label="5D", trading_days=5, calendar="ytd" }, '
        '{ label="1M", trading_days=21 }]\n',
    )


def test_ac5_neither_field():
    """AC5: neither trading_days nor calendar → ValueError."""
    print("\n─── AC5: neither field → ValueError ───")
    return _expect_valueerror(
        "AC5: neither field raises ValueError",
        '[sector_deep_dive]\ndefault_sort_column = "5D"\n'
        'timeframes = [{ label="5D" }, { label="1M", trading_days=21 }]\n',
    )


def test_ac6_bad_calendar():
    """AC6: calendar='qtd' raises ValueError."""
    print("\n─── AC6: calendar='qtd' → ValueError ───")
    return _expect_valueerror(
        "AC6: calendar='qtd' raises ValueError",
        '[sector_deep_dive]\ndefault_sort_column = "5D"\n'
        'timeframes = [{ label="5D", trading_days=5 }, '
        '{ label="QTD", calendar="qtd" }]\n',
    )


def test_ac7_duplicate_labels():
    """AC7: duplicate labels raise ValueError."""
    print("\n─── AC7: duplicate labels → ValueError ───")
    return _expect_valueerror(
        "AC7: duplicate labels raises ValueError",
        '[sector_deep_dive]\ndefault_sort_column = "1M"\n'
        'timeframes = [{ label="1M", trading_days=21 }, { label="1M", trading_days=63 }]\n',
    )


def test_ac8_bad_sort_column():
    """AC8: default_sort_column not in labels raises ValueError."""
    print("\n─── AC8: sort column not in labels → ValueError ───")
    return _expect_valueerror(
        "AC8: bad sort column raises ValueError",
        '[sector_deep_dive]\ndefault_sort_column = "5Y"\n'
        'timeframes = [{ label="5D", trading_days=5 }, { label="1M", trading_days=21 }]\n',
    )


def test_ac9_bad_sort_direction():
    """AC9: sort_direction='sideways' raises ValueError."""
    print("\n─── AC9: bad sort_direction → ValueError ───")
    return _expect_valueerror(
        "AC9: sort_direction='sideways' raises ValueError",
        '[sector_deep_dive]\ndefault_sort_column = "5D"\ndefault_sort_direction = "sideways"\n'
        'timeframes = [{ label="5D", trading_days=5 }, { label="1M", trading_days=21 }]\n',
    )


def test_ac10_too_many_timeframes():
    """AC10: 7 timeframes raises ValueError."""
    print("\n─── AC10: 7 timeframes → ValueError ───")
    tfs = ", ".join(
        f'{{ label="{i}D", trading_days={i*5} }}' for i in range(1, 8)
    )
    return _expect_valueerror(
        "AC10: 7 timeframes raises ValueError",
        f'[sector_deep_dive]\ndefault_sort_column = "5D"\ntimeframes = [{tfs}]\n',
    )


# ── Workflow ACs (11-19) ──────────────────────────────────────────────────

def _build_snap():
    from config.settings import Settings
    from workflows.multi_timeframe_sector_snapshot import build_multi_timeframe_sector_snapshot
    s = Settings.load()
    return build_multi_timeframe_sector_snapshot(
        timeframes=s.sector_deep_dive_config.timeframes,
        sector_config=s.sector_config,
    )


def test_ac11_row_count():
    """AC11: 12 rows (SPY + 11 sectors)."""
    print("\n─── AC11: snapshot has 12 rows ───")
    snap = _build_snap()
    ok = _check("AC11: len(rows) == 12", len(snap.rows) == 12, str(len(snap.rows)))
    return ok


def test_ac12_spy_row():
    """AC12: First row is SPY with is_benchmark=True and all rs_value==0.0."""
    print("\n─── AC12: SPY pin row ───")
    snap = _build_snap()
    spy = snap.rows[0]
    ok1 = _check("AC12: rows[0].symbol == 'SPY'", spy.symbol == "SPY")
    ok2 = _check("AC12: rows[0].is_benchmark == True", spy.is_benchmark is True)
    all_zero = all(tf.rs_value == 0.0 for tf in spy.timeframes)
    ok3 = _check("AC12: all SPY rs_value == 0.0", all_zero)
    return ok1 and ok2 and ok3


def test_ac13_sector_values():
    """AC13: Non-SPY rows have is_benchmark=False and at least one non-None rs_value."""
    print("\n─── AC13: sector rows have real RS values ───")
    snap = _build_snap()
    bad = []
    for row in snap.rows[1:]:
        if row.is_benchmark:
            bad.append(f"{row.symbol}: is_benchmark=True")
            continue
        if row.error:
            continue
        has_value = any(tf.rs_value is not None for tf in row.timeframes)
        if not has_value:
            bad.append(f"{row.symbol}: all rs_value=None")
    ok = _check("AC13: sector rows have values", len(bad) == 0, "; ".join(bad))
    return ok


def test_ac14_timeframe_labels():
    """AC14: timeframe_labels matches configured labels in order."""
    print("\n─── AC14: timeframe_labels order ───")
    from config.settings import Settings
    s = Settings.load()
    expected = tuple(tf.label for tf in s.sector_deep_dive_config.timeframes)
    snap = _build_snap()
    ok = _check("AC14: timeframe_labels match config",
                snap.timeframe_labels == expected,
                f"expected {expected}, got {snap.timeframe_labels}")
    return ok


def test_ac15_bad_sector():
    """AC15: Bad sector → that row errors; others render."""
    print("\n─── AC15: bad sector ticker per-row error ───")
    from config.settings import Settings
    import workflows.sector_snapshot as ss
    import workflows.multi_timeframe_sector_snapshot as mtf
    from workflows.multi_timeframe_sector_snapshot import build_multi_timeframe_sector_snapshot
    original_ss = ss.SPDR_SECTORS[:]
    original_mtf = mtf.SPDR_SECTORS[:]
    patched = [("XLZZZ", "Bogus")] + ss.SPDR_SECTORS[1:]
    ss.SPDR_SECTORS = patched
    mtf.SPDR_SECTORS = patched
    try:
        s = Settings.load()
        snap = build_multi_timeframe_sector_snapshot(
            timeframes=s.sector_deep_dive_config.timeframes,
            sector_config=s.sector_config,
        )
    finally:
        ss.SPDR_SECTORS = original_ss
        mtf.SPDR_SECTORS = original_mtf

    ok1 = _check("AC15: no panel-level error", snap.error is None)
    bad_row = next((r for r in snap.rows if r.symbol == "XLZZZ"), None)
    ok2 = _check("AC15: XLZZZ row exists", bad_row is not None)
    ok3 = _check("AC15: XLZZZ row has error", bad_row is not None and bad_row.error is not None)
    good_rows = [r for r in snap.rows if r.symbol not in ("SPY", "XLZZZ") and not r.error]
    ok4 = _check("AC15: other rows render", len(good_rows) >= 5, f"{len(good_rows)} good rows")
    return ok1 and ok2 and ok3 and ok4


def test_ac16_bad_benchmark():
    """AC16: Bad benchmark → snapshot-level error, rows=()."""
    print("\n─── AC16: bad benchmark → panel-level error ───")
    from config.settings import Settings, SectorConfig
    from workflows.multi_timeframe_sector_snapshot import build_multi_timeframe_sector_snapshot
    s = Settings.load()
    bad_sector_cfg = SectorConfig(
        comparison_ticker="ZZSPY",
        lookback_days=s.sector_config.lookback_days,
        intensity_max_pct=s.sector_config.intensity_max_pct,
        refresh_interval_seconds=s.sector_config.refresh_interval_seconds,
    )
    snap = build_multi_timeframe_sector_snapshot(
        timeframes=s.sector_deep_dive_config.timeframes,
        sector_config=bad_sector_cfg,
    )
    ok1 = _check("AC16: snapshot.error is set", snap.error is not None, snap.error or "")
    ok2 = _check("AC16: rows == ()", snap.rows == (), f"got {len(snap.rows)} rows")
    return ok1 and ok2


def test_ac17_ytd_slice():
    """AC17: YTD timeframe has ~95 trading days in May 2026."""
    print("\n─── AC17: YTD slice length ───")
    from config.settings import Settings
    from workflows.multi_timeframe_sector_snapshot import build_multi_timeframe_sector_snapshot
    s = Settings.load()
    snap = build_multi_timeframe_sector_snapshot(
        timeframes=s.sector_deep_dive_config.timeframes,
        sector_config=s.sector_config,
    )
    # Find a non-error sector row
    sector = next((r for r in snap.rows if not r.is_benchmark and not r.error), None)
    if sector is None:
        _check("AC17: YTD path length", False, "no non-error sector found")
        return False
    ytd_tf = next((tf for tf in sector.timeframes if tf.label == "YTD"), None)
    if ytd_tf is None:
        _check("AC17: YTD timeframe present", False, "no YTD label found")
        return False
    # In May 2026, YTD should be ~95 trading days; allow 60-130 range
    n = len(ytd_tf.rs_path)
    ok = _check("AC17: YTD path length ~95 (60-130)", 60 <= n <= 130,
                f"got {n} trading days")
    return ok


def test_ac18_trading_days_slice():
    """AC18: trading_days=21 produces rs_path of length 21."""
    print("\n─── AC18: trading_days slice length ───")
    from config.settings import Settings
    from workflows.multi_timeframe_sector_snapshot import build_multi_timeframe_sector_snapshot
    s = Settings.load()
    snap = build_multi_timeframe_sector_snapshot(
        timeframes=s.sector_deep_dive_config.timeframes,
        sector_config=s.sector_config,
    )
    sector = next((r for r in snap.rows if not r.is_benchmark and not r.error), None)
    if sector is None:
        _check("AC18: trading_days path length", False, "no non-error sector")
        return False
    one_m = next((tf for tf in sector.timeframes if tf.label == "1M"), None)
    if one_m is None:
        _check("AC18: 1M timeframe", False, "no 1M label")
        return False
    ok = _check("AC18: 1M rs_path length == 21", len(one_m.rs_path) == 21,
                f"got {len(one_m.rs_path)}")
    return ok


def test_ac19_insufficient_data():
    """AC19: Timeframe with insufficient data → rs_value=None; others still compute."""
    print("\n─── AC19: insufficient-data timeframe → rs_value=None ───")
    from config.settings import Settings, Timeframe, SectorDeepDiveConfig
    from workflows.multi_timeframe_sector_snapshot import build_multi_timeframe_sector_snapshot

    s = Settings.load()
    # Add a huge 1000-day timeframe that won't have enough data
    big_tf = Timeframe(label="HUGE", trading_days=1000)
    tfs_with_big = (*s.sector_deep_dive_config.timeframes, big_tf)

    snap = build_multi_timeframe_sector_snapshot(
        timeframes=tfs_with_big,
        sector_config=s.sector_config,
    )

    sector = next((r for r in snap.rows if not r.is_benchmark and not r.error), None)
    if sector is None:
        _check("AC19: sector row exists", False, "no non-error sector")
        return False

    huge_tf = next((tf for tf in sector.timeframes if tf.label == "HUGE"), None)
    ok1 = _check("AC19: HUGE timeframe has rs_value=None",
                 huge_tf is not None and huge_tf.rs_value is None,
                 str(huge_tf.rs_value if huge_tf else "not found"))

    # Other timeframes for same sector should still have values
    other_tfs = [tf for tf in sector.timeframes if tf.label != "HUGE" and tf.rs_value is not None]
    ok2 = _check("AC19: other timeframes still compute", len(other_tfs) >= 2,
                 f"{len(other_tfs)} timeframes with values")
    return ok1 and ok2


# ── Architectural ACs (20-24) ─────────────────────────────────────────────

def test_ac20_no_textual_asyncio_in_workflow():
    """AC20: workflow has no Textual/asyncio imports."""
    print("\n─── AC20: no textual/asyncio in workflow ───")
    path = Path("workflows/multi_timeframe_sector_snapshot.py")
    content = path.read_text()
    ok1 = _check("AC20: no 'from textual'", "from textual" not in content)
    ok2 = _check("AC20: no 'import asyncio'", "import asyncio" not in content)
    return ok1 and ok2


def test_ac21_no_yfinance_schwab_in_workflow():
    """AC21: workflow has no direct yfinance/schwab imports."""
    print("\n─── AC21: no yfinance/schwab in workflow ───")
    path = Path("workflows/multi_timeframe_sector_snapshot.py")
    content = path.read_text()
    ok1 = _check("AC21: no 'import yfinance'", "import yfinance" not in content)
    ok2 = _check("AC21: no 'import schwab'", "import schwab" not in content)
    return ok1 and ok2


def test_ac22_sectors_screen_no_marketdata():
    """AC22: sectors.py does not import from marketdata/."""
    print("\n─── AC22: sectors.py no marketdata import ───")
    content = Path("cockpit/screens/sectors.py").read_text()
    ok1 = _check("AC22: no 'from marketdata'", "from marketdata" not in content)
    ok2 = _check("AC22: no 'import marketdata'", "import marketdata" not in content)
    return ok1 and ok2


def test_ac23_sector_table_no_workflows_marketdata():
    """AC23: sector_table.py does not import from workflows/ or marketdata/."""
    print("\n─── AC23: sector_table.py no workflow/marketdata imports ───")
    content = Path("cockpit/widgets/sector_table.py").read_text()
    ok1 = _check("AC23: no 'from workflows'", "from workflows" not in content)
    ok2 = _check("AC23: no 'from marketdata'", "from marketdata" not in content)
    return ok1 and ok2


def test_ac24_spdr_sectors_reused():
    """AC24: multi_timeframe workflow imports SPDR_SECTORS from sector_snapshot."""
    print("\n─── AC24: SPDR_SECTORS reused from sector_snapshot ───")
    content = Path("workflows/multi_timeframe_sector_snapshot.py").read_text()
    ok = _check("AC24: imports SPDR_SECTORS from workflows.sector_snapshot",
                "from workflows.sector_snapshot import SPDR_SECTORS" in content)
    return ok


# ── Screen wiring ACs (25-28) ─────────────────────────────────────────────

def test_ac25_s_binding():
    """AC25: 's' is bound on HomeScreen."""
    print("\n─── AC25: 's' binding on HomeScreen ───")
    from cockpit.screens.home import HomeScreen
    bindings = [str(b.key) for b in HomeScreen.BINDINGS]
    ok = _check("AC25: 's' in HomeScreen.BINDINGS", "s" in bindings, str(bindings))
    return ok


def test_ac26_esc_binding():
    """AC26: 'escape' bound on SectorDeepDiveScreen."""
    print("\n─── AC26: 'escape' binding on SectorDeepDiveScreen ───")
    from cockpit.screens.sectors import SectorDeepDiveScreen
    binding_keys = [str(b.key) for b in SectorDeepDiveScreen.BINDINGS]
    ok = _check("AC26: 'escape' in SectorDeepDiveScreen.BINDINGS",
                "escape" in binding_keys, str(binding_keys))
    return ok


def test_ac27_home_sector_interval():
    """AC27: HomeScreen still has sector 5-min interval (Session 5 unchanged)."""
    print("\n─── AC27: HomeScreen sector interval from Session 5 intact ───")
    content = Path("cockpit/screens/home.py").read_text()
    ok = _check("AC27: sector_config.refresh_interval_seconds in home.py",
                "sector_config.refresh_interval_seconds" in content)
    return ok


def test_ac28_deep_dive_interval():
    """AC28: SectorDeepDiveScreen uses sector_deep_dive_config.refresh_interval_seconds."""
    print("\n─── AC28: deep-dive uses its own refresh_interval_seconds ───")
    content = Path("cockpit/screens/sectors.py").read_text()
    ok = _check("AC28: sector_deep_dive_config.refresh_interval_seconds in sectors.py",
                "sector_deep_dive_config.refresh_interval_seconds" in content)
    return ok


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Session 6 Verification — Sector Deep-Dive Screen")
    print("=" * 60)

    tests = [
        ("AC1",  test_ac1_defaults),
        ("AC2",  test_ac2_full_parse),
        ("AC3",  test_ac3_empty_timeframes),
        ("AC4",  test_ac4_both_fields),
        ("AC5",  test_ac5_neither_field),
        ("AC6",  test_ac6_bad_calendar),
        ("AC7",  test_ac7_duplicate_labels),
        ("AC8",  test_ac8_bad_sort_column),
        ("AC9",  test_ac9_bad_sort_direction),
        ("AC10", test_ac10_too_many_timeframes),
        ("AC11", test_ac11_row_count),
        ("AC12", test_ac12_spy_row),
        ("AC13", test_ac13_sector_values),
        ("AC14", test_ac14_timeframe_labels),
        ("AC15", test_ac15_bad_sector),
        ("AC16", test_ac16_bad_benchmark),
        ("AC17", test_ac17_ytd_slice),
        ("AC18", test_ac18_trading_days_slice),
        ("AC19", test_ac19_insufficient_data),
        ("AC20", test_ac20_no_textual_asyncio_in_workflow),
        ("AC21", test_ac21_no_yfinance_schwab_in_workflow),
        ("AC22", test_ac22_sectors_screen_no_marketdata),
        ("AC23", test_ac23_sector_table_no_workflows_marketdata),
        ("AC24", test_ac24_spdr_sectors_reused),
        ("AC25", test_ac25_s_binding),
        ("AC26", test_ac26_esc_binding),
        ("AC27", test_ac27_home_sector_interval),
        ("AC28", test_ac28_deep_dive_interval),
    ]

    results = []
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
    print("  AC29: 's' transitions to deep-dive screen within ~1s")
    print("  AC30: 12 rows appear within ~10s of entry")
    print("  AC31: arrow keys move column focus without changing sort")
    print("  AC32: Enter on non-sorted column sorts desc, reorders rows")
    print("  AC33: Enter on sorted column toggles ▼↔▲ arrow in header")
    print("  AC34: sparkline column follows currently-sorted timeframe")
    print("  AC35: SPY row stays pinned at top regardless of sort")
    print("  AC36: cell backgrounds shift by RS magnitude")
    print("  AC37: 'r' or 60s interval updates header timestamp")
    print("  AC38: Esc returns to home with previous state intact")
    print("  AC39: theme cycle updates colors on next refresh")
    print()
    print("Regression checks (manual):")
    print("  AC40: home SectorPanel from Session 5 still renders")
    print("  AC41: get_data / run_backtest / correlations scripts still work")


if __name__ == "__main__":
    main()
