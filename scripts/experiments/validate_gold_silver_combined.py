"""Validate combined strategy on Gold + Silver over long periods."""
from __future__ import annotations
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf
from collections import defaultdict

ASSETS = {
    "GOLD":   {"symbol": "GC=F", "name": "Gold Futures"},
    "SILVER": {"symbol": "SI=F", "name": "Silver Futures"},
}

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
    return ha

def fetch_data(symbol, interval="1h", period="3mo"):
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df is None or df.empty: return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.capitalize() for c in df.columns]
    return df

def backtest_combined(df, stop_pct=1.5, trail_pct=0.5, exit_on_flip=False, allow_short=False):
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

    trades = []
    position = None
    entry_price = 0
    entry_idx = 0
    entry_time = None
    peak_price = 0
    trail_active = False

    for i in range(22, len(d)):
        row = d.iloc[i]
        cp = float(row["Close"]); lo = float(row["Low"]); hi = float(row["High"]); ts = d.index[i]
        ha_bull = bool(row["HA_green"])
        ema_bull = row["EMA_10"] > row["EMA_20"]
        hm_bull = (not pd.isna(row["Strength"]) and row["Strength"] < row["Speed"] and row["Strength"] < row["RSI9"])
        bull = sum([ha_bull, ema_bull, hm_bull])
        bear = sum([not ha_bull, not ema_bull, not hm_bull])
        sig = 1 if bull >= 2 else (-1 if bear >= 2 else 0)

        if position is None:
            if sig == 1:
                position = {"entry": cp, "entry_time": ts, "action": "BUY", "entry_idx": i}
                entry_price = cp; entry_time = ts; entry_idx = i; peak_price = cp; trail_active = False
            elif allow_short and sig == -1:
                position = {"entry": cp, "entry_time": ts, "action": "SHORT", "entry_idx": i}
                entry_price = cp; entry_time = ts; entry_idx = i; peak_price = cp; trail_active = False
        else:
            act = position["action"]
            if act == "BUY":
                if cp > peak_price: peak_price = cp
                if peak_price / entry_price - 1 >= 0.01: trail_active = True
                stop = entry_price * (1 - stop_pct / 100)
                if lo <= stop:
                    trades.append({**position, "exit": stop, "exit_time": ts, "pnl_pct": round((stop/entry_price-1)*100,2), "exit_reason": "stop"}); position = None; continue
                if trail_active:
                    tstop = peak_price * (1 - trail_pct / 100)
                    if lo <= tstop:
                        trades.append({**position, "exit": tstop, "exit_time": ts, "pnl_pct": round((tstop/entry_price-1)*100,2), "exit_reason": "trail"}); position = None; continue
                if exit_on_flip and sig <= -1:
                    trades.append({**position, "exit": cp, "exit_time": ts, "pnl_pct": round((cp/entry_price-1)*100,2), "exit_reason": "flip"}); position = None; continue
            elif act == "SHORT":
                if cp < peak_price: peak_price = cp
                stop = entry_price * (1 + stop_pct / 100)
                if hi >= stop:
                    pnl = round((entry_price / stop - 1) * 100, 2)
                    trades.append({**position, "exit": stop, "exit_time": ts, "pnl_pct": pnl, "exit_reason": "stop"}); position = None; continue
                if exit_on_flip and sig >= 1:
                    pnl = round((entry_price / cp - 1) * 100, 2)
                    trades.append({**position, "exit": cp, "exit_time": ts, "pnl_pct": pnl, "exit_reason": "flip"}); position = None; continue

    if position is not None:
        cp = float(d["Close"].iloc[-1])
        if position["action"] == "BUY":
            pnl = round((cp/position["entry"]-1)*100,2)
        else:
            pnl = round((position["entry"]/cp-1)*100,2)
        trades.append({**position, "exit": cp, "exit_time": d.index[-1], "pnl_pct": pnl, "exit_reason": "end"})

    if not trades:
        return {"trades": 0, "win_rate": 0, "avg_pnl": 0, "compound": 0}
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    compound = 1.0
    for t in trades: compound *= (1 + t["pnl_pct"]/100)
    reasons = defaultdict(int)
    for t in trades: reasons[t.get("exit_reason","?")] += 1
    hold_hrs = [(t["exit_time"]-t["entry_time"]).total_seconds()/3600 for t in trades if "exit_time" in t and "entry_time" in t]

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
        "avg_hold_hrs": round(sum(hold_hrs)/len(hold_hrs),1) if hold_hrs else 0,
        "longest_hold_hrs": round(max(hold_hrs),1) if hold_hrs else 0,
    }

# Also try HM standalone for comparison
def backtest_hm_standalone(df, stop_pct=0.3):
    d = df.copy()
    d["RSI9"] = rsi9(d["Close"])
    d["Speed"] = d["RSI9"].ewm(span=3, adjust=False).mean()
    d["Strength"] = wma(d["RSI9"], 21)
    trades = []; pos = None
    for i in range(22, len(d)):
        r, s, st = d["RSI9"].iloc[i], d["Speed"].iloc[i], d["Strength"].iloc[i]
        pr, ps, pst = d["RSI9"].iloc[i-1], d["Speed"].iloc[i-1], d["Strength"].iloc[i-1]
        if pd.isna(r) or pd.isna(s) or pd.isna(st): continue
        below = st < s and st < r; above = st > s and st > r
        pbelow = pst < ps and pst < pr; pabove = pst > ps and pst > pr
        cp = float(d["Close"].iloc[i]); lo = float(d["Low"].iloc[i])
        if pos is None and below and not pbelow:
            pos = {"entry": cp, "entry_time": d.index[i], "action": "BUY"}
        elif pos is not None:
            stop = pos["entry"] * (1 - stop_pct/100)
            if lo <= stop:
                trades.append({**pos, "exit": stop, "exit_time": d.index[i], "pnl_pct": round((stop/pos["entry"]-1)*100,2), "exit_reason": "stop"}); pos = None
            elif above:
                trades.append({**pos, "exit": cp, "exit_time": d.index[i], "pnl_pct": round((cp/pos["entry"]-1)*100,2), "exit_reason": "hm_sell"}); pos = None
    if pos is not None:
        cp = float(d["Close"].iloc[-1])
        trades.append({**pos, "exit": cp, "exit_time": d.index[-1], "pnl_pct": round((cp/pos["entry"]-1)*100,2), "exit_reason": "end"})
    if not trades: return {"trades":0,"compound":0,"win_rate":0}
    compound = 1.0
    for t in trades: compound *= (1+t["pnl_pct"]/100)
    wins = [t for t in trades if t["pnl_pct"] > 0]
    return {"trades": len(trades), "compound": round((compound-1)*100,2), "win_rate": round(len(wins)/len(trades)*100,1)}

periods = [
    ("3mo",  "3 months"),
    ("6mo",  "6 months"),
    ("1y",   "1 year"),
    ("2y",   "2 years"),
]

print(f"╔{'═'*90}╗")
print(f"║  Gold + Silver Validation: Combined 2/3 Strategy (Trail0.5_FlipOFF, long only)")
print(f"║  Config: Entry on 2/3 indicator agreement, 1.5% stop, 0.5% trailing, no short")
print(f"╚{'═'*90}╝")

for key, c in ASSETS.items():
    print(f"\n{'═'*90}")
    print(f"  {c['name']} ({c['symbol']})")
    print(f"{'═'*90}")

    print(f"\n  ── Combined 2/3 Strategy (hourly) ──")
    print(f"  {'Period':<10} {'Trades':>7} {'WR%':>6} {'Avg%':>8} {'Cmpd%':>10} {'MaxW':>10} {'MaxL':>8} {'AvgHrs':>8} {'LongHrs':>8}  Exits")
    print(f"  {'-'*90}")

    for period, label in periods:
        df = fetch_data(c["symbol"], "1h", period)
        if df.empty or len(df) < 100:
            print(f"  {period:<10} No data")
            continue
        bt = backtest_combined(df.copy(), stop_pct=1.5, trail_pct=0.5, exit_on_flip=False, allow_short=False)
        if bt["trades"] > 0:
            print(f"  {period:<10} {bt['trades']:>7} {bt['win_rate']:>5.1f}% {bt['avg_pnl']:>+7.2f}% "
                  f"{bt['compound']:>+9.2f}% {bt['max_win']:>+9.2f}% {bt['max_loss']:>+8.2f}% "
                  f"{bt['avg_hold_hrs']:>7.1f} {bt['longest_hold_hrs']:>7.1f}  {bt['exit_reasons']}")
        else:
            print(f"  {period:<10} 0 trades")

    # Also try with tighter stop for Gold (since it's less volatile)
    print(f"\n  ── Combined 2/3 Strategy (hourly) with TIGHTER 0.5% stop ──")
    print(f"  {'Period':<10} {'Trades':>7} {'WR%':>6} {'Avg%':>8} {'Cmpd%':>10}")
    for period, label in periods:
        df = fetch_data(c["symbol"], "1h", period)
        if df.empty: continue
        bt = backtest_combined(df.copy(), stop_pct=0.5, trail_pct=0.3, exit_on_flip=False, allow_short=False)
        if bt["trades"] > 0:
            print(f"  {period:<10} {bt['trades']:>7} {bt['win_rate']:>5.1f}% {bt['avg_pnl']:>+7.2f}% {bt['compound']:>+9.2f}%")
        else:
            print(f"  {period:<10} 0 trades")

    # HM standalone comparison
    print(f"\n  ── HM Standalone (hourly) with 0.3% stop — for comparison ──")
    print(f"  {'Period':<10} {'Trades':>7} {'WR%':>6} {'Cmpd%':>10}")
    for period, label in periods:
        df = fetch_data(c["symbol"], "1h", period)
        if df.empty: continue
        bt = backtest_hm_standalone(df.copy(), stop_pct=0.3)
        print(f"  {period:<10} {bt['trades']:>7} {bt['win_rate']:>5.1f}% {bt['compound']:>+9.2f}%")

    # HM standalone with 1% stop (what worked for Silver earlier)
    print(f"\n  ── HM Standalone (hourly) with 1.0% stop ──")
    print(f"  {'Period':<10} {'Trades':>7} {'WR%':>6} {'Cmpd%':>10}")
    for period, label in periods:
        df = fetch_data(c["symbol"], "1h", period)
        if df.empty: continue
        bt = backtest_hm_standalone(df.copy(), stop_pct=1.0)
        print(f"  {period:<10} {bt['trades']:>7} {bt['win_rate']:>5.1f}% {bt['compound']:>+9.2f}%")

    # Today's signal
    df = fetch_data(c["symbol"], "1h", "5d")
    if len(df) > 22:
        d = df.copy()
        d["EMA_10"] = d["Close"].ewm(span=10, adjust=False).mean()
        d["EMA_20"] = d["Close"].ewm(span=20, adjust=False).mean()
        ha = compute_heikin_ashi(d)
        d["HA_Close"], d["HA_Open"] = ha["HA_Close"], ha["HA_Open"]
        d["HA_green"] = d["HA_Close"] >= d["HA_Open"]
        d["RSI9"] = rsi9(d["Close"])
        d["Speed"] = d["RSI9"].ewm(span=3, adjust=False).mean()
        d["Strength"] = wma(d["RSI9"], 21)
        last = d.iloc[-1]
        ha_b = bool(last["HA_green"]); ema_b = last["EMA_10"]>last["EMA_20"]
        hm_b = not pd.isna(last["Strength"]) and last["Strength"]<last["Speed"] and last["Strength"]<last["RSI9"]
        sig = "BULLISH" if sum([ha_b, ema_b, hm_b]) >= 2 else ("BEARISH" if sum([not ha_b, not ema_b, not hm_b]) >= 2 else "MIXED")
        print(f"\n  TODAY: {sig} | HA={'🟢' if ha_b else '🔴'} EMA={'🟢' if ema_b else '🔴'} HM={'🟢' if hm_b else '🔴'} | "
              f"${float(last['Close']):.2f} RSI9={float(last['RSI9']):.2f}")

print(f"\n{'═'*90}")
print(f"  SUMMARY: Best config per asset")
print(f"{'═'*90}")
