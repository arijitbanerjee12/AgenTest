"""BTST Strategy #4 — MACD (12,26,9) Crossover
BUY  = MACD line crosses above Signal line
SELL = MACD line crosses below Signal line
Exit = next-day close · Daily data · 6mo
"""
from __future__ import annotations
import sys
import pandas as pd
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


def fetch(symbol, period="6mo"):
    df = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
    if df.empty: return df
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def backtest(symbol, period="6mo"):
    df = fetch(symbol, period)
    if df.empty or len(df) < 30: return []
    exp12 = df["Close"].ewm(span=12, adjust=False).mean()
    exp26 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = exp12 - exp26
    df["Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["Histo"] = df["MACD"] - df["Signal"]
    df["Cross_Up"] = (df["Histo"] > 0) & (df["Histo"].shift(1) <= 0)
    df["Cross_Dn"] = (df["Histo"] < 0) & (df["Histo"].shift(1) >= 0)
    trades = []
    for i in range(len(df) - 1):
        t = df.iloc[i]; nx = df.iloc[i + 1]
        if t["Cross_Up"]: action = "BUY"
        elif t["Cross_Dn"]: action = "SELL"
        else: continue
        ep, xp = float(t["Close"]), float(nx["Close"])
        pnl = (xp - ep) / ep * 100 if action == "BUY" else (ep - xp) / ep * 100
        opt_pnl = max(min(pnl * 18, 45), -45) - 0.15
        trades.append({
            "symbol": symbol, "entry_date": str(df.index[i].date()), "exit_date": str(df.index[i+1].date()),
            "action": action, "entry_price": round(ep, 2), "exit_price": round(xp, 2),
            "pnl_pct": round(pnl, 2), "win": pnl > 0,
            "option_pnl_pct": round(opt_pnl, 2), "premium_rs": int(CAPITAL * 0.05),
            "option_pnl_rs": int(int(CAPITAL * 0.05) * opt_pnl / 100),
            "macd": round(float(t["MACD"]), 2), "signal": round(float(t["Signal"]), 2),
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


if __name__ == "__main__":
    print("=" * 80)
    print("  BTST Strategy #4 — MACD (12,26,9) Crossover")
    print("  BUY = MACD crosses above Signal | SELL = MACD crosses below Signal")
    print("  Exit = next-day close · Daily data · 6mo")
    print("=" * 80)
    all_trades, per_sym = [], {}
    for sym in TOP10:
        sys.stdout.write(f"  {sym['name']:<14} ({sym['symbol']})... "); sys.stdout.flush()
        t = backtest(sym["symbol"]); per_sym[sym["name"]] = t; all_trades.extend(t)
        s = summary(t)
        if s["total_trades"]:
            sys.stdout.write(f"{s['total_trades']:>3} tr | WR {s['win_rate']:>5.1f}% | EV {ev(t):>6.3f}% | Cmpd {s['compound_return_pct']:>7.2f}%")
        else:
            sys.stdout.write("0 trades")
        print()
    print(f"\n{'='*80}")
    print(f"  {'Symbol':<14} {'Trades':>6} {'WR%':>6} {'EV%':>7} {'AvgPnL%':>8} {'Cmpd%':>8} {'AvgWin%':>8} {'AvgLoss%':>8} {'MaxLoss%':>8}")
    print(f"  {'-'*73}")
    for sym in sorted(TOP10, key=lambda s: ev(per_sym[s["name"]]), reverse=True):
        s = summary(per_sym[sym["name"]])
        if s["total_trades"]:
            print(f"  {sym['name']:<14} {s['total_trades']:>6} {s['win_rate']:>5.1f}% {ev(per_sym[sym['name']]):>6.3f}% {s['avg_pnl_pct']:>7.2f}% {s['compound_return_pct']:>7.2f}% {s['avg_win_pct']:>7.2f}% {s['avg_loss_pct']:>7.2f}% {s['max_loss_pct']:>7.2f}%")
    b = summary(all_trades)
    print(f"\n  BASKET: {b['total_trades']} tr · WR {b['win_rate']}% · EV {ev(all_trades)}% · Cmpd {b['compound_return_pct']}% · MaxLoss {b['max_loss_pct']}% · Opt ₹{b['total_option_pnl_rs']:,}")
