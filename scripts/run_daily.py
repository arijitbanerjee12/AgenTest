"""run_daily.py — Full daily scan: long-term signals + BTST + options summary.

Usage:
    uv run python scripts/run_daily.py
    uv run python scripts/run_daily.py --skip-btst    # Only long-term scan
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from agentest.utils.indicators.enriched_report import generate_enriched_report
from agentest.utils.indicators.btst import (
    BTST_SYMBOLS,
    run_btst_backtest,
    compare_exit_strategies,
    generate_btst_report,
    generate_today_signal_report,
    get_today_signal,
    compute_summary,
)

REPORTS_DIR = Path.home() / "Documents" / "Agentest_Reports"
SCAN_RESULTS = Path("tests/temp/scan_results")


def run_technical_scan(workers: int = 6) -> int:
    """Step 1: Run pytest focus_scan. Returns exit code."""
    print("\n" + "=" * 65)
    print("  STEP 1: Long-Term Technical Scan (ETFs + Large Caps)")
    print("=" * 65)
    cmd = [
        "uv", "run", "pytest", "tests/test_runner.py",
        "-m", "focus_scan", "-n", str(workers), "--tb=line", "-v",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    # Print tail of output (last ~40 lines)
    lines = result.stdout.splitlines()
    print("\n".join(lines[-min(40, len(lines)):]))
    if result.returncode != 0:
        print("\n  [INFO] Some stocks have no BUY/SELL signal (expected).")
    return result.returncode


def run_enriched_report(folder: Path | None = None) -> Path:
    """Step 2: Generate enriched Excel report with fundamental analysis."""
    print("\n" + "=" * 65)
    print("  STEP 2: Fundamental Analysis + Enriched Report")
    print("=" * 65)
    return generate_enriched_report(folder=folder)


def run_btst() -> dict:
    """Step 3: BTST backtest + today's signals."""
    print("\n" + "=" * 65)
    print("  STEP 3: BTST Backtest (Hourly — Top 7 Symbols)")
    print("=" * 65)

    print("  Running exit-at-CLOSE strategy...")
    close_r = run_btst_backtest(period="3mo", interval="1h", exit_timing="close")
    close_p = generate_btst_report(close_r)
    print(f"    Report: {close_p}")

    print("  Running exit-at-OPEN strategy...")
    open_r = run_btst_backtest(period="3mo", interval="1h", exit_timing="open")
    open_p = generate_btst_report(open_r)
    print(f"    Report: {open_p}")

    return {"close": close_r, "close_path": close_p, "open": open_r, "open_path": open_p}


def run_today_signals(folder: Path | None = None) -> list[dict]:
    """Step 4: Generate today's BTST signals on 15m data."""
    print("\n" + "=" * 65)
    print("  STEP 4: Today's BTST Signals (15m data) + Options View")
    print("=" * 65)

    results = []
    for s in BTST_SYMBOLS:
        sig = get_today_signal(s["symbol"], s["name"], s["category"], "15m")
        results.append(sig or {"name": s["name"], "signal": "NO DATA"})

    print(f"  {'Symbol':<16} {'Signal':<8} {'Options Action':<35} {'Close':<10} {'Reason'}")
    print(f"  {'-'*80}")
    for r in results:
        if r.get("signal") == "NO DATA":
            print(f"  {r['name']:<16} NO DATA")
            continue
        opt = "BUY Call ATM" if r["signal"] == "BUY" else "BUY Put ATM" if r["signal"] == "SELL" else "Wait"
        print(f"  {r['name']:<16} {r['signal']:<8} {opt:<35} {r['close']:<10} {r['reason']}")
    print()

    # Brief options P&L context
    print(f"  Options note: ATM option ~18x multiplier. A {0.5}% underlying move → ~9% option P&L.")
    print(f"  For BUY signals → buy ATM Call, target next-day close.")
    print(f"  For SELL signals → buy ATM Put, target next-day close.")

    # Save to Excel
    report = generate_today_signal_report(results, folder=folder)
    print(f"  Today's signals report: {report}")

    return results


def print_combined_summary(btst_data: dict | None = None):
    """Step 5: Print combined daily summary."""
    print("\n" + "=" * 65)
    print("  STEP 5: COMBINED DAILY SUMMARY")
    print("=" * 65)

    # Long-term signals
    if SCAN_RESULTS.exists():
        counts: dict[str, int] = defaultdict(int)
        buys: list[dict] = []
        for f in SCAN_RESULTS.iterdir():
            if f.suffix == ".json":
                d = json.loads(f.read_text())
                counts[d.get("action", "SKIP")] += 1
                if d.get("action") == "BUY":
                    buys.append(d)
        print(f"\n  LONG-TERM SIGNALS ({sum(counts.values())} stocks scanned)")
        print(f"  {'-'*50}")
        print(f"  BUY={counts.get('BUY',0)}  SELL={counts.get('SELL',0)}  "
              f"HOLD={counts.get('HOLD',0)}  WATCH={counts.get('WATCH',0)}  SKIP={counts.get('SKIP',0)}")
        if buys:
            print(f"  BUY signals:")
            for b in buys:
                print(f"    {b['symbol']:<22} | {b['category']:<10} | {b['reason']}")
    else:
        print("  No scan results found.")

    # BTST summary
    if btst_data:
        for label, key in [("EXIT AT CLOSE (next-day EOD)", "close"),
                           ("EXIT AT OPEN (next-day open)", "open")]:
            r = btst_data[key]
            o = r["overall"]
            print(f"\n  BTST — {label}")
            print(f"  {'-'*50}")
            print(f"  {o['total_trades']} trades | {o['win_rate']}% WR | "
                  f"Avg {o['avg_pnl_pct']}% | Cmpd {o['compound_return_pct']}% | "
                  f"Option {o['total_option_pnl_pct']}%")
            for sym, s in sorted(r["per_symbol"].items()):
                print(f"    {sym:<16} {s['total_trades']:>3} trades | "
                      f"WR {s['win_rate']:>5.1f}% | Cmpd {s['compound_return_pct']:>7.2f}% | "
                      f"Opt {s['total_option_pnl_pct']:>8.1f}%")

    print("\n" + "=" * 65)
    print("  DAILY SCAN COMPLETE")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(description="Daily Scan — Long-term + BTST + Options")
    parser.add_argument("--workers", type=int, default=6, help="Parallel workers for pytest")
    parser.add_argument("--btst-backtest", action="store_true", help="Run BTST hourly backtest (3mo) + Excel reports")
    args = parser.parse_args()

    now = datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n  Daily Scan — {ts}")
    print(f"  Workers: {args.workers} | BTST backtest: {'ON' if args.btst_backtest else 'OFF'}")

    # Shared daily folder for all reports
    daily_folder = REPORTS_DIR / now.strftime("%Y-%m-%d")
    daily_folder.mkdir(parents=True, exist_ok=True)

    run_technical_scan(args.workers)
    report_path = run_enriched_report(folder=daily_folder)
    print(f"\n  Long-term report: {report_path}")

    btst_data = None
    if args.btst_backtest:
        btst_data = run_btst()
    run_today_signals(folder=daily_folder)

    print_combined_summary(btst_data)


if __name__ == "__main__":
    main()
