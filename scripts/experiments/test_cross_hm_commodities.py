"""Test HM CROSSOVER ONLY on Gold, Silver, Crude over long periods."""
from __future__ import annotations
import warnings; warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd
import yfinance as yf
from collections import defaultdict

ASSETS = {
    "CRUDE": {"symbol": "CL=F", "name": "Crude Oil"},
    "GOLD":   {"symbol": "GC=F", "name": "Gold"},
    "SILVER": {"symbol": "SI=F", "name": "Silver"},
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

def fetch_data(symbol, interval="1h", period="3mo"):
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df is None or df.empty: return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.capitalize() for c in df.columns]
    return df

def backtest_cross_hm(df, stop_pct=0.3, no_target=False):
    """HM crossover only: enter on crossover events, exit on opposite crossover or stop."""
    d = df.copy()
    d["RSI9"] = rsi9(d["Close"])
    d["Speed"] = d["RSI9"].ewm(span=3, adjust=False).mean()
    d["Strength"] = wma(d["RSI9"], 21)

    trades = []
    pos = None
    entry_price = 0; entry_time = None

    for i in range(22, len(d)):
        r = d["RSI9"].iloc[i]; s = d["Speed"].iloc[i]; st = d["Strength"].iloc[i]
        pr = d["RSI9"].iloc[i-1]; ps = d["Speed"].iloc[i-1]; pst = d["Strength"].iloc[i-1]
        if pd.isna(r) or pd.isna(s) or pd.isna(st): continue

        below = st < s and st < r
        above = st > s and st > r
        pbelow = pst < ps and pst < pr
        pabove = pst > ps and pst > pr

        cross_buy = below and not pbelow    # crossover BUY signal
        cross_sell = above and not pabove    # crossover SELL signal

        cp = float(d["Close"].iloc[i]); lo = float(d["Low"].iloc[i]); hi = float(d["High"].iloc[i]); ts = d.index[i]

        if pos is None:
            if cross_buy:
                pos = {"entry": cp, "entry_time": ts, "entry_idx": i, "action": "BUY"}
                entry_price = cp; entry_time = ts; continue
        else:
            # Stop loss check
            stop = entry_price * (1 - stop_pct/100)
            if lo <= stop:
                trades.append({**pos, "exit": stop, "exit_time": ts, "pnl_pct": round((stop/entry_price-1)*100,2), "exit_reason": f"stop_{stop_pct}"})
                pos = None; continue

            # Exit on opposite crossover
            if cross_sell:
                trades.append({**pos, "exit": cp, "exit_time": ts, "pnl_pct": round((cp/entry_price-1)*100,2), "exit_reason": "cross_sell"})
                pos = None; continue

    if pos is not None:
        cp = float(d["Close"].iloc[-1])
        trades.append({**pos, "exit": cp, "exit_time": d.index[-1], "pnl_pct": round((cp/pos["entry"]-1)*100,2), "exit_reason": "end"})

    if not trades: return {"trades":0,"win_rate":0,"avg_pnl":0,"compound":0}

    compound = 1.0
    for t in trades: compound *= (1 + t["pnl_pct"]/100)
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    reasons = defaultdict(int)
    for t in trades: reasons[t.get("exit_reason","?")] += 1
    hold_hrs = [(t["exit_time"]-t["entry_time"]).total_seconds()/3600 for t in trades if "exit_time" in t and "entry_time" in t]

    return {
        "trades": len(trades),
        "win_rate": round(len(wins)/len(trades)*100,1),
        "avg_pnl": round(sum(t["pnl_pct"] for t in trades)/len(trades),2),
        "compound": round((compound-1)*100,2),
        "max_win": round(max(t["pnl_pct"] for t in trades),2) if trades else 0,
        "max_loss": round(min(t["pnl_pct"] for t in trades),2) if trades else 0,
        "avg_hold_hrs": round(sum(hold_hrs)/len(hold_hrs),1) if hold_hrs else 0,
        "exit_reasons": dict(reasons),
    }

# Also test with no stop (pure crossover entry/exit)
def backtest_cross_hm_no_stop(df):
    d = df.copy()
    d["RSI9"] = rsi9(d["Close"])
    d["Speed"] = d["RSI9"].ewm(span=3, adjust=False).mean()
    d["Strength"] = wma(d["RSI9"], 21)
    trades = []; pos = None
    for i in range(22, len(d)):
        r, s, st = d["RSI9"].iloc[i], d["Speed"].iloc[i], d["Strength"].iloc[i]
        pr, ps, pst = d["RSI9"].iloc[i-1], d["Speed"].iloc[i-1], d["Strength"].iloc[i-1]
        if pd.isna(r) or pd.isna(s) or pd.isna(st): continue
        cross_buy = (st < s and st < r) and not (pst < ps and pst < pr)
        cross_sell = (st > s and st > r) and not (pst > ps and pst > pr)
        cp = float(d["Close"].iloc[i]); ts = d.index[i]
        if pos is None and cross_buy:
            pos = {"entry": cp, "entry_time": ts, "action": "BUY"}
        elif pos is not None and cross_sell:
            trades.append({**pos, "exit": cp, "exit_time": ts, "pnl_pct": round((cp/pos["entry"]-1)*100,2), "exit_reason": "cross"})
            pos = None
    if pos is not None:
        cp = float(d["Close"].iloc[-1])
        trades.append({**pos, "exit": cp, "exit_time": d.index[-1], "pnl_pct": round((cp/pos["entry"]-1)*100,2), "exit_reason": "end"})
    if not trades: return {"trades":0,"compound":0}
    compound = 1.0
    for t in trades: compound *= (1+t["pnl_pct"]/100)
    wins = [t for t in trades if t["pnl_pct"] > 0]
    return {"trades": len(trades), "compound": round((compound-1)*100,2), "win_rate": round(len(wins)/len(trades)*100,1)}

periods = [("3mo","3mo"), ("6mo","6mo"), ("1y","1yr"), ("2y","2yr")]

print(f"╔{'═'*80}╗")
print(f"║  HM CROSSOVER ONLY on Commodities (no HOLD/WATCH state — pure event-based)")
print(f"║  Entry: Strength crosses BELOW both Speed+RSI9 (BUY)")
print(f"║  Exit:  Opposite crossover (SELL) OR stop loss")
print(f"╚{'═'*80}╝")

for key, c in ASSETS.items():
    print(f"\n{'═'*80}")
    print(f"  {c['name']} ({c['symbol']})")
    print(f"{'═'*80}")

    print(f"\n  ── Cross HM with 0.3% stop (equity default) ──")
    print(f"  {'Period':<10} {'Trades':>7} {'WR%':>6} {'Avg%':>8} {'Cmpd%':>10} {'MaxW':>8} {'MaxL':>8} {'AvgHrs':>8}  Exits")
    print(f"  {'-'*80}")
    for p, pl in periods:
        df = fetch_data(c["symbol"], "1h", p)
        if df.empty: continue
        bt = backtest_cross_hm(df.copy(), stop_pct=0.3)
        print(f"  {p:<10} {bt['trades']:>7} {bt['win_rate']:>5.1f}% {bt['avg_pnl']:>+7.2f}% {bt['compound']:>+9.2f}% "
              f"{bt['max_win']:>+7.2f}% {bt['max_loss']:>+7.2f}% {bt['avg_hold_hrs']:>7.1f}  {bt['exit_reasons']}")

    print(f"\n  ── Cross HM with NO STOP (pure crossover exit) ──")
    print(f"  {'Period':<10} {'Trades':>7} {'WR%':>6} {'Cmpd%':>10}")
    for p, pl in periods:
        df = fetch_data(c["symbol"], "1h", p)
        if df.empty: continue
        bt = backtest_cross_hm_no_stop(df.copy())
        if bt["trades"] > 0:
            print(f"  {p:<10} {bt['trades']:>7} {bt['win_rate']:>5.1f}% {bt['compound']:>+9.2f}%")
        else:
            print(f"  {p:<10} {'0 trades':>14}")

    # Find best stop for each
    print(f"\n  ── Cross HM — STOP SWEEP (finding optimal stop %) ──")
    print(f"  {'Stop%':<8} {'3mo Cmpd':>10} {'6mo Cmpd':>10} {'1yr Cmpd':>10} {'2yr Cmpd':>10}")
    print(f"  {'-'*48}")
    for stop in [0.3, 0.5, 1.0, 1.5, 2.0, 5.0]:
        vals = []
        for p, pl in periods:
            df = fetch_data(c["symbol"], "1h", p)
            if df.empty: vals.append("N/A"); continue
            bt = backtest_cross_hm(df.copy(), stop_pct=stop)
            vals.append(f"{bt['compound']:>+8.2f}%" if bt['compound'] != 0 else "  0.00%")
        print(f"  {stop:<7.1f}%  {'  '.join(vals)}")

    # Compare with original HM (non-crossover) for same periods
    print(f"\n  ── Original HM (non-crossover) with best stop for comparison ──")
    print(f"  Previous best: Gold@0.3%, Silver@1.0%, Crude@1.0%")

    df = fetch_data(c["symbol"], "1h", "1y")
    if not df.empty:
        d = d2 = df.copy()
        d["RSI9"] = rsi9(d["Close"]); d["Speed"] = d["RSI9"].ewm(span=3, adjust=False).mean(); d["Strength"] = wma(d["RSI9"], 21)
        last = d.iloc[-1]; prev = d.iloc[-2]
        r = last["RSI9"]; s = last["Speed"]; st = last["Strength"]
        pr = prev["RSI9"]; ps = prev["Speed"]; pst = prev["Strength"]
        below = not pd.isna(st) and st < s and st < r
        above = not pd.isna(st) and st > s and st > r
        pbelow = not pd.isna(pst) and pst < ps and pst < pr
        pabove = not pd.isna(pst) and pst > ps and pst > pr
        cross_buy = below and not pbelow
        cross_sell = above and not pabove
        state = "bullish" if below else ("bearish" if above else "mixed")
        if cross_buy: state = "🚀 CROSS BUY"
        if cross_sell: state = "💀 CROSS SELL"
        print(f"  TODAY: {state} | Close=${float(last['Close']):.2f} RSI9={float(r):.2f} Speed={float(s):.2f} Strength={float(st):.2f}")

print(f"\n{'═'*80}")
print(f"  Cross HM vs Original HM — which wins per asset?")
print(f"{'═'*80}")
