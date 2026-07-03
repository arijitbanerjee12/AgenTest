"""Track ALL signal types — mark PASS/FAIL based on next-day price action.
Run after market close to update yesterday's signal results in DB."""
from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
import yfinance as yf
from agentest.utils.indicators.tracker_db import _conn, DB_PATH

STOP_PCT = 0.3   # BTST stop loss
TARGET_PCT = 0.8 # BTST target

def determine_result(signal: str, pnl: float, low_dd: float, high_gain: float) -> str:
    """Determine PASS/FAIL for each signal type."""
    if signal == "BUY":
        return "PASS" if pnl > 0 else "FAIL"
    elif signal == "SELL":
        return "PASS" if pnl > 0 else "FAIL"
    elif signal == "HOLD":
        # HOLD = we are already in the position. PASS if price didn't hit stop
        return "PASS" if low_dd > -STOP_PCT else "FAIL"
    elif signal == "WATCH":
        # WATCH = crossed but weak. PASS if no significant move against
        return "PASS" if abs(pnl) < 1.5 else "FAIL"
    elif signal == "SKIP":
        return "PASS"  # no action taken, always pass
    return "pending"


def track_signals(target_date: str | None = None):
    """Compare signals from target_date with next-day price action."""
    if target_date is None:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    conn = _conn()
    
    # Fetch ALL signal types (not just BUY/SELL)
    cur = conn.execute(
        "SELECT id, symbol, signal, close, strategy FROM btst_signals WHERE signal_date=? AND signal IN ('BUY','SELL','HOLD','WATCH','SKIP')",
        (target_date,)
    )
    signals = cur.fetchall()
    if not signals:
        print(f"  [DB] No signals found for {target_date}")
        conn.close()
        return
    
    print(f"  [DB] Tracking {len(signals)} signals from {target_date}")
    
    updated = 0
    for row in signals:
        sid, symbol, signal, entry_price, strategy = row
        
        # Build yfinance symbol
        sym = symbol
        if "^" not in sym and ".NS" not in sym:
            sym = sym + ".NS"
        
        df = yf.download(sym, period="2d", interval="15m", progress=False, auto_adjust=True)
        if df.empty or len(df) < 5:
            print(f"    ⚠ {symbol:<14} No data")
            continue
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        
        open_p = float(df["Close"].iloc[0])
        last_p = float(df["Close"].iloc[-1])
        low_p = float(df["Low"].min())
        high_p = float(df["High"].max())
        
        # PnL depends on direction
        if signal == "BUY":
            pnl = round((last_p / open_p - 1) * 100, 2)
        elif signal == "SELL":
            pnl = round((open_p / last_p - 1) * 100, 2)
        else:
            pnl = round((last_p / open_p - 1) * 100, 2)  # neutral for HOLD/WATCH/SKIP
        
        low_dd = round((low_p / open_p - 1) * 100, 2)
        high_gain = round((high_p / open_p - 1) * 100, 2)
        result = determine_result(signal, pnl, low_dd, high_gain)
        
        hit_target = 1 if high_gain >= TARGET_PCT else 0
        hit_stop = 1 if low_dd <= -STOP_PCT else 0
        
        # Upsert: replace if already exists for this date+symbol+strategy
        conn.execute("""
            DELETE FROM signal_performance WHERE signal_date=? AND symbol=? AND strategy=?
        """, (target_date, symbol, strategy))
        
        conn.execute("""
            INSERT INTO signal_performance
            (signal_date, symbol, name, strategy, signal, entry_price,
             next_open, next_close, next_high, next_low, pnl_pct, result,
             hit_target, hit_stop)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            target_date, symbol, symbol, strategy, signal,
            entry_price if entry_price else open_p,
            open_p, last_p, high_p, low_p, pnl, result,
            hit_target, hit_stop
        ))
        
        icon = "✅" if result == "PASS" else "❌"
        print(f"    {icon} {symbol:<14} {signal:<6} {strategy:<8} Entry={entry_price or open_p:.2f} → Now={last_p:.2f}  PnL={pnl:+.2f}%  DD={low_dd:.2f}%  → {result}")
        updated += 1
    
    conn.commit()
    conn.close()
    print(f"  [DB] Done: {updated}/{len(signals)} signals updated")


def summary(date: str | None = None):
    """Print today's tracking summary from DB."""
    conn = _conn()
    
    print(f"\n{'='*60}")
    print(f"  SIGNAL TRACKING SUMMARY")
    print(f"{'='*60}")
    
    cur = conn.execute("""
        SELECT signal_date, strategy, signal, result, COUNT(*) as cnt
        FROM signal_performance
        GROUP BY signal_date, strategy, signal, result
        ORDER BY signal_date DESC, strategy, signal
    """)
    
    current_date = None
    for r in cur.fetchall():
        sd, strat, sig, res, cnt = r
        if sd != current_date:
            print(f"\n  {sd}:")
            current_date = sd
        icon = "✅" if res == "PASS" else "❌"
        print(f"    {strat:<8} {sig:<6} → {icon} {res:<6} {cnt}x")
    
    # Overall accuracy
    cur = conn.execute("""
        SELECT strategy, signal,
               SUM(CASE WHEN result='PASS' THEN 1 ELSE 0 END) as passes,
               COUNT(*) as total
        FROM signal_performance
        WHERE result IN ('PASS','FAIL')
        GROUP BY strategy, signal
    """)
    print(f"\n  RUNNING ACCURACY (all time):")
    for r in cur.fetchall():
        strat, sig, passes, total = r
        pct = round(passes/total*100, 1)
        bar = "█" * int(pct/10) + "░" * (10 - int(pct/10))
        print(f"    {strat:<8} {sig:<6} {bar} {passes}/{total} ({pct}%)")
    
    conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Track signal performance in DB")
    parser.add_argument("--date", type=str, help="Signal date (YYYY-MM-DD), default=yesterday")
    parser.add_argument("--summary", action="store_true", help="Print summary from DB")
    args = parser.parse_args()
    
    if args.summary:
        summary(args.date)
    else:
        track_signals(args.date)
        summary(args.date)
