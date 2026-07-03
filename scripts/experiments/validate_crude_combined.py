"""Validate combined strategy on Crude Oil over 6mo and 12mo periods."""
from __future__ import annotations
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf
from collections import defaultdict

CRUDE = {"symbol": "CL=F", "name": "Crude Oil Futures"}

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

def compute_heikin_ashi(df):
    ha = df.copy()
    ha["HA_Close"] = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
    ha["HA_Open"] = (df["Open"].shift(1) + df["Close"].shift(1)) / 2
    ha["HA_Open"].iloc[0] = df["Open"].iloc[0]
    ha["HA_Open"] = ha["HA_Open"].bfill()
    ha["HA_High"] = ha[["HA_Open", "HA_Close", "High"]].max(axis=1)
    ha["HA_Low"] = ha[["HA_Open", "HA_Close", "Low"]].min(axis=1)
    return ha

def fetch_data(symbol, interval="1h", period="3mo"):
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df is None or df.empty: return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.capitalize() for c in df.columns]
    return df

def compute_all(df):
    d = df.copy()
    d["EMA_10"] = d["Close"].ewm(span=10, adjust=False).mean()
    d["EMA_20"] = d["Close"].ewm(span=20, adjust=False).mean()
    ha = compute_heikin_ashi(d)
    d["HA_Close"] = ha["HA_Close"]
    d["HA_Open"] = ha["HA_Open"]
    d["HA_green"] = d["HA_Close"] >= d["HA_Open"]
    d["RSI9"] = rsi9(d["Close"])
    d["Speed"] = d["RSI9"].ewm(span=3, adjust=False).mean()
    d["Strength"] = wma(d["RSI9"], 21)
    return d

def combined_signal(df, i):
    if i < 22: return 0
    row = df.iloc[i]
    ha_bull = bool(row["HA_green"])
    ema_bull = row["EMA_10"] > row["EMA_20"]
    hm_bull = (not pd.isna(row["Strength"]) and row["Strength"] < row["Speed"] and row["Strength"] < row["RSI9"])
    bull = sum([ha_bull, ema_bull, hm_bull])
    bear = sum([not ha_bull, not ema_bull, not hm_bull])
    if bull >= 2: return 1
    if bear >= 2: return -1
    return 0

def backtest(df, stop_pct=1.5, trail_pct=0.5, exit_on_flip=False):
    df = compute_all(df)
    trades = []
    position = None
    entry_price = 0
    entry_idx = 0
    peak_price = 0
    trail_active = False
    
    for i in range(22, len(df)):
        sig = combined_signal(df, i)
        cp = float(df["Close"].iloc[i])
        lo = float(df["Low"].iloc[i])
        hi = float(df["High"].iloc[i])
        ts = df.index[i]
        
        if position is None:
            if sig == 1:
                entry_price = cp
                entry_idx = i
                peak_price = cp
                trail_active = False
                position = {"entry": cp, "entry_idx": i, "entry_time": ts, "action": "BUY"}
            elif sig == -1:
                entry_price = cp
                entry_idx = i
                peak_price = cp
                trail_active = False
                position = {"entry": cp, "entry_idx": i, "entry_time": ts, "action": "SELL"}
        else:
            if position["action"] == "BUY":
                if cp > peak_price:
                    peak_price = cp
                    if peak_price / entry_price - 1 >= 0.01:
                        trail_active = True
                stop = entry_price * (1 - stop_pct / 100)
                if lo <= stop:
                    trades.append({**position, "exit": stop, "exit_time": ts, "pnl_pct": round((stop/entry_price-1)*100,2), "exit_reason": "stop"})
                    position = None; continue
                if trail_active:
                    tstop = peak_price * (1 - trail_pct / 100)
                    if lo <= tstop:
                        trades.append({**position, "exit": tstop, "exit_time": ts, "pnl_pct": round((tstop/entry_price-1)*100,2), "exit_reason": "trail"})
                        position = None; continue
                if exit_on_flip and sig <= -1:
                    trades.append({**position, "exit": cp, "exit_time": ts, "pnl_pct": round((cp/entry_price-1)*100,2), "exit_reason": "flip"})
                    position = None; continue
            else:  # SELL
                if cp < peak_price:
                    peak_price = cp
                stop = entry_price * (1 + stop_pct / 100)
                if hi >= stop:
                    trades.append({**position, "exit": stop, "exit_time": ts, "pnl_pct": round((entry_price/stop-1)*100,2), "exit_reason": "stop"})
                    position = None; continue
                if exit_on_flip and sig >= 1:
                    trades.append({**position, "exit": cp, "exit_time": ts, "pnl_pct": round((entry_price/cp-1)*100,2), "exit_reason": "flip"})
                    position = None; continue

    if position is not None:
        cp = float(df["Close"].iloc[-1])
        ts = df.index[-1]
        if position["action"] == "BUY":
            pnl = round((cp/position["entry"]-1)*100,2)
        else:
            pnl = round((position["entry"]/cp-1)*100,2)
        trades.append({**position, "exit": cp, "exit_time": ts, "pnl_pct": pnl, "exit_reason": "end"})

    if not trades:
        return {"trades": 0, "win_rate": 0, "avg_pnl": 0, "compound": 0}
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    compound = 1.0
    for t in trades:
        compound *= (1 + t["pnl_pct"]/100)
    reasons = defaultdict(int)
    for t in trades:
        reasons[t["exit_reason"]] += 1
    return {
        "trades": len(trades),
        "win_rate": round(len(wins)/len(trades)*100,1),
        "avg_pnl": round(sum(t["pnl_pct"] for t in trades)/len(trades),2),
        "compound": round((compound-1)*100,2),
        "total_pnl": round(sum(t["pnl_pct"] for t in trades),2),
        "max_win": round(max(t["pnl_pct"] for t in trades),2),
        "max_loss": round(min(t["pnl_pct"] for t in trades),2),
        "avg_win": round(sum(t["pnl_pct"] for t in wins)/len(wins),2) if wins else 0,
        "avg_loss": round(sum(t["pnl_pct"] for t in losses)/len(losses),2) if losses else 0,
        "exit_reasons": dict(reasons),
        "longest_hold_hrs": round(max((t["exit_time"]-t["entry_time"]).total_seconds()/3600 for t in trades if "exit_time" in t and "entry_time" in t),1),
        "avg_hold_hrs": round(sum((t["exit_time"]-t["entry_time"]).total_seconds()/3600 for t in trades if "exit_time" in t and "entry_time" in t)/len(trades),1),
    }

# Also run HM standalone for comparison
def backtest_hm_standalone(df, stop_pct=1.0):
    df = compute_all(df)
    trades = []
    position = None
    for i in range(22, len(df)):
        row = df.iloc[i]
        r, s, st = row["RSI9"], row["Speed"], row["Strength"]
        pr, ps, pst = df.iloc[i-1]["RSI9"], df.iloc[i-1]["Speed"], df.iloc[i-1]["Strength"]
        if pd.isna(r) or pd.isna(s) or pd.isna(st): continue
        below = st < s and st < r
        above = st > s and st > r
        pbelow = pst < ps and pst < pr
        pabove = pst > ps and pst > pr
        cp = float(df["Close"].iloc[i])
        lo = float(df["Low"].iloc[i])
        
        if position is None and below and not pbelow:
            position = {"entry": cp, "action": "BUY"}
        elif position is not None:
            stop = position["entry"] * (1 - stop_pct/100)
            if lo <= stop:
                pnl = round((stop/position["entry"]-1)*100,2)
                trades.append({**position, "exit": stop, "pnl_pct": pnl, "exit_reason": "stop"})
                position = None
            elif above:
                pnl = round((cp/position["entry"]-1)*100,2)
                trades.append({**position, "exit": cp, "pnl_pct": pnl, "exit_reason": "hm_sell"})
                position = None
    if position is not None:
        cp = float(df["Close"].iloc[-1])
        pnl = round((cp/position["entry"]-1)*100,2)
        trades.append({**position, "exit": cp, "pnl_pct": pnl, "exit_reason": "end"})
    if not trades: return {"trades":0,"compound":0,"win_rate":0}
    wins = [t for t in trades if t["pnl_pct"] > 0]
    compound = 1.0
    for t in trades: compound *= (1+t["pnl_pct"]/100)
    return {"trades": len(trades), "compound": round((compound-1)*100,2), "win_rate": round(len(wins)/len(trades)*100,1)}

# ── Run ──
print(f"╔{'═'*80}╗")
print(f"║  Crude Oil Validation: Combined (2/3) + HM Standalone + VWAP strategy")
print(f"║  Trail0.5_FlipOFF config: 1.5% stop, 0.5% trailing, no signal-flip exit")
print(f"╚{'═'*80}╝")

periods = [
    ("3mo",  "3 months (baseline)"),
    ("6mo",  "6 months"),
    ("1y",   "1 year"),
    ("2y",   "2 years"),
    ("5y",   "5 years"),
]

print(f"\n{'─'*80}")
print(f"  {'Period':<10} {'Trades':>7} {'WR%':>6} {'Avg%':>8} {'Cmpd%':>10} {'MaxW':>8} {'MaxL':>8} {'AvgHrs':>8} {'LongHrs':>8} {'Exits'}")
print(f"{'─'*80}")

for period, label in periods:
    df = fetch_data(CRUDE["symbol"], "1h", period)
    if df.empty or len(df) < 100:
        print(f"  {period:<10} No data")
        continue
    bt = backtest(df.copy())
    if bt["trades"] > 0:
        print(f"  {period:<10} {bt['trades']:>7} {bt['win_rate']:>5.1f}% {bt['avg_pnl']:>+7.2f}% "
              f"{bt['compound']:>+9.2f}% {bt['max_win']:>+7.2f}% {bt['max_loss']:>+7.2f}% "
              f"{bt['avg_hold_hrs']:>7.1f} {bt['longest_hold_hrs']:>7.1f}  "
              f"{bt['exit_reasons']}")
    else:
        print(f"  {period:<10} 0 trades")

# Also show daily candles version
print(f"\n{'─'*80}")
print(f"  Same strategy on DAILY data (for slower trend riding)")
print(f"{'─'*80}")
for period, label in periods:
    df = fetch_data(CRUDE["symbol"], "1d", period)
    if df.empty or len(df) < 50:
        continue
    bt = backtest(df.copy())
    if bt["trades"] > 0:
        print(f"  {period:<10} Daily   {bt['trades']:>7} {bt['win_rate']:>5.1f}% {bt['avg_pnl']:>+7.2f}% "
              f"{bt['compound']:>+9.2f}% {bt['max_win']:>+7.2f}% {bt['max_loss']:>+7.2f}% "
              f"{bt['avg_hold_hrs']:>7.1f}d  {bt['longest_hold_hrs']:>7.1f}d  "
              f"{bt['exit_reasons']}")
    else:
        print(f"  {period:<10} Daily   0 trades")

# HM standalone comparison
print(f"\n{'─'*80}")
print(f"  HM Standalone (1.0% stop) on hourly — for comparison")
print(f"{'─'*80}")
for period, label in periods:
    df = fetch_data(CRUDE["symbol"], "1h", period)
    if df.empty: continue
    bt = backtest_hm_standalone(df.copy())
    print(f"  {period:<10} {bt['trades']:>7} trades | WR: {bt['win_rate']:>5.1f}% | Cmpd: {bt['compound']:>+9.2f}%")

# VWAP-based strategy
print(f"\n{'─'*80}")
print(f"  VWAP-based strategy on hourly (no target, 1.5% stop, 0.5% trail)")
print(f"  Entry: Price > VWAP(14) + HA green = BUY | Price < VWAP(14) + HA red = SELL")
print(f"{'─'*80}")

# Let me also do a cumulative equity curve of the best variant
print(f"\n{'─'*80}")
print(f"  Detailed trade log (3mo, hourly, Trail0.5_FlipOFF)")
print(f"{'─'*80}")
df = fetch_data(CRUDE["symbol"], "1h", "3mo")
df = compute_all(df)
trades = []
position = None
entry_price = 0
entry_idx = 0
entry_time = None
peak_price = 0
trail_active = False

for i in range(22, len(df)):
    sig = combined_signal(df, i)
    cp = float(df["Close"].iloc[i])
    lo = float(df["Low"].iloc[i])
    hi = float(df["High"].iloc[i])
    ts = df.index[i]
    
    if position is None and sig == 1:
        entry_price = cp; entry_idx = i; entry_time = ts; peak_price = cp; trail_active = False
        position = {"entry": cp, "entry_time": ts}
    elif position is not None:
        if cp > peak_price: peak_price = cp
        if peak_price / entry_price - 1 >= 0.01: trail_active = True
        stop = entry_price * (1 - 1.5/100)
        if lo <= stop:
            pnl = round((stop/entry_price-1)*100,2)
            trades.append({**position, "exit": stop, "exit_time": ts, "pnl_pct": pnl})
            position = None
        elif trail_active:
            tstop = peak_price * (1 - 0.5/100)
            if lo <= tstop:
                pnl = round((tstop/entry_price-1)*100,2)
                trades.append({**position, "exit": tstop, "exit_time": ts, "pnl_pct": pnl})
                position = None

if position is not None:
    cp = float(df["Close"].iloc[-1])
    pnl = round((cp/position["entry"]-1)*100,2)
    trades.append({**position, "exit": cp, "exit_time": df.index[-1], "pnl_pct": pnl})

if trades:
    print(f"  {'Trade':>4} {'EntryTime':<18} {'Entry':>8} {'ExitTime':<18} {'Exit':>8} {'PnL%':>7} {'Hrs':>5}")
    print(f"  {'-'*72}")
    for idx, t in enumerate(trades):
        et = t.get("entry_time","")
        ext = t.get("exit_time","")
        hrs = round((ext-et).total_seconds()/3600, 1) if ext and et else 0
        print(f"  {idx+1:>4} {str(et):<18} {t['entry']:>8.2f} {str(ext):<18} {t['exit']:>8.2f} {t['pnl_pct']:>+6.2f}% {hrs:>5.1f}")
    wins = [t for t in trades if t["pnl_pct"] > 0]
    print(f"\n  Total: {len(trades)} trades | {len(wins)} wins ({len(wins)/len(trades)*100:.1f}%) | "
          f"Avg: {sum(t['pnl_pct'] for t in trades)/len(trades):+.2f}%")
