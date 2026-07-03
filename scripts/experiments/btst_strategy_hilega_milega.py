"""BTST Strategy #6 — Hilega Milega (by NK Sir / Nitish Kumar)

Original TradingView + Chartink logic, adapted for BTST (next-day close).

Three lines:
  BLACK (Strength) = RSI(9)
  GREEN (Price/Speed) = EMA(RSI(9), 3)
  RED (Volume) = WMA(RSI(9), 21)

Original entry logic:
  SELL = RED (WMA21) is above BOTH GREEN (EMA3) and BLACK (RSI9)
  BUY  = RED (WMA21) is below BOTH GREEN (EMA3) and BLACK (RSI9)

Chartink screening conditions (for filter):
  RSI(9) >= 50, WMA(RSI9,21) <= 50, EMA(RSI9,3) >= 50, EMA(RSI9,3) < RSI(9)

We test 3 signal variants + exit at next-day close (no SL).
"""
from __future__ import annotations
import sys
import pandas as pd
import numpy as np
import yfinance as yf

TOP10 = [
    {"name":"HDFCLIFE","symbol":"HDFCLIFE.NS","category":"large_cap"},
    {"name":"M&M","symbol":"M&M.NS","category":"large_cap"},
    {"name":"BEL","symbol":"BEL.NS","category":"large_cap"},
    {"name":"SBIN","symbol":"SBIN.NS","category":"large_cap"},
    {"name":"JSWSTEEL","symbol":"JSWSTEEL.NS","category":"large_cap"},
    {"name":"ICICIBANK","symbol":"ICICIBANK.NS","category":"large_cap"},
    {"name":"BANKNIFTY","symbol":"^NSEBANK","category":"index"},
    {"name":"HDFCBANK","symbol":"HDFCBANK.NS","category":"large_cap"},
    {"name":"BHARTIARTL","symbol":"BHARTIARTL.NS","category":"large_cap"},
    {"name":"NIFTY","symbol":"^NSEI","category":"index"},
]
CAPITAL = 100_000

# ─── helpers ───

def fetch(symbol, period="6mo"):
    df = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
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


def wma(series, length):
    """Linearly weighted moving average (most recent = weight length)."""
    weights = np.arange(1, length + 1)
    def _wma(arr):
        if len(arr) < length: return np.nan
        return np.dot(arr, weights) / weights.sum()
    return series.rolling(length).apply(_wma, raw=True)


def compute_lines(df):
    df["RSI9"] = rsi9(df["Close"])
    df["Speed"] = df["RSI9"].ewm(span=3, adjust=False).mean()
    df["Strength"] = wma(df["RSI9"], 21)
    return df


# ─── Signal variants ───

def signal_original(df):
    """Original Hilega Milega: RED(WMA21) above/below BOTH GREEN(EMA3) and BLACK(RSI9)"""
    buy = (df["Strength"] < df["Speed"]) & (df["Strength"] < df["RSI9"])
    sell = (df["Strength"] > df["Speed"]) & (df["Strength"] > df["RSI9"])
    return buy, sell


def signal_cross(df):
    """Crossover variant: Speed (EMA3) crosses above/below Strength (WMA21)"""
    buy = (df["Speed"] > df["Strength"]) & (df["Speed"].shift(1) <= df["Strength"].shift(1))
    sell = (df["Speed"] < df["Strength"]) & (df["Speed"].shift(1) >= df["Strength"].shift(1))
    return buy, sell


def signal_chartink(df):
    """Chartink screener conditions as entry signal + crossover confirmation"""
    cond = (df["RSI9"] >= 50) & (df["Strength"] <= 50) & (df["Speed"] >= 50) & (df["Speed"] < df["RSI9"])
    # Also require speed > strength for buy, speed < strength for sell
    buy = cond & (df["Speed"] > df["Strength"])
    sell = cond & (df["Speed"] < df["Strength"])
    return buy, sell


# ─── backtest ───

def backtest(symbol, signal_fn, period="6mo"):
    df = fetch(symbol, period)
    if df.empty or len(df) < 30: return []
    df = compute_lines(df)
    df = df.iloc[25:].copy()  # warmup
    buy_sig, sell_sig = signal_fn(df)
    trades = []
    for i in range(len(df) - 1):
        t = df.iloc[i]
        nx = df.iloc[i + 1]
        if buy_sig.iloc[i]:
            action = "BUY"
        elif sell_sig.iloc[i]:
            action = "SELL"
        else:
            continue
        ep, xp = float(t["Close"]), float(nx["Close"])
        pnl = (xp - ep) / ep * 100 if action == "BUY" else (ep - xp) / ep * 100
        opt_pnl = max(min(pnl * 18, 45), -45) - 0.15
        trades.append({
            "symbol": symbol, "entry_date": str(df.index[i].date()), "exit_date": str(df.index[i+1].date()),
            "action": action, "entry_price": round(ep, 2), "exit_price": round(xp, 2),
            "pnl_pct": round(pnl, 2), "win": pnl > 0,
            "option_pnl_pct": round(opt_pnl, 2), "premium_rs": int(CAPITAL * 0.05),
            "option_pnl_rs": int(int(CAPITAL * 0.05) * opt_pnl / 100),
            "rsi9": round(float(t["RSI9"]), 1),
            "speed": round(float(t["Speed"]), 1),
            "strength": round(float(t["Strength"]), 1),
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

def ev(trades):
    n = len(trades)
    if n == 0: return 0
    wr = sum(1 for t in trades if t["win"]) / n
    aw = sum(t["pnl_pct"] for t in trades if t["win"]) / max(sum(1 for t in trades if t["win"]), 1)
    al = sum(t["pnl_pct"] for t in trades if not t["win"]) / max(sum(1 for t in trades if not t["win"]), 1)
    return round(wr * aw + (1 - wr) * al, 3)


SIGNALS = [
    ("Original HM", signal_original, "RED < GREEN & BLACK = BUY, RED > BOTH = SELL"),
    ("Cross HM", signal_cross, "Speed crosses Strength"),
    ("Chartink HM", signal_chartink, "RSI>=50, WMA<=50, EMA>=50, EMA<RSI"),
]

if __name__ == "__main__":
    for sname, sfunc, sdesc in SIGNALS:
        print("=" * 90)
        print(f"  HILEGA MILEGA — {sname}")
        print(f"  {sdesc}")
        print("=" * 90)
        all_trades, per_sym = [], {}
        for sym in TOP10:
            sys.stdout.write(f"  {sym['name']:<14}... "); sys.stdout.flush()
            t = backtest(sym["symbol"], sfunc); per_sym[sym["name"]] = t; all_trades.extend(t)
            s = summary(t)
            if s["total_trades"]:
                sys.stdout.write(f"{s['total_trades']:>3} tr | WR {s['win_rate']:>5.1f}% | EV {ev(t):>6.3f}% | Cmpd {s['compound_return_pct']:>7.2f}%")
            else:
                sys.stdout.write("0 trades")
            print()
        b = summary(all_trades)
        print(f"\n  {'Symbol':<14} {'Trades':>6} {'WR%':>6} {'EV%':>7} {'AvgPnL%':>8} {'Cmpd%':>8}")
        print(f"  {'-'*55}")
        for sym in sorted(TOP10, key=lambda s: ev(per_sym[s["name"]]), reverse=True):
            s = summary(per_sym[sym["name"]])
            if s["total_trades"]:
                print(f"  {sym['name']:<14} {s['total_trades']:>6} {s['win_rate']:>5.1f}% {ev(per_sym[sym['name']]):>6.3f}% {s['avg_pnl_pct']:>7.2f}% {s['compound_return_pct']:>7.2f}%")
        print(f"\n  BASKET: {b['total_trades']} tr | WR {b['win_rate']}% | EV {ev(all_trades)}% | Cmpd {b['compound_return_pct']}% | MaxLoss {b['max_loss_pct']}%")
        print()
