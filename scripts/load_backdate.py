"""Load June 21's BTST signals into DB, then track performance."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import yfinance as yf
from agentest.utils.indicators.tracker_db import _conn, init_db

REPORTS = Path.home() / "Documents" / "Agentest_Reports"
STOP_PCT = 0.3
TARGET_PCT = 0.8

def determine_result(signal, pnl, low_dd):
    if signal == "BUY": return "PASS" if pnl > 0 else "FAIL"
    elif signal == "SELL": return "PASS" if pnl < 0 else "FAIL"
    elif signal == "HOLD": return "PASS" if low_dd > -STOP_PCT else "FAIL"
    elif signal in ("WATCH", "SKIP"): return "PASS"
    return "pending"

def load_backdate(date_str: str):
    """Load signals from a historical BTST Excel into DB and track."""
    folder = REPORTS / date_str
    if not folder.exists():
        print(f"No folder for {date_str}")
        return
    
    files = list(folder.glob("BTST_TodaySignals_*.xlsx"))
    if not files:
        print(f"No BTST file in {folder}")
        return
    file = max(files, key=lambda x: x.stat().st_mtime)
    
    df = pd.read_excel(file, header=None)
    conn = _conn()
    
    # Delete existing entries for this date
    conn.execute("DELETE FROM btst_signals WHERE signal_date=?", (date_str,))
    conn.execute("DELETE FROM signal_performance WHERE signal_date=?", (date_str,))
    
    loaded = 0
    for i in range(3, 28):
        sym = str(df.iloc[i, 0]) if pd.notna(df.iloc[i, 0]) else ""
        sig = str(df.iloc[i, 1]) if pd.notna(df.iloc[i, 1]) else ""
        if not sym or not sig or sig in ("Symbol", "Signal"): continue
        
        reason = str(df.iloc[i, 4]) if pd.notna(df.iloc[i, 4]) else ""
        strategy = "HM" if "HM" in reason else "EMA+HA"
        close_val = df.iloc[i, 3]
        try: close = float(close_val)
        except: close = None
        
        conn.execute("""
            INSERT INTO btst_signals
            (signal_date, symbol, name, category, strategy, signal, reason, close)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (date_str, sym, sym, str(df.iloc[i, 10]) if pd.notna(df.iloc[i, 10]) else "",
              strategy, sig, reason, close))
        loaded += 1
    
    conn.commit()
    print(f"Loaded {loaded} signals from {date_str}")
    
    # Now track performance against next day
    tracked = 0
    cur = conn.execute(
        "SELECT id, symbol, signal, close, strategy FROM btst_signals WHERE signal_date=?",
        (date_str,)
    )
    for row in cur.fetchall():
        sid, symbol, signal, entry_price, strategy = row
        sym_yf = symbol
        if "^" not in sym_yf and ".NS" not in sym_yf:
            sym_yf = sym_yf + ".NS"
        
        df2 = yf.download(sym_yf, period="2d", interval="15m", progress=False, auto_adjust=True)
        if df2.empty or len(df2) < 5:
            continue
        if isinstance(df2.columns, pd.MultiIndex):
            df2.columns = [c[0] for c in df2.columns]
        
        open_p = float(df2["Close"].iloc[0])
        last_p = float(df2["Close"].iloc[-1])
        low_p = float(df2["Low"].min())
        high_p = float(df2["High"].max())
        
        if signal == "BUY": pnl = round((last_p/open_p-1)*100,2)
        elif signal == "SELL": pnl = round((open_p/last_p-1)*100,2)
        else: pnl = round((last_p/open_p-1)*100,2)
        
        low_dd = round((low_p/open_p-1)*100,2)
        result = determine_result(signal, pnl, low_dd)
        
        conn.execute("""
            INSERT INTO signal_performance
            (signal_date, symbol, name, strategy, signal, entry_price,
             next_open, next_close, next_high, next_low, pnl_pct, result,
             hit_target, hit_stop)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (date_str, symbol, symbol, strategy, signal, entry_price or open_p,
              open_p, last_p, high_p, low_p, pnl, result,
              1 if (high_p/open_p-1)*100 >= TARGET_PCT else 0,
              1 if low_dd <= -STOP_PCT else 0))
        
        icon = "✅" if result == "PASS" else "❌"
        print(f"  {icon} {symbol:<14} {signal:<6} {strategy:<8} PnL={pnl:+.2f}% DD={low_dd:.2f}% → {result}")
        tracked += 1
    
    conn.commit(); conn.close()
    print(f"Tracked {tracked} signals from {date_str}")

if __name__ == "__main__":
    init_db()
    for d in ["2026-06-21"]:
        load_backdate(d)
