"""HM Standalone + Quality Filters — which filter(s) improve WR and compound?"""
from __future__ import annotations
import sys
import pandas as pd
import numpy as np
import yfinance as yf

TOP20 = [
    {"name":"NIFTY","symbol":"^NSEI"},{"name":"SENSEX","symbol":"^BSESN"},{"name":"BANKNIFTY","symbol":"^NSEBANK"},
    {"name":"HDFCBANK","symbol":"HDFCBANK.NS"},{"name":"ICICIBANK","symbol":"ICICIBANK.NS"},{"name":"AXISBANK","symbol":"AXISBANK.NS"},
    {"name":"KOTAKBANK","symbol":"KOTAKBANK.NS"},{"name":"SBIN","symbol":"SBIN.NS"},{"name":"BAJFINANCE","symbol":"BAJFINANCE.NS"},
    {"name":"BAJAJFINSV","symbol":"BAJAJFINSV.NS"},{"name":"INFY","symbol":"INFY.NS"},{"name":"HCLTECH","symbol":"HCLTECH.NS"},
    {"name":"WIPRO","symbol":"WIPRO.NS"},{"name":"HINDUNILVR","symbol":"HINDUNILVR.NS"},{"name":"ITC","symbol":"ITC.NS"},
    {"name":"DMART","symbol":"DMART.NS"},{"name":"M&M","symbol":"M&M.NS"},{"name":"MARUTI","symbol":"MARUTI.NS"},
    {"name":"BAJAJ-AUTO","symbol":"BAJAJ-AUTO.NS"},{"name":"BHARTIARTL","symbol":"BHARTIARTL.NS"},
]
CAPITAL = 100_000; TARGET_PCT = 0.8; STOP_PCT = 0.3

def fetch(sym, p="3mo"):
    df = yf.download(sym, period=p, interval="1h", progress=False, auto_adjust=True)
    if df.empty: return df
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df

def rsi9(s):
    d = s.diff(); g = d.clip(lower=0); l = (-d).clip(lower=0)
    ag = g.rolling(9).mean(); al = l.rolling(9).mean()
    return 100 - (100 / (1 + ag / al))

def wma(s, l):
    w = np.arange(1, l + 1)
    def _w(a): return np.nan if len(a) < l else np.dot(a, w) / w.sum()
    return s.rolling(l).apply(_w, raw=True)

def adx(df, period=14):
    high, low, close = df["High"], df["Low"], df["Close"]
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    up = high - high.shift(); dn = low.shift() - low
    plus_dm = ((up > dn) & (up > 0)).astype(float) * up
    minus_dm = ((dn > up) & (dn > 0)).astype(float) * dn
    atr = tr.rolling(period).mean()
    di_plus = 100 * plus_dm.rolling(period).sum() / (atr * period + 1e-10)
    di_minus = 100 * minus_dm.rolling(period).sum() / (atr * period + 1e-10)
    dx = 100 * (di_plus - di_minus).abs() / (di_plus + di_minus + 1e-10)
    return dx.rolling(period).mean()

def compute(df):
    df["RSI9"] = rsi9(df["Close"])
    df["Speed"] = df["RSI9"].ewm(span=3, adjust=False).mean()
    df["Strength"] = wma(df["RSI9"], 21)
    df["HM_Buy"] = (df["Strength"] < df["Speed"]) & (df["Strength"] < df["RSI9"])
    df["HM_Sell"] = (df["Strength"] > df["Speed"]) & (df["Strength"] > df["RSI9"])
    df["EMA_50"] = df["Close"].ewm(span=50, adjust=False).mean()
    df["Vol_SMA"] = df["Volume"].rolling(20).mean()
    df["ADX"] = adx(df, 14)
    df["HM_Buy_x2"] = df["HM_Buy"] & df["HM_Buy"].shift(1)
    df["HM_Sell_x2"] = df["HM_Sell"] & df["HM_Sell"].shift(1)
    df["Gap"] = (df["Speed"] - df["Strength"]).abs()
    return df

# ─── Filter definitions ───
FILTERS = [
    ("C0 HM base",  lambda r, a: True),
    ("C1 +Trend",   lambda r, a: a == "BUY" and r["Close"] > r["EMA_50"] or a == "SELL" and r["Close"] < r["EMA_50"]),
    ("C2 +Volume",  lambda r, a: r["Volume"] > 1.3 * r["Vol_SMA"]),
    ("C3 +Gap>1",   lambda r, a: r["Gap"] > 1.0),
    ("C4 +ADX>20",  lambda r, a: r["ADX"] > 20),
    ("C5 +2bar",    lambda r, a: r["HM_Buy_x2"] if a == "BUY" else r["HM_Sell_x2"]),
    ("C6 +Trend+Vol", lambda r, a: (r["Close"] > r["EMA_50"] if a == "BUY" else r["Close"] < r["EMA_50"]) and r["Volume"] > 1.3 * r["Vol_SMA"]),
    ("C7 +Trend+Gap", lambda r, a: (r["Close"] > r["EMA_50"] if a == "BUY" else r["Close"] < r["EMA_50"]) and r["Gap"] > 1.0),
    ("C8 +Trend+ADX", lambda r, a: (r["Close"] > r["EMA_50"] if a == "BUY" else r["Close"] < r["EMA_50"]) and r["ADX"] > 20),
]

def backtest(sym, filter_fn, p="3mo"):
    df = fetch(sym, p)
    if df.empty or len(df) < 100: return []
    df = compute(df); df = df.iloc[60:].copy()
    trades = []
    for d, g in df.groupby(df.index.date):
        if len(g) < 2: continue
        last = g.iloc[-1]
        if last["HM_Buy"]: action = "BUY"
        elif last["HM_Sell"]: action = "SELL"
        else: continue
        try:
            if callable(filter_fn):
                passes = filter_fn(last, action)
            else:
                passes = True
            if not passes: continue
        except: continue
        ep = float(last["Close"])
        nd = [x for x in df.groupby(df.index.date).groups.keys() if x > d]
        if not nd: continue
        nx = df[df.index.date == nd[0]]
        if nx.empty: continue
        hi, lo, cl = float(nx["High"].max()), float(nx["Low"].min()), float(nx["Close"].iloc[-1])
        if action == "BUY":
            tg = ep * (1 + TARGET_PCT/100); st = ep * (1 - STOP_PCT/100)
            if hi >= tg: xp, rsn = tg, "target"
            elif lo <= st: xp, rsn = st, "stop"
            else: xp, rsn = cl, "close"
            pnl = (xp - ep) / ep * 100
        else:
            tg = ep * (1 - TARGET_PCT/100); st = ep * (1 + STOP_PCT/100)
            if lo <= tg: xp, rsn = tg, "target"
            elif hi >= st: xp, rsn = st, "stop"
            else: xp, rsn = cl, "close"
            pnl = (ep - xp) / ep * 100
        op = max(min(pnl * 18, 45), -45) - 0.15
        trades.append({"sym":sym, "ed":str(d), "xd":str(nd[0]), "action":action,
            "pnl":round(pnl,2), "win":pnl>0, "opt":int(int(CAPITAL*0.05)*op/100)})
    return trades

def summary(t):
    n = len(t)
    if n == 0: return {}
    w = [x for x in t if x["win"]]
    c = 1.0
    for x in t: c *= (1 + x["pnl"]/100)
    return {"n":n, "wr":round(len(w)/n*100,1), "avg":round(sum(x["pnl"] for x in t)/n,2),
            "avg_w":round(sum(x["pnl"] for x in w)/len(w),2) if w else 0,
            "avg_l":round(sum(x["pnl"] for x in t if not x["win"])/max(n-len(w),1),2),
            "maxl":round(min(x["pnl"] for x in t),2), "cmpd":round((c-1)*100,2)}

if __name__ == "__main__":
    print("=" * 140)
    print("  HM QUALITY FILTERS — Each filter applied to HM standalone (hourly 3mo)")
    print("  Target: reduce trades but improve WR and compound return")
    print("=" * 140)

    headers = ["Filter"] + [f[0] for f in FILTERS]
    print(f"  {'Symbol':<14}", end="")
    for h in headers[1:]:
        print(f" {h:<18}", end="")
    print()

    all_data = {f[0]: [] for f in FILTERS}

    for sym in TOP20:
        sys.stdout.write(f"\n  {sym['name']:<14}"); sys.stdout.flush()
        for fi, (fname, ffn) in enumerate(FILTERS):
            t = backtest(sym["symbol"], ffn)
            all_data[fname].extend(t)
            s = summary(t)
            if s.get("n", 0):
                sys.stdout.write(f" {s['n']:>3}tr{s['wr']:>5.1f}%{s['cmpd']:>+6.2f}%  ")
            else:
                sys.stdout.write(f" {'':>3}  {'':>5}  {'':>7}  ")

    # Summary table
    print(f"\n\n{'='*140}")
    print(f"  {'FILTER':<18} {'Trades':>6} {'WR%':>6} {'AvgPnL':>7} {'AvgWin':>7} {'AvgLoss':>7} {'MaxLoss':>8} {'Cmpd%':>8} {'Opt P&L':>9} {'ΔCmpd':>7} {'ΔTrades':>8}")
    print(f"  {'-'*92}")
    base = summary(all_data["C0 HM base"])
    for fname, _ in FILTERS:
        if fname not in all_data: continue
        s = summary(all_data[fname])
        if not s: continue
        dc = s["cmpd"] - base["cmpd"]
        dt = s["n"] - base["n"]
        print(f"  {fname:<18} {s['n']:>6} {s['wr']:>5.1f}% {s['avg']:>6.2f}% {s['avg_w']:>6.2f}% {s['avg_l']:>6.2f}% {s['maxl']:>7.2f}% {s['cmpd']:>7.2f}% {sum(x['opt'] for x in all_data[fname]):>8,} {dc:>+6.2f}% {dt:>+7d}")

    # Best filter analysis
    print(f"\n{'='*140}")
    print(f"  BEST FILTER by per-symbol compound improvement (vs C0 base)")
    print(f"{'='*140}")
    best_for_sym = {}
    for sym in TOP20:
        best_imp = -999; best_fn = "None"
        for fname, _ in FILTERS:
            if fname not in all_data: continue
            t0 = [x for x in all_data["C0 HM base"] if x["sym"] == sym["symbol"]]
            tf = [x for x in all_data[fname] if x["sym"] == sym["symbol"]]
            s0 = summary(t0); sf = summary(tf)
            if sf and s0 and sf.get("cmpd") is not None and s0.get("cmpd") is not None:
                imp = sf["cmpd"] - s0["cmpd"]
                if imp > best_imp:
                    best_imp = imp; best_fn = fname
        print(f"  {sym['name']:<14} → {best_fn:<18} ΔCmpd {best_imp:>+6.2f}%")

    print(f"\n{'='*140}")
    improved = sum(1 for fname, _ in FILTERS if fname != "C0 HM base" and fname in all_data and summary(all_data[fname]) and summary(all_data[fname])["cmpd"] > base["cmpd"])
    print(f"  Filters that improved compound vs base: {improved}/{len(FILTERS)-1}")
    for fname, _ in FILTERS[1:]:
        if fname not in all_data: continue
        s = summary(all_data[fname])
        if s and s["cmpd"] > base["cmpd"]:
            print(f"    ✓ {fname:<18} Cmpd {s['cmpd']:>+7.2f}% (vs base {base['cmpd']:>+7.2f}%)")
        elif s:
            print(f"    ✗ {fname:<18} Cmpd {s['cmpd']:>+7.2f}% (vs base {base['cmpd']:>+7.2f}%)")
