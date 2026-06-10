"""BTST Backtest Runner — compare exit at open vs close on best symbols."""
from agentest.utils.indicators.btst import run_btst_backtest, compare_exit_strategies, generate_btst_report, BTST_SYMBOLS

print("=" * 70)
print("  BTST Backtest — Best 7 Symbols (hourly, EMA 10/20 + HA)")
print("  Exit comparison: next-day OPEN vs next-day CLOSE")
print("=" * 70)

comparison = compare_exit_strategies(period="3mo", interval="1h")

for label, key in [("CLOSE (next day EOD)", "close"), ("OPEN (next day market open)", "open")]:
    r = comparison[key]
    o = r["overall"]
    print(f"\n{'─'*70}")
    print(f"  EXIT AT {label}")
    print(f"{'─'*70}")
    print(f"{'Symbol':<16} {'Trades':>7} {'WR%':>6} {'Avg%':>7} {'Cmpd%':>8} {'Opt%':>9}")
    print("-" * 55)
    for sym, s in sorted(r["per_symbol"].items()):
        print(f"{sym:<16} {s['total_trades']:>7} {s['win_rate']:>5.1f}% {s['avg_pnl_pct']:>6.2f}% {s['compound_return_pct']:>7.2f}% {s['total_option_pnl_pct']:>8.1f}%")
    print("-" * 55)
    print(f"{'TOTAL':<16} {o['total_trades']:>7} {o['win_rate']:>5.1f}% {o['avg_pnl_pct']:>6.2f}% {o['compound_return_pct']:>7.2f}% {o['total_option_pnl_pct']:>8.1f}%")

# Generate reports for both
print("\n\nGenerating Excel reports...")
close_path = generate_btst_report(comparison["close"])
open_path = generate_btst_report(comparison["open"])
print(f"  Exit CLOSE: {close_path}")
print(f"  Exit OPEN : {open_path}")

# ── Today's Signal ──
print("\n\n" + "=" * 70)
print("  TODAY'S BTST SIGNAL (15m data)")
print("=" * 70)
from agentest.utils.indicators.btst import get_today_signal

for s in BTST_SYMBOLS:
    sig = get_today_signal(s["symbol"], s["name"], s["category"], "15m")
    if sig:
        print(f"  {sig['name']:<14} {sig['signal']:<6} | {sig['reason']:<35} | Close={sig['close']:<10} | HA={sig['ha_signal']}")
    else:
        print(f"  {s['name']:<14} NO DATA")
