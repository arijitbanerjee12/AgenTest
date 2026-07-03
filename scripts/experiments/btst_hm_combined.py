"""Combine Hilega Milega (COMPUTED ON HOURLY DATA) with EMA+HA.
Test on last 3mo hourly, top 20 stocks.
Both EMA+HA and HM condition checked on the SAME hourly candle (last of day).
Variant: also test HM standalone (no EMA+HA) on hourly data.
"""
from __future__ import annotations
import sys
import pandas as pd
import numpy as np
import yfinance as yf

TOP20 = [
    {"name":"NIFTY","symbol":"^NSEI","category":"index"},
    {"name":"SENSEX","symbol":"^BSESN","category":"index"},
    {"name":"BANKNIFTY","symbol":"^NSEBANK","category":"index"},
    {"name":"HDFCBANK","symbol":"HDFCBANK.NS","category":"large_cap"},
    {"name":"ICICIBANK","symbol":"ICICIBANK.NS","category":"large_cap"},
    {"name":"AXISBANK","symbol":"AXISBANK.NS","category":"large_cap"},
    {"name":"KOTAKBANK","symbol":"KOTAKBANK.NS","category":"large_cap"},
    {"name":"SBIN","symbol":"SBIN.NS","category":"large_cap"},
    {"name":"BAJFINANCE","symbol":"BAJFINANCE.NS","category":"large_cap"},
    {"name":"BAJAJFINSV","symbol":"BAJAJFINSV.NS","category":"large_cap"},
    {"name":"INFY","symbol":"INFY.NS","category":"large_cap"},
    {"name":"HCLTECH","symbol":"HCLTECH.NS","category":"large_cap"},
    {"name":"WIPRO","symbol":"WIPRO.NS","category":"large_cap"},
    {"name":"HINDUNILVR","symbol":"HINDUNILVR.NS","category":"large_cap"},
    {"name":"ITC","symbol":"ITC.NS","category":"large_cap"},
    {"name":"DMART","symbol":"DMART.NS","category":"large_cap"},
    {"name":"M&M","symbol":"M&M.NS","category":"large_cap"},
    {"name":"MARUTI","symbol":"MARUTI.NS","category":"large_cap"},
    {"name":"BAJAJ-AUTO","symbol":"BAJAJ-AUTO.NS","category":"large_cap"},
    {"name":"BHARTIARTL","symbol":"BHARTIARTL.NS","category":"large_cap"},
]

CAPITAL = 100_000
TARGET_PCT = 0.8   # 0.8% target
STOP_PCT = 0.3     # 0.3% stop loss


# ─── helpers ───

def fetch_hourly(symbol, period="3mo"):
    df = yf.download(symbol, period=period, interval="1h", progress=False, auto_adjust=True)
    if df.empty: return df
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def rsi9(series):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_g = gain.rolling(9).mean()
    avg_l = loss.rolling(9).mean()
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))


def wma_lin(series, length):
    weights = np.arange(1, length + 1)
    def _wma(arr):
        if len(arr) < length: return np.nan
        return np.dot(arr, weights) / weights.sum()
    return series.rolling(length).apply(_wma, raw=True)


# ─── HM on hourly data ───

def compute_hm_hourly(df):
    """Compute HM lines on hourly data. Modifies df in place."""
    df["RSI9"] = rsi9(df["Close"])
    df["Speed"] = df["RSI9"].ewm(span=3, adjust=False).mean()
    df["Strength"] = wma_lin(df["RSI9"], 21)
    # Original HM: Strength < both Speed & RSI9 = BUY, > both = SELL
    df["HM_Buy"] = (df["Strength"] < df["Speed"]) & (df["Strength"] < df["RSI9"])
    df["HM_Sell"] = (df["Strength"] > df["Speed"]) & (df["Strength"] > df["RSI9"])
    # Crossover HM: Speed crosses above/below Strength
    df["Cross_Buy"] = (df["Speed"] > df["Strength"]) & (df["Speed"].shift(1) <= df["Strength"].shift(1))
    df["Cross_Sell"] = (df["Speed"] < df["Strength"]) & (df["Speed"].shift(1) >= df["Strength"].shift(1))
    return df


# ─── EMA + HA (same as production btst.py) ───

def compute_ema_ha(df):
    df["EMA_10"] = df["Close"].ewm(span=10, adjust=False).mean()
    df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
    ha = compute_heikin_ashi(df)
    for c in ["HA_Open","HA_High","HA_Low","HA_Close"]:
        df[c] = ha[c]
    return df


def compute_heikin_ashi(df):
    ha = df.copy()
    ha["HA_Close"] = (df["Open"] + df["High"] + df["Low"] + df["Close"]) / 4
    ha["HA_Open"] = (df["Open"].shift(1) + df["Close"].shift(1)) / 2
    ha.loc[ha.index[0], "HA_Open"] = (df["Open"].iloc[0] + df["Close"].iloc[0]) / 2
    ha["HA_High"] = ha[["HA_Open", "HA_Close", "High"]].max(axis=1)
    ha["HA_Low"] = ha[["HA_Open", "HA_Close", "Low"]].min(axis=1)
    return ha


# ─── Backtest: EMA+HA alone ───

def backtest_baseline(symbol, period="3mo"):
    df = fetch_hourly(symbol, period)
    if df.empty or len(df) < 100: return []
    df = compute_ema_ha(df)
    df = df.iloc[25:].copy()

    trades = []
    # Group by date
    for date, group in df.groupby(df.index.date):
        if len(group) < 2: continue
        last = group.iloc[-1]
        prev = group.iloc[-2] if len(group) > 1 else last

        # Determine signal (same logic as btst.py)
        ema_bull = last["EMA_10"] > last["EMA_20"]
        ha_bull = last["HA_Close"] > last["HA_Open"]
        prev_ha_bull = prev["HA_Close"] > prev["HA_Open"]

        if ema_bull and ha_bull:
            action = "BUY"
        elif not ema_bull and not ha_bull:
            action = "SELL"
        else:
            continue

        entry_price = float(last["Close"])
        # Find next day's data
        next_dates = [d for d in df.groupby(df.index.date).groups.keys() if d > date]
        if not next_dates: continue
        next_day = df[df.index.date == next_dates[0]]
        if next_day.empty: continue

        # Exit: next-day close with target/SL
        high = float(next_day["High"].max())
        low = float(next_day["Low"].min())
        close = float(next_day["Close"].iloc[-1])

        if action == "BUY":
            target = entry_price * (1 + TARGET_PCT / 100)
            stop = entry_price * (1 - STOP_PCT / 100)
            if high >= target:
                exit_price = target
                exit_reason = "target"
            elif low <= stop:
                exit_price = stop
                exit_reason = "stop"
            else:
                exit_price = close
                exit_reason = "close"
            pnl = (exit_price - entry_price) / entry_price * 100
        else:
            target = entry_price * (1 - TARGET_PCT / 100)
            stop = entry_price * (1 + STOP_PCT / 100)
            if low <= target:
                exit_price = target
                exit_reason = "target"
            elif high >= stop:
                exit_price = stop
                exit_reason = "stop"
            else:
                exit_price = close
                exit_reason = "close"
            pnl = (entry_price - exit_price) / entry_price * 100

        opt_pnl = max(min(pnl * 18, 45), -45) - 0.15
        trades.append({
            "symbol": symbol, "entry_date": str(date), "exit_date": str(next_dates[0]),
            "action": action, "entry_price": round(entry_price, 2), "exit_price": round(exit_price, 2),
            "pnl_pct": round(pnl, 2), "win": pnl > 0, "exit_reason": exit_reason,
            "option_pnl_pct": round(opt_pnl, 2), "premium_rs": int(CAPITAL * 0.05),
            "option_pnl_rs": int(int(CAPITAL * 0.05) * opt_pnl / 100),
        })
    return trades


# ─── Backtest: EMA+HA + HM filter (both on hourly) ───

def backtest_combined(symbol, period="3mo"):
    df = fetch_hourly(symbol, period)
    if df.empty or len(df) < 100: return []

    # Compute both EMA+HA and HM on hourly data
    df = compute_ema_ha(df)
    df = compute_hm_hourly(df)
    # Need warmup: EMA 10/20 = 25 bars, HM WMA21 = 25 bars (RSI9 needs 10)
    df = df.iloc[30:].copy()

    trades = []
    for date, group in df.groupby(df.index.date):
        if len(group) < 2: continue
        last = group.iloc[-1]

        # EMA+HA signal on last hourly candle
        ema_bull = last["EMA_10"] > last["EMA_20"]
        ha_bull = last["HA_Close"] > last["HA_Open"]
        if ema_bull and ha_bull:
            action = "BUY"
        elif not ema_bull and not ha_bull:
            action = "SELL"
        else:
            continue

        # HM condition on SAME candle (hourly)
        hm_buy = bool(last["HM_Buy"])
        hm_sell = bool(last["HM_Sell"])

        # Only take trade if HM agrees
        if action == "BUY" and not hm_buy:
            continue
        if action == "SELL" and not hm_sell:
            continue

        entry_price = float(last["Close"])
        next_dates = [d for d in df.groupby(df.index.date).groups.keys() if d > date]
        if not next_dates: continue
        next_day = df[df.index.date == next_dates[0]]
        if next_day.empty: continue

        high = float(next_day["High"].max())
        low = float(next_day["Low"].min())
        close = float(next_day["Close"].iloc[-1])

        if action == "BUY":
            target = entry_price * (1 + TARGET_PCT / 100)
            stop = entry_price * (1 - STOP_PCT / 100)
            if high >= target:
                exit_price = target; exit_reason = "target"
            elif low <= stop:
                exit_price = stop; exit_reason = "stop"
            else:
                exit_price = close; exit_reason = "close"
            pnl = (exit_price - entry_price) / entry_price * 100
        else:
            target = entry_price * (1 - TARGET_PCT / 100)
            stop = entry_price * (1 + STOP_PCT / 100)
            if low <= target:
                exit_price = target; exit_reason = "target"
            elif high >= stop:
                exit_price = stop; exit_reason = "stop"
            else:
                exit_price = close; exit_reason = "close"
            pnl = (entry_price - exit_price) / entry_price * 100

        opt_pnl = max(min(pnl * 18, 45), -45) - 0.15
        trades.append({
            "symbol": symbol, "entry_date": str(date), "exit_date": str(next_dates[0]),
            "action": action, "entry_price": round(entry_price, 2), "exit_price": round(exit_price, 2),
            "pnl_pct": round(pnl, 2), "win": pnl > 0, "exit_reason": exit_reason,
            "option_pnl_pct": round(opt_pnl, 2), "premium_rs": int(CAPITAL * 0.05),
            "option_pnl_rs": int(int(CAPITAL * 0.05) * opt_pnl / 100),
        })
    return trades


# ─── Backtest: HM standalone on hourly data ───

def backtest_hm_standalone(symbol, period="3mo"):
    df = fetch_hourly(symbol, period)
    if df.empty or len(df) < 100: return []

    df = compute_hm_hourly(df)
    df = df.iloc[30:].copy()  # warmup for WMA21

    trades = []
    for date, group in df.groupby(df.index.date):
        if len(group) < 2: continue
        last = group.iloc[-1]

        # HM condition on last candle of day
        if last["HM_Buy"]:
            action = "BUY"
        elif last["HM_Sell"]:
            action = "SELL"
        else:
            continue

        entry_price = float(last["Close"])
        next_dates = [d for d in df.groupby(df.index.date).groups.keys() if d > date]
        if not next_dates: continue
        next_day = df[df.index.date == next_dates[0]]
        if next_day.empty: continue

        high = float(next_day["High"].max())
        low = float(next_day["Low"].min())
        close = float(next_day["Close"].iloc[-1])

        if action == "BUY":
            target = entry_price * (1 + TARGET_PCT / 100)
            stop = entry_price * (1 - STOP_PCT / 100)
            if high >= target:
                exit_price = target; exit_reason = "target"
            elif low <= stop:
                exit_price = stop; exit_reason = "stop"
            else:
                exit_price = close; exit_reason = "close"
            pnl = (exit_price - entry_price) / entry_price * 100
        else:
            target = entry_price * (1 - TARGET_PCT / 100)
            stop = entry_price * (1 + STOP_PCT / 100)
            if low <= target:
                exit_price = target; exit_reason = "target"
            elif high >= stop:
                exit_price = stop; exit_reason = "stop"
            else:
                exit_price = close; exit_reason = "close"
            pnl = (entry_price - exit_price) / entry_price * 100

        opt_pnl = max(min(pnl * 18, 45), -45) - 0.15
        trades.append({
            "symbol": symbol, "entry_date": str(date), "exit_date": str(next_dates[0]),
            "action": action, "entry_price": round(entry_price, 2), "exit_price": round(exit_price, 2),
            "pnl_pct": round(pnl, 2), "win": pnl > 0, "exit_reason": exit_reason,
            "option_pnl_pct": round(opt_pnl, 2), "premium_rs": int(CAPITAL * 0.05),
            "option_pnl_rs": int(int(CAPITAL * 0.05) * opt_pnl / 100),
            "hm_rsi9": round(float(last["RSI9"]), 1),
            "hm_speed": round(float(last["Speed"]), 1),
            "hm_strength": round(float(last["Strength"]), 1),
        })
    return trades


def summary(trades):
    n = len(trades)
    if n == 0: return {"total_trades": 0}
    wins = [t for t in trades if t["win"]]
    wr = len(wins) / n * 100
    compound = 1.0
    for t in trades: compound *= (1 + t["pnl_pct"] / 100)
    return {"total_trades": n, "win_rate": round(wr, 1),
            "avg_pnl_pct": round(sum(t["pnl_pct"] for t in trades) / n, 2),
            "avg_win_pct": round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else 0,
            "avg_loss_pct": round(sum(t["pnl_pct"] for t in trades if not t["win"]) / max(len(trades) - len(wins), 1), 2),
            "max_loss_pct": round(min(t["pnl_pct"] for t in trades), 2),
            "compound_return_pct": round((compound - 1) * 100, 2),
            "total_option_pnl_rs": sum(t.get("option_pnl_rs", 0) for t in trades)}


# ─── Backtest: EMA+HA + Cross HM filter ───

def backtest_combined_cross(symbol, period="3mo"):
    """EMA+HA entry, Cross HM must agree (same candle)."""
    df = fetch_hourly(symbol, period)
    if df.empty or len(df) < 100: return []
    df = compute_ema_ha(df)
    df = compute_hm_hourly(df)
    df = df.iloc[30:].copy()
    trades = []
    for date, group in df.groupby(df.index.date):
        if len(group) < 2: continue
        last = group.iloc[-1]
        ema_bull = last["EMA_10"] > last["EMA_20"]
        ha_bull = last["HA_Close"] > last["HA_Open"]
        if ema_bull and ha_bull:
            action = "BUY"
        elif not ema_bull and not ha_bull:
            action = "SELL"
        else:
            continue
        cross_buy = bool(last["Cross_Buy"])
        cross_sell = bool(last["Cross_Sell"])
        if action == "BUY" and not cross_buy:
            continue
        if action == "SELL" and not cross_sell:
            continue
        entry_price = float(last["Close"])
        next_dates = [d for d in df.groupby(df.index.date).groups.keys() if d > date]
        if not next_dates: continue
        next_day = df[df.index.date == next_dates[0]]
        if next_day.empty: continue
        high, low, close = float(next_day["High"].max()), float(next_day["Low"].min()), float(next_day["Close"].iloc[-1])
        if action == "BUY":
            target = entry_price * (1 + TARGET_PCT / 100)
            stop = entry_price * (1 - STOP_PCT / 100)
            if high >= target: exit_price = target; exit_reason = "target"
            elif low <= stop: exit_price = stop; exit_reason = "stop"
            else: exit_price = close; exit_reason = "close"
            pnl = (exit_price - entry_price) / entry_price * 100
        else:
            target = entry_price * (1 - TARGET_PCT / 100)
            stop = entry_price * (1 + STOP_PCT / 100)
            if low <= target: exit_price = target; exit_reason = "target"
            elif high >= stop: exit_price = stop; exit_reason = "stop"
            else: exit_price = close; exit_reason = "close"
            pnl = (entry_price - exit_price) / entry_price * 100
        opt_pnl = max(min(pnl * 18, 45), -45) - 0.15
        trades.append({"symbol": symbol, "entry_date": str(date), "exit_date": str(next_dates[0]),
            "action": action, "entry_price": round(entry_price, 2), "exit_price": round(exit_price, 2),
            "pnl_pct": round(pnl, 2), "win": pnl > 0, "exit_reason": exit_reason,
            "option_pnl_pct": round(opt_pnl, 2), "premium_rs": int(CAPITAL * 0.05),
            "option_pnl_rs": int(int(CAPITAL * 0.05) * opt_pnl / 100)})
    return trades


# ─── Backtest: Cross HM standalone ───

def backtest_cross_standalone(symbol, period="3mo"):
    df = fetch_hourly(symbol, period)
    if df.empty or len(df) < 100: return []
    df = compute_hm_hourly(df)
    df = df.iloc[30:].copy()
    trades = []
    for date, group in df.groupby(df.index.date):
        if len(group) < 2: continue
        last = group.iloc[-1]
        if last["Cross_Buy"]: action = "BUY"
        elif last["Cross_Sell"]: action = "SELL"
        else: continue
        entry_price = float(last["Close"])
        next_dates = [d for d in df.groupby(df.index.date).groups.keys() if d > date]
        if not next_dates: continue
        next_day = df[df.index.date == next_dates[0]]
        if next_day.empty: continue
        high, low, close = float(next_day["High"].max()), float(next_day["Low"].min()), float(next_day["Close"].iloc[-1])
        if action == "BUY":
            target = entry_price * (1 + TARGET_PCT / 100)
            stop = entry_price * (1 - STOP_PCT / 100)
            if high >= target: exit_price = target; exit_reason = "target"
            elif low <= stop: exit_price = stop; exit_reason = "stop"
            else: exit_price = close; exit_reason = "close"
            pnl = (exit_price - entry_price) / entry_price * 100
        else:
            target = entry_price * (1 - TARGET_PCT / 100)
            stop = entry_price * (1 + STOP_PCT / 100)
            if low <= target: exit_price = target; exit_reason = "target"
            elif high >= stop: exit_price = stop; exit_reason = "stop"
            else: exit_price = close; exit_reason = "close"
            pnl = (entry_price - exit_price) / entry_price * 100
        opt_pnl = max(min(pnl * 18, 45), -45) - 0.15
        trades.append({"symbol": symbol, "entry_date": str(date), "exit_date": str(next_dates[0]),
            "action": action, "entry_price": round(entry_price, 2), "exit_price": round(exit_price, 2),
            "pnl_pct": round(pnl, 2), "win": pnl > 0, "exit_reason": exit_reason,
            "option_pnl_pct": round(opt_pnl, 2), "premium_rs": int(CAPITAL * 0.05),
            "option_pnl_rs": int(int(CAPITAL * 0.05) * opt_pnl / 100)})
    return trades


if __name__ == "__main__":
    print("=" * 120)
    print("  HM CROSSOVER: Speed(EMA3) crosses Strength(WMA21)")
    print("  A=EMA+HA | B= +HM filter | C=HM orig alone | D= +Cross HM | E=Cross HM alone")
    print("  All on hourly 3mo | Exit: 0.8% target / 0.3% stop")
    print("=" * 120)

    all_b, all_c, all_h, all_d, all_e = [], [], [], [], []
    per_b, per_c, per_h, per_d, per_e = {}, {}, {}, {}, {}

    for sym in TOP20:
        sys.stdout.write(f"\n  {sym['name']:<14}... "); sys.stdout.flush()
        b = backtest_baseline(sym["symbol"])
        c = backtest_combined(sym["symbol"])
        h = backtest_hm_standalone(sym["symbol"])
        d = backtest_combined_cross(sym["symbol"])
        e = backtest_cross_standalone(sym["symbol"])
        per_b[sym["name"]]=b; all_b.extend(b); per_c[sym["name"]]=c; all_c.extend(c)
        per_h[sym["name"]]=h; all_h.extend(h); per_d[sym["name"]]=d; all_d.extend(d)
        per_e[sym["name"]]=e; all_e.extend(e)
        sb=summary(b); sc=summary(c); sh=summary(h); sd=summary(d); se=summary(e)
        if sb["total_trades"]: sys.stdout.write(f"A{sb['total_trades']:>3}tr C{sb['compound_return_pct']:>+6.2f}%")
        if sc["total_trades"]: sys.stdout.write(f" | B{sc['total_trades']:>3}tr C{sc['compound_return_pct']:>+6.2f}%")
        if sh["total_trades"]: sys.stdout.write(f" | C{sh['total_trades']:>3}tr C{sh['compound_return_pct']:>+6.2f}%")
        if sd["total_trades"]: sys.stdout.write(f" | D{sd['total_trades']:>3}tr C{sd['compound_return_pct']:>+6.2f}%")
        if se["total_trades"]: sys.stdout.write(f" | E{se['total_trades']:>3}tr C{se['compound_return_pct']:>+6.2f}%")

    print(f"\n\n{'='*120}")
    print(f"  COMPANY-WISE: All 5 Variants")
    print(f"{'='*120}")
    print(f"  {'Symbol':<14} {'A-Tr':>4}{'A-WR':>6}{'A-Cmpd':>8} {'B-Tr':>4}{'B-WR':>6}{'B-Cmpd':>8} {'C-Tr':>4}{'C-WR':>6}{'C-Cmpd':>8} {'D-Tr':>4}{'D-WR':>6}{'D-Cmpd':>8} {'E-Tr':>4}{'E-WR':>6}{'E-Cmpd':>8}")
    print(f"  {'-'*110}")
    def s(d):
        r = summary(d[sym["name"]])
        return r if r["total_trades"] else {"total_trades":0,"win_rate":0,"compound_return_pct":0,"max_loss_pct":0}
    for sym in TOP20:
        b,c,h,d,e = s(per_b), s(per_c), s(per_h), s(per_d), s(per_e)
        print(f"  {sym['name']:<14} {b['total_trades']:>4}{b['win_rate']:>4.1f}%{b['compound_return_pct']:>7.2f}% {c['total_trades']:>4}{c['win_rate']:>4.1f}%{c['compound_return_pct']:>7.2f}% {h['total_trades']:>4}{h['win_rate']:>4.1f}%{h['compound_return_pct']:>7.2f}% {d['total_trades']:>4}{d['win_rate']:>4.1f}%{d['compound_return_pct']:>7.2f}% {e['total_trades']:>4}{e['win_rate']:>4.1f}%{e['compound_return_pct']:>7.2f}%")

    def t(d): return summary(d)
    bb,bc,bh,bd,be = t(all_b), t(all_c), t(all_h), t(all_d), t(all_e)
    print(f"  {'-'*110}")
    print(f"  {'TOTAL':<14} {bb['total_trades']:>4}{bb['win_rate']:>5.1f}%{bb['compound_return_pct']:>7.2f}% {bc['total_trades']:>4}{bc['win_rate']:>5.1f}%{bc['compound_return_pct']:>7.2f}% {bh['total_trades']:>4}{bh['win_rate']:>5.1f}%{bh['compound_return_pct']:>7.2f}% {bd['total_trades']:>4}{bd['win_rate']:>5.1f}%{bd['compound_return_pct']:>7.2f}% {be['total_trades']:>4}{be['win_rate']:>5.1f}%{be['compound_return_pct']:>7.2f}%")

    variants = [("A", per_b), ("B", per_c), ("C", per_h), ("D", per_d), ("E", per_e)]

    def safe_compound(data, sym):
        r = summary(data[sym])
        return r.get("compound_return_pct", -999) if r.get("total_trades", 0) > 0 else -999

    best_counts = {}
    for sym in TOP20:
        best_v = max(variants, key=lambda x: safe_compound(x[1], sym["name"]))
        if safe_compound(best_v[1], sym["name"]) > -999:
            best_counts[best_v[0]] = best_counts.get(best_v[0], 0) + 1

    def fmt_r(r):
        if r.get("total_trades", 0) == 0: return f"{'':>4}tr | {'':>5} | {'':>9}"
        return f"{r['total_trades']:>4}tr | WR {r['win_rate']:>5.1f}% | Cmpd {r['compound_return_pct']:>+8.2f}%"

    print(f"\n{'='*120}")
    print(f"  BOTTOM LINE")
    print(f"{'='*120}")
    print(f"  A (EMA+HA):         {fmt_r(bb)} | Best: {best_counts.get('A',0)}/20")
    print(f"  B (+Orig HM filter): {fmt_r(bc)} | Best: {best_counts.get('B',0)}/20")
    print(f"  C (Orig HM alone):  {fmt_r(bh)} | Best: {best_counts.get('C',0)}/20")
    print(f"  D (+Cross HM filter):{fmt_r(bd)} | Best: {best_counts.get('D',0)}/20")
    print(f"  E (Cross HM alone): {fmt_r(be)} | Best: {best_counts.get('E',0)}/20")
