"""Experiment v2: HM on hourly commodities — no target, -0.5% stop, exit on HM SELL."""
from __future__ import annotations
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf

COMMODITIES = {
    "GOLD":    {"symbol": "GC=F",  "name": "Gold Futures"},
    "SILVER":  {"symbol": "SI=F",  "name": "Silver Futures"},
    "NGAS":    {"symbol": "NG=F",  "name": "Nat Gas Futures"},
    "CRUDEOIL":{"symbol": "CL=F",  "name": "Crude Oil Futures"},
}

STOP_LOSS_PCT = 1.0

def rsi9(series):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_g = gain.rolling(9).mean()
    avg_l = loss.rolling(9).mean().replace(0, np.nan)
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))

def wma(series, length):
    weights = np.arange(1, length + 1)
    def _wma(arr):
        if len(arr) < length: return np.nan
        return np.dot(arr, weights) / weights.sum()
    return series.rolling(length).apply(_wma, raw=True)

def fetch_data(symbol, interval="1h", period="3mo"):
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df is None or df.empty: return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.capitalize() for c in df.columns]
    return df

def hm_signal_at(df, idx):
    if idx < 22: return None
    last = df.iloc[idx]
    prev = df.iloc[idx-1]
    r, s, st = last["RSI9"], last["Speed"], last["Strength"]
    pr, ps, pst = prev["RSI9"], prev["Speed"], prev["Strength"]
    if pd.isna(r) or pd.isna(s) or pd.isna(st): return None
    below = st < s and st < r
    above = st > s and st > r
    prev_below = pst < ps and pst < pr
    prev_above = pst > ps and pst > pr
    
    if below and not prev_below:
        return {"action": "BUY", "strength": 2}
    if above and not prev_above:
        return {"action": "SELL", "strength": -2}
    if below:
        return {"action": "HOLD", "strength": 1}
    if above:
        return {"action": "SELL", "strength": -1}
    return {"action": "WATCH", "strength": 0}

def backtest_hm_no_target(df, label=""):
    df["RSI9"] = rsi9(df["Close"])
    df["Speed"] = df["RSI9"].ewm(span=3, adjust=False).mean()
    df["Strength"] = wma(df["RSI9"], 21)
    
    trades = []
    position = None
    entry_price = 0
    entry_idx = 0
    
    for i in range(22, len(df)):
        sig = hm_signal_at(df, i)
        if sig is None:
            continue
        
        if position is None and sig["action"] == "BUY":
            entry_price = float(df["Close"].iloc[i])
            entry_idx = i
            position = {"entry": entry_price, "entry_idx": i, "action": "BUY"}
        
        elif position is not None:
            current_price = float(df["Close"].iloc[i])
            low = float(df["Low"].iloc[i])
            high = float(df["High"].iloc[i])
            
            # Check stop loss first (intra-bar)
            stop_price = entry_price * (1 - STOP_LOSS_PCT / 100)
            if low <= stop_price:
                exit_price = stop_price
                pnl_pct = round((exit_price / entry_price - 1) * 100, 2)
                trades.append({**position, "exit": exit_price, "pnl_pct": pnl_pct, "exit_reason": f"stop_{STOP_LOSS_PCT}pct"})
                position = None
                continue
            
            # Exit on HM SELL signal (cross or above both)
            if sig["action"] == "SELL":
                exit_price = current_price
                pnl_pct = round((exit_price / entry_price - 1) * 100, 2)
                trades.append({**position, "exit": exit_price, "pnl_pct": pnl_pct, "exit_reason": "hm_sell"})
                position = None
    
    # Close any open position at end
    if position is not None:
        exit_price = float(df["Close"].iloc[-1])
        pnl_pct = round((exit_price / position["entry"] - 1) * 100, 2)
        trades.append({**position, "exit": exit_price, "pnl_pct": pnl_pct, "exit_reason": "end_data"})
    
    if not trades:
        return {"trades": 0, "win_rate": 0, "avg_pnl": 0, "compound": 0, "total_pnl": 0}
    
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    
    compound = 1.0
    for t in trades:
        compound *= (1 + abs(t["pnl_pct"]) / 100) if t["pnl_pct"] < 0 else (1 + t["pnl_pct"] / 100)
    # Actually just multiply
    compound = 1.0
    for t in trades:
        compound *= (1 + t["pnl_pct"] / 100)
    compound_pct = round((compound - 1) * 100, 2)
    
    stop_exits = [t for t in trades if "stop" in t.get("exit_reason", "")]
    hm_exits = [t for t in trades if "hm" in t.get("exit_reason", "")]
    end_exits = [t for t in trades if "end" in t.get("exit_reason", "")]
    
    avg_hold = round(sum(t["entry_idx"] for t in [t for t in trades if "entry_idx" in t]), 0) if trades else 0
    # calculate avg hold bars properly
    hold_bars = []
    for t in trades:
        idx = t.get("entry_idx", 0)
        # find exit idx — not stored, approximate
    hold_bars_str = ""
    
    return {
        "trades": len(trades),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "avg_pnl": round(sum(t["pnl_pct"] for t in trades) / len(trades), 2),
        "compound": compound_pct,
        "total_pnl": round(sum(t["pnl_pct"] for t in trades), 2),
        "max_win": round(max(t["pnl_pct"] for t in trades), 2) if trades else 0,
        "max_loss": round(min(t["pnl_pct"] for t in trades), 2) if trades else 0,
        "avg_win": round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else 0,
        "avg_loss": round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else 0,
        "pct_stop": round(len(stop_exits) / len(trades) * 100, 1) if trades else 0,
        "pct_hm": round(len(hm_exits) / len(trades) * 100, 1) if trades else 0,
    }

# ── Run experiment ──
print(f"╔{'═'*70}╗")
print(f"║  HM Commodities v4: No target | Stop -1.0% | Exit on HM SELL")
print(f"╚{'═'*70}╝")

results = []
for key, c in COMMODITIES.items():
    print(f"\n{'─'*70}")
    print(f"  {c['name']} ({c['symbol']})")
    print(f"{'─'*70}")
    
    df = fetch_data(c["symbol"], "1h", "3mo")
    if df.empty or len(df) < 100:
        print(f"  ⚠ No data")
        continue
    print(f"  Data: {len(df)} hourly candles")
    
    bt = backtest_hm_no_target(df, key)
    results.append({"key": key, **c, **bt})
    
    print(f"  Trades: {bt['trades']} | WR: {bt['win_rate']}% | Avg: {bt['avg_pnl']:+.2f}%")
    print(f"  Compound: {bt['compound']:+.2f}% | Total PnL: {bt['total_pnl']:+.2f}%")
    if bt['trades'] > 0:
        print(f"  Max win: {bt['max_win']:+.2f}% | Max loss: {bt['max_loss']:+.2f}%")
        print(f"  Avg win: {bt['avg_win']:+.2f}% | Avg loss: {bt['avg_loss']:+.2f}%")
        print(f"  Exits: {bt['pct_stop']}% via -1.0% stop | {bt['pct_hm']}% via HM SELL")
    
    # Today's signal
    df_sig = df.copy()
    df_sig["RSI9"] = rsi9(df_sig["Close"])
    df_sig["Speed"] = df_sig["RSI9"].ewm(span=3, adjust=False).mean()
    df_sig["Strength"] = wma(df_sig["RSI9"], 21)
    if len(df_sig) > 22:
        sig = hm_signal_at(df_sig, len(df_sig)-1)
        if sig:
            last = df_sig.iloc[-1]
            print(f"\n  TODAY: {sig['action']:<6} | ${float(last['Close']):.2f} | "
                  f"RSI9={float(last['RSI9']):.2f} Speed={float(last['Speed']):.2f} Strength={float(last['Strength']):.2f}")

# Summary
print(f"\n\n{'='*70}")
print(f"  RESULTS SUMMARY (v4: no target, -1.0% stop, HM SELL exit)")
print(f"{'='*70}")
print(f"  {'Symbol':<18} {'Trades':>8} {'WR%':>6} {'Avg%':>8} {'Compound%':>12} {'viaStop':>8} {'viaHM':>8}")
print(f"  {'-'*70}")
for r in results:
    if r['trades'] > 0:
        print(f"  {r['key']:<18} {r['trades']:>8} {r['win_rate']:>5.1f}% {r['avg_pnl']:>+7.2f}% {r['compound']:>+10.2f}% {r['pct_stop']:>7.1f}% {r['pct_hm']:>7.1f}%")
    else:
        print(f"  {r['key']:<18} {'0 trades':>14}")

print(f"\n{'─'*70}")
print(f"  Compare: HM equity (hourly, same params) ~53% WR, ~+155% compound avg")
print(f"  Key question: can we widen stop/target to match commodity vol?")
print(f"{'─'*70}")
