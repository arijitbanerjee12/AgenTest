"""Compare exit strategies — per-symbol breakdown."""
from __future__ import annotations

import agentest.utils.indicators.btst as btst

# Add HDFCBANK and NIFTY (user requested)
SYMBOLS = btst.BTST_SYMBOLS + [
    {"name": "HDFCBANK", "symbol": "HDFCBANK.NS", "category": "large_cap", "sector": "Banking"},
    {"name": "NIFTY",    "symbol": "^NSEI",       "category": "index",      "sector": "Index"},
]

SCENARIOS = {
    "A: No SL/Target (EOD close)": {"exit_timing": "close", "target_pct": 99.0, "stop_pct": 99.0},
    "B: Tight 0.5/0.3":            {"exit_timing": "close", "target_pct": 0.5,  "stop_pct": 0.3},
    "C: Medium 0.8/0.3 (current)": {"exit_timing": "close", "target_pct": 0.8,  "stop_pct": 0.3},
    "D: Wide 1.2/0.5":             {"exit_timing": "close", "target_pct": 1.2,  "stop_pct": 0.5},
}

all_data = {}

for label, cfg in SCENARIOS.items():
    btst.TARGET_PCT = cfg["target_pct"]
    btst.STOP_LOSS_PCT = cfg["stop_pct"]
    r = btst.run_btst_backtest(SYMBOLS, period="3mo", interval="1h", exit_timing=cfg["exit_timing"])
    all_data[label] = r["per_symbol"]

# Print per-symbol table for each scenario
for label in SCENARIOS:
    ps = all_data[label]
    print(f"\n{'='*80}")
    print(f"  {label}")
    print(f"{'='*80}")
    print(f"  {'Symbol':<16} {'Trades':>6} {'WR%':>6} {'AvgPnL%':>8} {'Cmpd%':>8} {'AvgWin%':>8} {'AvgLoss%':>8} {'MaxLoss%':>8}")
    print(f"  {'-'*70}")
    for sym in sorted(ps.keys()):
        s = ps[sym]
        if s["total_trades"] > 0:
            print(f"  {sym:<16} {s['total_trades']:>6} {s['win_rate']:>5.1f}% {s['avg_pnl_pct']:>7.2f}% {s['compound_return_pct']:>7.2f}% {s['avg_win_pct']:>7.2f}% {s['avg_loss_pct']:>7.2f}% {s['max_loss_pct']:>7.2f}%")
