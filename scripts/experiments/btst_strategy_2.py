"""BTST Strategy #2 — Daily Momentum + Volume Breakout
Completely different from our EMA 10/20 + HA hourly system:

Signal generation on daily data:
  BUY  = Close > EMA(20) AND 5-day high AND Volume > 1.5x 20-day avg
  SELL = Close < EMA(20) AND 5-day low  AND Volume > 1.5x 20-day avg

Entry: at today's close
Exit:  at next day's close (BTST)
"""
from __future__ import annotations

import sys
import pandas as pd
import yfinance as yf

TOP10 = [
    {"name": "HDFCLIFE",  "symbol": "HDFCLIFE.NS",  "category": "large_cap"},
    {"name": "M&M",       "symbol": "M&M.NS",        "category": "large_cap"},
    {"name": "BEL",       "symbol": "BEL.NS",        "category": "large_cap"},
    {"name": "SBIN",      "symbol": "SBIN.NS",       "category": "large_cap"},
    {"name": "JSWSTEEL",  "symbol": "JSWSTEEL.NS",   "category": "large_cap"},
    {"name": "ICICIBANK", "symbol": "ICICIBANK.NS",  "category": "large_cap"},
    {"name": "BANKNIFTY", "symbol": "^NSEBANK",      "category": "index"},
    {"name": "HDFCBANK",  "symbol": "HDFCBANK.NS",   "category": "large_cap"},
    {"name": "BHARTIARTL","symbol": "BHARTIARTL.NS",  "category": "large_cap"},
    {"name": "NIFTY",     "symbol": "^NSEI",         "category": "index"},
]

CAPITAL = 100_000


def fetch_daily(symbol: str, period: str = "6mo") -> pd.DataFrame:
    df = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        return df
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def backtest(symbol: str, period: str = "6mo"):
    df = fetch_daily(symbol, period)
    if df.empty or len(df) < 30:
        return []

    df["EMA_20"] = df["Close"].ewm(span=20, adjust=False).mean()
    df["Vol_SMA"] = df["Volume"].rolling(20).mean()
    df["High_5"] = df["High"].rolling(5).max()
    df["Low_5"] = df["Low"].rolling(5).min()

    # BUY: close above EMA + 5-day high + volume > 1.5x
    df["Sig_Buy"] = (
        (df["Close"] > df["EMA_20"])
        & (df["Close"] >= df["High_5"].shift(1))   # highest close in 5 days
        & (df["Volume"] > 1.5 * df["Vol_SMA"])
    )

    # SELL: close below EMA + 5-day low + volume > 1.5x
    df["Sig_Sell"] = (
        (df["Close"] < df["EMA_20"])
        & (df["Close"] <= df["Low_5"].shift(1))
        & (df["Volume"] > 1.5 * df["Vol_SMA"])
    )

    trades = []
    for i in range(len(df) - 1):
        today = df.iloc[i]
        tomorrow = df.iloc[i + 1]

        if today["Sig_Buy"]:
            action = "BUY"
        elif today["Sig_Sell"]:
            action = "SELL"
        else:
            continue

        entry_price = float(today["Close"])
        exit_price = float(tomorrow["Close"])

        pnl = (exit_price - entry_price) / entry_price * 100 if action == "BUY" else (entry_price - exit_price) / entry_price * 100
        opt_pnl = max(min(pnl * 18, 45), -45) - 0.15
        premium = int(CAPITAL * 0.05)

        trades.append({
            "symbol": symbol,
            "entry_date": str(df.index[i].date()),
            "exit_date": str(df.index[i + 1].date()),
            "action": action,
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "pnl_pct": round(pnl, 2),
            "win": pnl > 0,
            "option_pnl_pct": round(opt_pnl, 2),
            "premium_rs": premium,
            "option_pnl_rs": int(premium * opt_pnl / 100),
            "vol_ratio": round(float(today["Volume"] / today["Vol_SMA"]), 2),
            "ema_20": round(float(today["EMA_20"]), 2),
        })
    return trades


def summary(trades):
    n = len(trades)
    if n == 0:
        return {"total_trades": 0}
    wins = [t for t in trades if t["win"]]
    wr = len(wins) / n * 100
    compound = 1.0
    for t in trades:
        compound *= (1 + t["pnl_pct"] / 100)
    return {
        "total_trades": n,
        "win_rate": round(wr, 1),
        "avg_pnl_pct": round(sum(t["pnl_pct"] for t in trades) / n, 2),
        "avg_win_pct": round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else 0,
        "avg_loss_pct": round(sum(t["pnl_pct"] for t in trades if not t["win"]) / max(len(trades) - len(wins), 1), 2),
        "max_loss_pct": round(min(t["pnl_pct"] for t in trades), 2),
        "compound_return_pct": round((compound - 1) * 100, 2),
        "total_option_pnl_rs": sum(t.get("option_pnl_rs", 0) for t in trades),
    }


def expected_value(trades):
    """Expected value = WR × avg_win + (1-WR) × avg_loss"""
    n = len(trades)
    if n == 0:
        return 0
    wr = sum(1 for t in trades if t["win"]) / n
    avg_win = sum(t["pnl_pct"] for t in trades if t["win"]) / max(sum(1 for t in trades if t["win"]), 1)
    avg_loss = sum(t["pnl_pct"] for t in trades if not t["win"]) / max(sum(1 for t in trades if not t["win"]), 1)
    return round(wr * avg_win + (1 - wr) * avg_loss, 3)


if __name__ == "__main__":
    print("=" * 80)
    print("  BTST Strategy #2 — Daily Momentum + Volume Breakout")
    print("  BUY  = Close > EMA(20) + 5-day high + Vol > 1.5x avg")
    print("  SELL = Close < EMA(20) + 5-day low  + Vol > 1.5x avg")
    print("  Exit = next-day close · No SL · No target")
    print("=" * 80)

    all_trades = []
    per_sym = {}

    for sym in TOP10:
        sys.stdout.write(f"  {sym['name']:<14} ({sym['symbol']})... ")
        sys.stdout.flush()
        trades = backtest(sym["symbol"])
        per_sym[sym["name"]] = trades
        all_trades.extend(trades)
        s = summary(trades)
        if s["total_trades"]:
            ev = expected_value(trades)
            sys.stdout.write(f"{s['total_trades']:>3} tr | WR {s['win_rate']:>5.1f}% | EV {ev:>6.3f}% | Cmpd {s['compound_return_pct']:>7.2f}%")
        else:
            sys.stdout.write("0 trades")
        print()

    print(f"\n{'='*80}")
    print(f"  PER-SYMBOL (sorted by Expected Value)")
    print(f"{'='*80}")
    print(f"  {'Symbol':<14} {'Trades':>6} {'WR%':>6} {'EV%':>7} {'AvgPnL%':>8} {'Cmpd%':>8} {'AvgWin%':>8} {'AvgLoss%':>8} {'MaxLoss%':>8}")
    print(f"  {'-'*73}")
    sorted_syms = sorted(TOP10, key=lambda s: expected_value(per_sym[s["name"]]), reverse=True)
    for sym in sorted_syms:
        s = summary(per_sym[sym["name"]])
        if s["total_trades"]:
            ev = expected_value(per_sym[sym["name"]])
            print(f"  {sym['name']:<14} {s['total_trades']:>6} {s['win_rate']:>5.1f}% {ev:>6.3f}% {s['avg_pnl_pct']:>7.2f}% {s['compound_return_pct']:>7.2f}% {s['avg_win_pct']:>7.2f}% {s['avg_loss_pct']:>7.2f}% {s['max_loss_pct']:>7.2f}%")
        else:
            print(f"  {sym['name']:<14}      0   N/A     N/A      N/A      N/A      N/A      N/A      N/A")

    b = summary(all_trades)
    ev_all = expected_value(all_trades)
    print(f"\n{'='*80}")
    print(f"  BASKET: {b['total_trades']} trades · WR {b['win_rate']}% · EV {ev_all}%")
    print(f"  Avg PnL: {b['avg_pnl_pct']}% · Compound: {b['compound_return_pct']}% · Max Loss: {b['max_loss_pct']}%")
    print(f"  Option P&L: ₹{b['total_option_pnl_rs']:,}")
    print(f"{'='*80}")

    print(f"\n{'='*55}")
    print(f"  COMPARISON")
    print(f"{'='*55}")
    print(f"  {'Metric':<24} {'Daily Brkout':>12} {'EMA+HA 0.8/0.3':>15}")
    print(f"  {'-'*51}")
    print(f"  {'Data':<24} {'Daily 6mo':>12} {'Hourly 3mo':>15}")
    print(f"  {'Trades':<24} {b['total_trades']:>12} {'~509':>15}")
    print(f"  {'Win Rate':<24} {b['win_rate']:>11.1f}% {'52.8%':>15}")
    print(f"  {'Expected Value':<24} {ev_all:>11.3f}% {'0.172%':>15}")
    print(f"  {'Compound':<24} {b['compound_return_pct']:>11.2f}% {'86.4%':>15}")
    print(f"  {'Max Loss':<24} {b['max_loss_pct']:>11.2f}% {'-1.96%':>15}")
    print(f"  {'='*51}")
