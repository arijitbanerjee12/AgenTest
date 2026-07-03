"""Select top 10 BTST symbols by win rate × avg PnL across strategies."""
from __future__ import annotations

import agentest.utils.indicators.btst as btst

SYMBOLS = btst.BTST_SYMBOLS + [
    {"name": "HDFCBANK", "symbol": "HDFCBANK.NS", "category": "large_cap", "sector": "Banking"},
    {"name": "NIFTY",    "symbol": "^NSEI",       "category": "index",      "sector": "Index"},
]

SCENARIOS = {
    "NoSL":   {"exit_timing": "close", "target_pct": 99.0, "stop_pct": 99.0},
    "Tight":  {"exit_timing": "close", "target_pct": 0.5,  "stop_pct": 0.3},
    "Medium": {"exit_timing": "close", "target_pct": 0.8,  "stop_pct": 0.3},
    "Wide":   {"exit_timing": "close", "target_pct": 1.2,  "stop_pct": 0.5},
}

# Collect per-symbol results across all strategies
from collections import defaultdict
symbol_scores = defaultdict(list)

for label, cfg in SCENARIOS.items():
    btst.TARGET_PCT = cfg["target_pct"]
    btst.STOP_LOSS_PCT = cfg["stop_pct"]
    r = btst.run_btst_backtest(SYMBOLS, period="3mo", interval="1h", exit_timing=cfg["exit_timing"])
    for sym, s in r["per_symbol"].items():
        if s["total_trades"] >= 20:
            # Score: expected value per trade = WR × avg_win + (1-WR) × avg_loss
            wr = s["win_rate"] / 100
            ev = wr * s["avg_win_pct"] + (1 - wr) * s["avg_loss_pct"]
            symbol_scores[sym].append({
                "scenario": label,
                "wr": s["win_rate"],
                "avg_pnl": s["avg_pnl_pct"],
                "compound": s["compound_return_pct"],
                "ev": round(ev, 3),
            })

# For each symbol, compute average EV across scenarios
avg_scores = []
for sym, scores in symbol_scores.items():
    avg_ev = sum(s["ev"] for s in scores) / len(scores)
    avg_wr = sum(s["wr"] for s in scores) / len(scores)
    avg_pnl = sum(s["avg_pnl"] for s in scores) / len(scores)
    medium = next((s for s in scores if s["scenario"] == "Medium"), None)
    avg_scores.append({
        "symbol": sym,
        "avg_ev": avg_ev,
        "avg_wr": avg_wr,
        "avg_pnl": avg_pnl,
        "medium_compound": medium["compound"] if medium else 0,
    })

# Sort by average EV descending
avg_scores.sort(key=lambda x: x["avg_ev"], reverse=True)

print(f"\n{'='*80}")
print(f"  TOP 10 BTST SYMBOLS (ranked by expected value across all strategies)")
print(f"{'='*80}")
print(f"\n  {'Rank':<5} {'Symbol':<16} {'Avg EV%':>8} {'Avg WR%':>8} {'Avg PnL%':>9} {'Med Cmpd%':>10}")
print(f"  {'-'*52}")
for i, s in enumerate(avg_scores[:10], 1):
    print(f"  #{i:<3} {s['symbol']:<16} {s['avg_ev']:>7.3f}% {s['avg_wr']:>7.1f}% {s['avg_pnl']:>8.2f}% {s['medium_compound']:>9.2f}%")

# Also show the rest
print(f"\n  Rest of the pack:")
print(f"  {'Symbol':<16} {'Avg EV%':>8} {'Avg WR%':>8} {'Avg PnL%':>9}")
print(f"  {'-'*42}")
for s in avg_scores[10:]:
    print(f"  {s['symbol']:<16} {s['avg_ev']:>7.3f}% {s['avg_wr']:>7.1f}% {s['avg_pnl']:>8.2f}%")

# Full per-symbol detail
print(f"\n{'='*80}")
print(f"  PER-SYMBOL BREAKDOWN ACROSS ALL STRATEGIES")
print(f"{'='*80}")
for s in avg_scores:
    print(f"\n  {s['symbol']}")
    print(f"  {'Strategy':<10} {'WR%':>6} {'AvgPnL%':>8} {'Cmpd%':>8} {'EV%':>8}")
    print(f"  {'-'*40}")
    for sc in symbol_scores[s['symbol']]:
        print(f"  {sc['scenario']:<10} {sc['wr']:>5.1f}% {sc['avg_pnl']:>7.2f}% {sc['compound']:>7.2f}% {sc['ev']:>7.3f}%")
