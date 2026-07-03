"""Save today's signals to DB + query tools for tracking."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentest.utils.indicators.tracker_db import (
    init_db, save_btst_signals, save_longterm_signals,
    get_accuracy_summary, get_running_accuracy,
)

import json
import pandas as pd

REPORTS = Path.home() / "Documents" / "Agentest_Reports"
SCAN_RESULTS = Path("tests/temp/scan_results")


def save_todays_btst():
    """Read today's BTST Excel and save to DB."""
    today = datetime.now().strftime("%Y-%m-%d")
    folder = REPORTS / today
    if not folder.exists():
        folder = REPORTS / datetime.now().strftime("%Y-%m-%d")
        if not folder.exists():
            print(f"  No report folder for today ({today})")
            return []
    
    btst_files = list(folder.glob("BTST_TodaySignals_*.xlsx"))
    if not btst_files:
        print(f"  No BTST signal file found in {folder}")
        return []
    
    file = max(btst_files, key=lambda x: x.stat().st_mtime)
    df = pd.read_excel(file, header=None)
    
    signals = []
    for i in range(3, 28):
        sym = str(df.iloc[i, 0]) if pd.notna(df.iloc[i, 0]) else ""
        sig = str(df.iloc[i, 1]) if pd.notna(df.iloc[i, 1]) else ""
        close_val = df.iloc[i, 3]
        reason = str(df.iloc[i, 4]) if pd.notna(df.iloc[i, 4]) else ""
        ha_sig = str(df.iloc[i, 5]) if pd.notna(df.iloc[i, 5]) else ""
        ha_str = df.iloc[i, 6] if pd.notna(df.iloc[i, 6]) else 0
        vix = df.iloc[i, 7] if pd.notna(df.iloc[i, 7]) else None
        
        if not sym or not sig or sig in ("Symbol", "Signal"):
            continue
        
        strategy = "HM" if "HM" in reason else "EMA+HA"
        cat = str(df.iloc[i, 10]) if pd.notna(df.iloc[i, 10]) else ""
        
        try:
            c = float(close_val) if close_val not in (None, "Close", "") else None
        except (ValueError, TypeError):
            c = None
        
        signals.append({
            "symbol": sym.replace(".NS", "").replace("^", ""),
            "name": sym.replace(".NS", "").replace("^", ""),
            "category": cat,
            "strategy": strategy,
            "signal": sig,
            "reason": reason,
            "close": c,
            "ha_signal": ha_sig,
            "ha_strength": int(ha_str) if ha_str else 0,
            "vix": float(vix) if vix and vix != "VIX" else None,
            "volume_confirmed": False,
            "timestamp": str(datetime.now()),
        })
    
    if signals:
        save_btst_signals(signals, today)
        print(f"  Saved {len(signals)} BTST signals to DB")
    return signals


def save_todays_longterm():
    """Read today's scan_results JSONs and save to DB."""
    today = datetime.now().strftime("%Y-%m-%d")
    if not SCAN_RESULTS.exists():
        print(f"  No scan_results folder")
        return
    
    signals = []
    for f in SCAN_RESULTS.iterdir():
        if f.suffix != ".json":
            continue
        try:
            d = json.loads(f.read_text())
            if d.get("action") in ("BUY", "SELL", "HOLD", "WATCH", "SKIP"):
                # Ensure numeric fields
                for k in ("close", "ema_10", "ema_20", "ha_strength"):
                    if k in d:
                        try: d[k] = float(d[k]) if d[k] not in (None, "") else None
                        except: d[k] = None
                signals.append(d)
        except:
            continue
    
    if signals:
        save_longterm_signals(signals, today)
        print(f"  Saved {len(signals)} long-term signals to DB")
    return signals


def print_summary():
    """Print accuracy summary from DB."""
    print(f"\n{'='*55}")
    print("  BTST Signal Accuracy (last 30 days)")
    print(f"{'='*55}")
    
    acc = get_accuracy_summary()
    if not acc:
        print("  No data yet")
        return
    
    for r in acc:
        print(f"  {r['signal_date']:<12} {r['strategy']:<8} {r['total']:>3} signals ({r['buys']} BUY / {r['sells']} SELL)")
    
    print(f"\n  Running accuracy (last 90 days):")
    run_acc = get_running_accuracy()
    for r in run_acc:
        print(f"  {r['strategy']:<10} {r['signal']:<6} {r['total']:>3} trades | Avg PnL: {r['avg_pnl']:>+.2f}%")


if __name__ == "__main__":
    init_db()
    save_todays_longterm()
    save_todays_btst()
    print_summary()
