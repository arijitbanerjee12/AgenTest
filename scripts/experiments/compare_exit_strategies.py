"""Compare exit strategies: no target/SL (just EOD close) vs 3 target/SL combos."""
from __future__ import annotations

import importlib
import agentest.utils.indicators.btst as btst

# Use a representative subset for speed
SYMBOLS = btst.BTST_SYMBOLS[:7]  # 7 diverse symbols

# Scenario configs
SCENARIOS = {
    "A: No SL/Target (EOD close)": {
        "exit_timing": "close",
        "target_pct": 99.0,  # never hits
        "stop_pct": 99.0,    # never hits
    },
    "B: Tight 0.5/0.3": {
        "exit_timing": "close",
        "target_pct": 0.5,
        "stop_pct": 0.3,
    },
    "C: Medium 0.8/0.3 (current)": {
        "exit_timing": "close",
        "target_pct": 0.8,
        "stop_pct": 0.3,
    },
    "D: Wide 1.2/0.5": {
        "exit_timing": "close",
        "target_pct": 1.2,
        "stop_pct": 0.5,
    },
}

results = []

for label, cfg in SCENARIOS.items():
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")

    # Set constants
    btst.TARGET_PCT = cfg["target_pct"]
    btst.STOP_LOSS_PCT = cfg["stop_pct"]

    r = btst.run_btst_backtest(SYMBOLS, period="3mo", interval="1h", exit_timing=cfg["exit_timing"])
    o = r["overall"]
    ps = r["per_symbol"]
    sym_wrs = [ps[s]["win_rate"] for s in ps if ps[s]["total_trades"] > 0]

    results.append({
        "label": label,
        "total_trades": o["total_trades"],
        "win_rate": o["win_rate"],
        "avg_pnl": o["avg_pnl_pct"],
        "compound": o["compound_return_pct"],
        "opt_roi": o["option_roi_pct"],
        "max_loss": o["max_loss_pct"],
        "avg_win": o["avg_win_pct"],
        "avg_loss": o["avg_loss_pct"],
        "min_wr": min(sym_wrs) if sym_wrs else 0,
        "max_wr": max(sym_wrs) if sym_wrs else 0,
    })

# Summary table
print(f"\n{'='*80}")
print(f"  COMPARISON SUMMARY")
print(f"{'='*80}")
print(f"\n{'Strategy':<30} {'Trades':>7} {'WR%':>6} {'AvgPnL%':>8} {'Cmpd%':>8} {'OptROI%':>8} {'MaxLoss%':>9} {'AvgWin%':>8} {'AvgLoss%':>8}")
print(f"{'-'*92}")
for r in results:
    print(f"{r['label']:<30} {r['total_trades']:>7} {r['win_rate']:>5.1f}% {r['avg_pnl']:>7.2f}% {r['compound']:>7.2f}% {r['opt_roi']:>7.2f}% {r['max_loss']:>8.2f}% {r['avg_win']:>7.2f}% {r['avg_loss']:>7.2f}%")
