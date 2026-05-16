"""Mock data for cockpit visual development.

DELETE THIS FILE IN SESSION 3 once real data is wired.
"""
import random

WATCHLIST_TICKERS = ["AAPL", "MSFT", "NVDA", "ISRG", "GOOGL"]

# (ticker, last, change, change_pct, volume, change_5d_pct, change_30d_pct, sparkline_values, rsi)
WATCHLIST_HOLDINGS: list[tuple] = [
    ("AAPL",   187.42, +1.23, +0.66, 42_100_000, +2.1, +5.4,  [1, 2, 3, 5, 6], 58),
    ("MSFT",   412.18, +3.81, +0.93, 28_400_000, +1.8, +7.2,  [2, 3, 4, 5, 6], 62),
    ("NVDA",   132.91, -2.14, -1.58, 98_200_000, -4.3, +12.1, [6, 5, 4, 3, 2], 47),
    ("ISRG",   487.55, +0.21, +0.04,  1_200_000, +0.8, +3.1,  [4, 5, 5, 4, 5], 52),
    ("GOOGL",  178.92, +2.41, +1.37, 18_700_000, +3.2, +8.9,  [2, 3, 4, 5, 7], 64),
]

# (ticker, last, change_pct, sparkline_values, format_hint)
MARKET_PULSE: list[tuple] = [
    ("SPY",  582.43, +0.42, [1, 2, 3, 5, 6, 7, 6, 5, 6, 7], "price"),
    ("QQQ",  512.18, +0.61, [1, 2, 4, 6, 7, 7, 6, 7, 7, 7], "price"),
    ("IWM",  228.41, -0.18, [7, 6, 5, 4, 3, 2, 3, 3, 2, 1], "price"),
    ("VIX",   14.20, -2.10, [7, 6, 5, 4, 3, 3, 4, 3, 2, 2], "price"),
    ("10Y",    4.18, +0.48, [2, 3, 4, 4, 5, 6, 6, 7, 7, 7], "yield"),
    ("DXY",  103.42, +0.05, [5, 5, 6, 5, 5, 6, 5, 5, 6, 5], "price"),
]

# (etf, name, change_pct)
SECTORS: list[tuple] = [
    ("XLK",  "TECH",       +0.82),
    ("XLC",  "COMM",       +0.61),
    ("XLY",  "CONS.DISC",  +0.43),
    ("XLF",  "FINANC.",    +0.21),
    ("XLI",  "INDUST.",    +0.12),
    ("XLP",  "CONS.STAP",  -0.08),
    ("XLU",  "UTILITIES",  -0.31),
    ("XLE",  "ENERGY",     -0.82),
    ("XLV",  "HEALTH",     -0.41),
    ("XLB",  "MATERIALS",  -0.18),
    ("XLRE", "REAL EST",   -0.71),
]

# (ticker, [row of correlation values matching WATCHLIST_TICKERS order])
CORRELATIONS: list[tuple] = [
    ("AAPL",  [1.00, 0.72, 0.51, 0.18, 0.68]),
    ("MSFT",  [0.72, 1.00, 0.68, 0.22, 0.81]),
    ("NVDA",  [0.51, 0.68, 1.00, 0.15, 0.59]),
    ("ISRG",  [0.18, 0.22, 0.15, 1.00, 0.21]),
    ("GOOGL", [0.68, 0.81, 0.59, 0.21, 1.00]),
]


def regenerate_mock() -> dict:
    """Return fresh mock data with small random perturbations.

    Called by the home screen on `r` press to demonstrate the flash mechanism.
    Each price is perturbed by ±0.5%, change_pct is recomputed.
    """
    new_holdings = []
    for ticker, last, chg, chg_pct, vol, c5d, c30d, spark, rsi in WATCHLIST_HOLDINGS:
        delta_pct = random.uniform(-0.005, 0.005)
        new_last = round(last * (1 + delta_pct), 2)
        new_chg = round(new_last - last, 2)
        new_chg_pct = round(delta_pct * 100, 2)
        new_rsi = max(0, min(100, rsi + random.randint(-3, 3)))
        new_spark = spark[1:] + [random.randint(1, 8)]
        new_holdings.append(
            (ticker, new_last, new_chg, new_chg_pct, vol, c5d, c30d, new_spark, new_rsi)
        )

    new_pulse = []
    for ticker, last, chg_pct, spark, fmt in MARKET_PULSE:
        delta = random.uniform(-0.003, 0.003)
        new_last = round(last * (1 + delta), 2)
        new_chg_pct = round(delta * 100, 2)
        new_spark = spark[1:] + [random.randint(1, 8)]
        new_pulse.append((ticker, new_last, new_chg_pct, new_spark, fmt))

    return {
        "holdings": new_holdings,
        "pulse":    new_pulse,
        "sectors":  SECTORS,
        "corr":     CORRELATIONS,
    }
