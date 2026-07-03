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
    BTST_SYMBOLS_SECTOR,
    HM_SYMBOLS,
    INDEX_NAMES,
    run_btst_backtest,
    run_btst_backtest_hm,
    generate_btst_report,
    generate_today_signal_report,
    get_today_signal,
    get_today_signal_hm,
    compute_summary,
)
from agentest.utils.indicators.journal import journal_summary, JOURNAL_FILE
from agentest.utils.indicators.slack_notify import send_btst_daily, send_longterm_report
from agentest.utils.indicators.enriched_report import _load_holdings
from agentest.utils.indicators.tracker_db import save_btst_signals, save_longterm_signals

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
    """Step 3: BTST backtest (core 11 symbols)."""
    print("\n" + "=" * 65)
    print("  STEP 3: BTST Backtest (Hourly — 11 Symbols)")
    print("=" * 65)

    print("  Running TRAILING strategy (activate 0.5%, trail 0.3%, SL 0.3%)...")
    trail_r = run_btst_backtest(period="3mo", interval="1h", exit_timing="trailing")
    trail_p = generate_btst_report(trail_r)
    print(f"    Report: {trail_p}")

    print("  Running CLOSE strategy (exit next-day EOD, SL 0.3% / Tgt 0.8%)...")
    close_r = run_btst_backtest(period="3mo", interval="1h", exit_timing="close")
    close_p = generate_btst_report(close_r)
    print(f"    Report: {close_p}")

    return {"trailing": trail_r, "trailing_path": trail_p,
            "close": close_r, "close_path": close_p}


def run_btst_hm() -> dict:
    """Step 3c: HM BTST backtest on same symbols."""
    print("\n" + "=" * 65)
    print("  STEP 3c: HM BTST Backtest (Hourly — same symbols)")
    print("=" * 65)
    print("  Running TRAILING strategy with HM signals...")
    hm_trail = run_btst_backtest_hm(period="3mo", interval="1h", exit_timing="trailing")
    hm_trail_p = generate_btst_report(hm_trail)
    print(f"    Report: {hm_trail_p}")
    print("  Running CLOSE strategy with HM signals...")
    hm_close = run_btst_backtest_hm(period="3mo", interval="1h", exit_timing="close")
    hm_close_p = generate_btst_report(hm_close)
    print(f"    Report: {hm_close_p}")
    return {"trailing": hm_trail, "trailing_path": hm_trail_p,
            "close": hm_close, "close_path": hm_close_p}


def run_btst_sector() -> dict:
    """Step 3b: Sector-wise BTST backtest (39 symbols by sector)."""
    print("\n" + "=" * 65)
    print("  STEP 3b: SECTOR BTST Backtest (Hourly — 39 Symbols)")
    print("=" * 65)

    print("  Running TRAILING strategy across all sectors...")
    trail_r = run_btst_backtest(BTST_SYMBOLS_SECTOR, period="3mo", interval="1h", exit_timing="trailing")
    trail_p = generate_btst_report(trail_r)
    print(f"    Report: {trail_p}")

    print("  Running CLOSE strategy across all sectors...")
    close_r = run_btst_backtest(BTST_SYMBOLS_SECTOR, period="3mo", interval="1h", exit_timing="close")
    close_p = generate_btst_report(close_r)
    print(f"    Report: {close_p}")

    return {"trailing": trail_r, "trailing_path": trail_p,
            "close": close_r, "close_path": close_p}


def _print_table(rows, headers, widths):
    """Print a formatted table. rows = list of lists of values. headers = list of strings."""
    hdr = "  " + "  ".join(f"{h:<{w}}" for h, w in zip(headers, widths))
    sep = "  " + "-" * (sum(widths) + len(widths) * 2)
    print(hdr)
    print(sep)
    for row in rows:
        print("  " + "  ".join(f"{str(v):<{w}}" for v, w in zip(row, widths)))


def run_today_signals(folder: Path | None = None) -> list[dict]:
    """Step 4: Generate today's BTST signals on 15m data (EMA+HA + HM)."""
    print("\n" + "=" * 65)
    print("  STEP 4: Today's BTST Signals (15m data) + Options View")
    print("=" * 65)

    # ── Collect ALL signals ──
    ha_results: list[dict] = []
    for s in BTST_SYMBOLS:
        sig = get_today_signal(s["symbol"], s["name"], s["category"], "15m")
        ha_results.append(sig or {"name": s["name"], "signal": "NO DATA", "strategy": "HA"})

    hm_results: list[dict] = []
    for s in HM_SYMBOLS:
        sig = get_today_signal_hm(s["symbol"], s["name"], s["category"], "15m")
        hm_results.append(sig or {"name": s["name"], "signal": "NO DATA", "strategy": "HM"})

    # ── Split: indices vs stocks ──
    idx_ha = [r for r in ha_results if r.get("name") in INDEX_NAMES]
    stock_ha = [r for r in ha_results if r.get("name") not in INDEX_NAMES]
    idx_hm = [r for r in hm_results if r.get("name") in INDEX_NAMES]
    stock_hm = [r for r in hm_results if r.get("name") not in INDEX_NAMES]

    def _fmt_amt(r):
        if r.get("signal") in ("SKIP", "NO DATA"):
            return "—"
        pct = r.get("position_size_pct")
        rs = r.get("recommended_premium_rs")
        if pct and rs:
            return f"₹{rs:,} ({pct}%)"
        return "—"

    # ── Print INDICES table (always shown, HA + HM) ──
    print(f"\n  ── INDICES ──")
    combo_hdrs_idx = ["Symbol", "Strat", "Sig", "Close", "VIX", "Invest", "HA/HM", "Reason"]
    combo_widths_idx = [14, 6, 6, 10, 8, 12, 10, 50]
    idx_rows = []
    for r in idx_ha:
        s = r.get("signal", "NO DATA")
        vd = f"{r.get('vix','')}!" if r.get("vix_warning") else str(r.get('vix',''))
        hh = f"HA_{r.get('ha_signal','')}" if r.get("ha_signal") else "HA"
        idx_rows.append([r["name"], "HA", s, r.get("close",""), vd, _fmt_amt(r), hh, r.get("reason","")])
    for r in idx_hm:
        s = r.get("signal", "NO DATA")
        vd = f"{r.get('vix','')}!" if r.get("vix_warning") else str(r.get('vix',''))
        hh = f"RSI{r.get('rsi9','')}" if r.get("rsi9") else "HM"
        idx_rows.append([r["name"], "HM", s, r.get("close",""), vd, _fmt_amt(r), hh, r.get("reason","")])
    _print_table(idx_rows, combo_hdrs_idx, combo_widths_idx)

    # ── Print COMBINED table (stock HA + HM) ──
    print(f"\n  ── ALL SIGNALS (HA + HM) ──")
    combined_rows = []
    combo_hdrs = ["Symbol", "Strat", "Sig", "Close", "VIX", "Invest", "HA/HM", "Reason"]
    combo_widths = [14, 6, 6, 10, 8, 12, 10, 50]

    for r in stock_ha:
        s = r.get("signal", "NO DATA")
        vd = f"{r.get('vix','')}!" if r.get("vix_warning") else str(r.get('vix',''))
        hh = f"HA_{r.get('ha_signal','')}" if r.get("ha_signal") else r.get("strategy","HA")
        combined_rows.append([r["name"], "HA", s, r.get("close",""), vd, _fmt_amt(r), hh, r.get("reason","")])

    for r in stock_hm:
        s = r.get("signal", "NO DATA")
        vd = f"{r.get('vix','')}!" if r.get("vix_warning") else str(r.get('vix',''))
        hh = f"RSI{r.get('rsi9','')}" if r.get("rsi9") else ""
        combined_rows.append([r["name"], "HM", s, r.get("close",""), vd, _fmt_amt(r), hh, r.get("reason","")])

    _print_table(combined_rows, combo_hdrs, combo_widths)

    print()
    print(f"  Capital: ₹1,00,000")
    print(f"  SL: 0.3% underlying (~5.4% option) | Target: 0.8% underlying (~14.4% option)")
    print(f"  VIX > 25 → skip trading. ATM opt ~18x multiplier. BUY→Call, SELL→Put.")

    # ── Excel report ──
    combined = ha_results + hm_results
    report = generate_today_signal_report(combined, folder=folder)
    print(f"  Today's signals report: {report}")

    return combined


def print_combined_summary(btst_data: dict | None = None, sector_data: dict | None = None, hm_btst_data: dict | None = None):
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
        for label, key in [("TRAILING (activate 0.5%, trail 0.3%)", "trailing"),
                           ("CLOSE (exit next-day EOD, SL/Tgt)", "close")]:
            r = btst_data[key]
            o = r["overall"]
            cfg = r.get("config", {})
            print(f"\n  BTST — {label}")
            print(f"  {'-'*65}")
            print(f"  {o['total_trades']} trades | {o['win_rate']}% WR | "
                  f"Cmpd {o['compound_return_pct']}% | "
                  f"Opt ₹{o.get('total_option_pnl_rs', 0):,} | ROI {o.get('option_roi_pct', 0)}%")
            for sym, s in sorted(r["per_symbol"].items()):
                print(f"    {sym:<16} {s['total_trades']:>3} trades | "
                      f"WR {s['win_rate']:>5.1f}% | Cmpd {s['compound_return_pct']:>7.2f}% | "
                      f"Opt ₹{s.get('total_option_pnl_rs', 0):>7,} | ROI {s.get('option_roi_pct', 0):>5.1f}%")

    # Sector BTST summary
    if sector_data:
        for label, key in [("TRAILING", "trailing"), ("CLOSE", "close")]:
            r = sector_data[key]
            o = r["overall"]
            print(f"\n  SECTOR BTST — {label} ({len(r['symbols_run'])} symbols)")
            print(f"  {'-'*65}")
            print(f"  {o['total_trades']} trades | {o['win_rate']}% WR | "
                  f"Cmpd {o['compound_return_pct']}% | "
                  f"Opt ₹{o.get('total_option_pnl_rs', 0):,} | ROI {o.get('option_roi_pct', 0)}%")
            print(f"\n  {'Sector':<26} {'Trades':>6} {'WR':>6} {'Cmpd':>8} {'Opt₹':>8} {'ROI':>6}")
            print(f"  {'-'*65}")
            sec_sum = r.get("sector_summary", {})
            for sec in SECTOR_ORDER:
                s = sec_sum.get(sec)
                if s and s["total_trades"] > 0:
                    print(f"  {sec:<26} {s['total_trades']:>6} {s['win_rate']:>5.1f}% "
                          f"{s['compound_return_pct']:>7.2f}% ₹{s.get('total_option_pnl_rs', 0):>6,} "
                          f"{s.get('option_roi_pct', 0):>5.1f}%")
            # Top 5 symbols
            print(f"\n  Top 5 symbols by WR:")
            top5 = sorted(r["per_symbol"].items(), key=lambda x: x[1]["win_rate"], reverse=True)[:5]
            for sym, s in top5:
                print(f"    {sym:<18} {s['total_trades']:>3} trades | WR {s['win_rate']:>5.1f}% | "
                      f"Cmpd {s['compound_return_pct']:>6.2f}% | ROI {s.get('option_roi_pct', 0):>5.1f}%")

    # HM BTST summary
    if hm_btst_data:
        for label, key in [("TRAILING", "trailing"), ("CLOSE", "close")]:
            r = hm_btst_data[key]
            o = r["overall"]
            print(f"\n  HM BTST — {label}")
            print(f"  {'-'*65}")
            print(f"  {o['total_trades']} trades | {o['win_rate']}% WR | "
                  f"Cmpd {o['compound_return_pct']}% | "
                  f"Opt ₹{o.get('total_option_pnl_rs', 0):,} | ROI {o.get('option_roi_pct', 0)}%")
            for sym, s in sorted(r["per_symbol"].items()):
                print(f"    {sym:<16} {s['total_trades']:>3} trades | "
                      f"WR {s['win_rate']:>5.1f}% | Cmpd {s['compound_return_pct']:>7.2f}% | "
                      f"Opt ₹{s.get('total_option_pnl_rs', 0):>7,} | ROI {s.get('option_roi_pct', 0):>5.1f}%")

    print("\n" + "=" * 65)
    print("  DAILY SCAN COMPLETE")
    print("=" * 65)


SECTOR_ORDER = [
    "Index", "Banking", "Banking (PSU)", "NBFC", "Financial Services",
    "IT", "FMCG", "Retail", "Cement & Textiles",
    "Automotive", "Pharma", "Telecom", "Insurance",
    "Mining (PSU)", "Power Transmission", "Power", "Oil & Gas", "Defense & Aerospace",
    "Engineering & Construction", "Aluminum & Metals", "Steel", "Healthcare",
    "Paints & Chemicals",
]

def main():
    parser = argparse.ArgumentParser(description="Daily Scan — Long-term + BTST + Options")
    parser.add_argument("--workers", type=int, default=6, help="Parallel workers for pytest")
    parser.add_argument("--btst-backtest", action="store_true", help="Run BTST hourly backtest (3mo) + Excel reports")
    parser.add_argument("--sector-backtest", action="store_true", help="Run sector-wise BTST backtest (39 symbols)")
    parser.add_argument("--date", type=str, default=None, help="Override date (YYYY-MM-DD), defaults to today")
    args = parser.parse_args()

    now = datetime.strptime(args.date + " 09:15:00", "%Y-%m-%d %H:%M:%S") if args.date else datetime.now()
    ts = now.strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n  Daily Scan — {ts}")
    print(f"  Workers: {args.workers} | BTST backtest: {'ON' if args.btst_backtest else 'OFF'} | Sector BTST: {'ON' if args.sector_backtest else 'OFF'}")

    daily_folder = REPORTS_DIR / now.strftime("%Y-%m-%d")
    daily_folder.mkdir(parents=True, exist_ok=True)

    run_technical_scan(args.workers)
    report_path = run_enriched_report(folder=daily_folder)
    print(f"\n  Long-term report: {report_path}")

    btst_data = None
    hm_btst_data = None
    sector_data = None
    if args.btst_backtest:
        btst_data = run_btst()
        hm_btst_data = run_btst_hm()
    if args.sector_backtest:
        sector_data = run_btst_sector()

    today_signals = run_today_signals(folder=daily_folder)

    print_combined_summary(btst_data, sector_data, hm_btst_data=hm_btst_data)

    # Slack notification
    _notify_slack(btst_data, sector_data, now, SCAN_RESULTS, today_signals, hm_btst_data=hm_btst_data)

    # Journal summary
    j = journal_summary()
    if j["total_trades"] > 0:
        print(f"\n  JOURNAL ({JOURNAL_FILE})")
        print(f"  {'-'*40}")
        print(f"  Total trades: {j['total_trades']} | WR: {j['win_rate']}% | "
              f"Avg P&L: {j['avg_pnl_pct']}%")
        top = sorted(j["by_symbol"].items(), key=lambda x: x[1]["win_rate"], reverse=True)[:5]
        for sym, d in top:
            print(f"    {sym:<16} {d['trades']:>3} trades | WR {d['win_rate']}%")

    print(f"\n  [Slack] Notification sent to workspace.")


def _notify_slack(btst_data, sector_data, now, scan_results_dir, today_signals=None, hm_btst_data=None):
    """Gather data and send Slack notifications (BTST + Long-term channels)."""
    long_term_counts = None
    buy_signals = []
    sell_signals = []
    if scan_results_dir.exists():
        from collections import defaultdict as dd
        c: dict[str, int] = dd(int)
        for f in scan_results_dir.iterdir():
            if f.suffix == ".json":
                try:
                    d = json.loads(f.read_text())
                    c[d.get("action", "SKIP")] += 1
                    if d.get("action") == "BUY":
                        buy_signals.append(d)
                    elif d.get("action") == "SELL":
                        sell_signals.append(d)
                except Exception:
                    pass
        long_term_counts = dict(c)

    btst_signals = today_signals

    btst_summary = None
    r = None
    if btst_data:
        r = btst_data.get("trailing")
    elif sector_data:
        r = sector_data.get("trailing")
    if r:
        btst_summary = {"overall": r["overall"], "per_symbol": r.get("per_symbol", {})}

    hm_summary = None
    if hm_btst_data:
        r2 = hm_btst_data.get("trailing")
        if r2:
            hm_summary = {"overall": r2["overall"], "per_symbol": r2.get("per_symbol", {})}

    # ── Save to DB ──
    sd = now.strftime("%Y-%m-%d")
    if btst_signals:
        save_btst_signals(btst_signals, sd)
    all_scan_signals = buy_signals + sell_signals + [{"action": "SKIP"}]
    if all_scan_signals:
        save_longterm_signals(all_scan_signals, sd)

    # ── BTST channel ──
    send_btst_daily(
        btst_signals=btst_signals,
        long_term_counts=long_term_counts,
        btst_summary=btst_summary,
        hm_summary=hm_summary,
        scan_date=now.strftime("%d %b %Y"),
    )

    # ── Long-term channel ──
    holdings_alerts = []
    holdings = _load_holdings()
    if holdings:
        sell_tickers = {s.get("symbol", "").upper() for s in sell_signals}
        for h in holdings:
            if h.get("ticker", "").upper() in sell_tickers:
                holdings_alerts.append(h)

    send_longterm_report(
        buy_signals=buy_signals,
        sell_signals=sell_signals,
        holdings_alerts=holdings_alerts,
        counts=long_term_counts,
        scan_date=now.strftime("%d %b %Y"),
    )


if __name__ == "__main__":
    main()
