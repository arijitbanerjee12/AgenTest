"""BTST Strategy #2 — Bollinger Band Squeeze + Volume Breakout
Idea: After low-volatility squeeze, a high-volume breakout often continues next day.
Entry: BBW < 20-period avg (squeeze) + close breaks BB + volume > 1.5x avg
Exit:  Next day close
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import yfinance as yf

# ── Top 10 from our analysis ──
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
SLIPPAGE = 0.0015
OPTION_MULT = 18


def fetch_data(symbol: str, interval: str = "1h", period: str = "3mo") -> pd.DataFrame:
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df.empty:
        return df
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df


def bb_squeeze_breakout(df: pd.DataFrame, bb_period: int = 20, bb_std: float = 2.0) -> pd.DataFrame:
    """Compute Bollinger Bands, Band Width, Squeeze, and Breakout signals."""
    df = df.copy()
    df["BB_Mid"] = df["Close"].rolling(bb_period).mean()
    df["BB_Std"] = df["Close"].rolling(bb_period).std()
    df["BB_Upper"] = df["BB_Mid"] + bb_std * df["BB_Std"]
    df["BB_Lower"] = df["BB_Mid"] - bb_std * df["BB_Std"]
    df["BBW"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Mid"] * 100
    df["BBW_SMA"] = df["BBW"].rolling(bb_period).mean()
    df["Vol_SMA"] = df["Volume"].rolling(20).mean()

    # Squeeze: BBW < average BBW
    df["Squeeze"] = df["BBW"] < df["BBW_SMA"]

    # Breakout: close above upper BB or below lower BB
    df["Breakout_Up"] = df["Close"] > df["BB_Upper"]
    df["Breakout_Dn"] = df["Close"] < df["BB_Lower"]

    # Volume confirmation
    df["Vol_Confirm"] = df["Volume"] > 1.5 * df["Vol_SMA"]

    # Combined signal
    conditions = (
        df["Squeeze"]
        & df["Vol_Confirm"]
    )
    df["Sig_Buy"] = conditions & df["Breakout_Up"]
    df["Sig_Sell"] = conditions & df["Breakout_Dn"]
    return df


def backtest(symbol: str, period: str = "3mo", interval: str = "1h"):
    df = fetch_data(symbol, interval, period)
    if df.empty or len(df) < 50:
        return []

    df = bb_squeeze_breakout(df)
    df["date"] = df.index.date
    day_groups = list(df.groupby("date"))

    trades = []
    for i in range(len(day_groups) - 1):
        day_df = day_groups[i][1].sort_index()
        entry = day_df.iloc[-1]

        if entry["Sig_Buy"]:
            action, target_pct = "BUY", 1.0
        elif entry["Sig_Sell"]:
            action, target_pct = "SELL", 1.0
        else:
            continue

        entry_price = float(entry["Close"])
        next_day_df = day_groups[i + 1][1].sort_index()

        # Exit next day at close (BTST)
        exit_price = float(next_day_df["Close"].iloc[-1])

        if action == "BUY":
            pnl_pct = (exit_price - entry_price) / entry_price * 100
        else:
            pnl_pct = (entry_price - exit_price) / entry_price * 100

        opt_pnl = max(min(pnl_pct * OPTION_MULT, 45), -45) - SLIPPAGE * 100

        trades.append({
            "entry_date": str(day_groups[i][0]),
            "exit_date": str(day_groups[i + 1][0]),
            "action": action,
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "pnl_pct": round(pnl_pct, 2),
            "win": pnl_pct > 0,
            "option_pnl_pct": round(opt_pnl, 2),
            "bbw": round(float(entry["BBW"]), 2),
            "bbw_avg": round(float(entry["BBW_SMA"]), 2),
            "vol_ratio": round(float(entry["Volume"] / entry["Vol_SMA"]), 2),
        })
    return trades


def summary(trades: list[dict]) -> dict:
    n = len(trades)
    if n == 0:
        return {"total_trades": 0}
    wins = [t for t in trades if t["win"]]
    losses = [t for t in trades if not t["win"]]
    wr = len(wins) / n * 100
    total_pnl = sum(t["pnl_pct"] for t in trades)
    compound = 1.0
    for t in trades: compound *= (1 + t["pnl_pct"] / 100)
    opt_roi = sum(t["option_pnl_pct"] for t in trades) / CAPITAL * 100 * CAPITAL / CAPITAL
    total_opt = sum(t.get("option_pnl_pct", 0) for t in trades)
    opt_roi_pct = total_opt / CAPITAL * 100 if CAPITAL else 0
    avg_premium = CAPITAL * 0.05
    total_opt_rs = sum(int(avg_premium * t["option_pnl_pct"] / 100) for t in trades)

    return {
        "total_trades": n,
        "win_rate": round(wr, 1),
        "avg_pnl_pct": round(total_pnl / n, 2),
        "avg_win_pct": round(sum(t["pnl_pct"] for t in wins) / len(wins), 2) if wins else 0,
        "avg_loss_pct": round(sum(t["pnl_pct"] for t in losses) / len(losses), 2) if losses else 0,
        "max_loss_pct": round(min(t["pnl_pct"] for t in trades), 2),
        "compound_return_pct": round((compound - 1) * 100, 2),
        "total_option_pnl_rs": total_opt_rs,
        "best_symbol": "",  # filled later
    }


if __name__ == "__main__":
    print("=" * 70)
    print("  BTST Strategy #2 — Bollinger Squeeze + Volume Breakout")
    print("  Exit: next-day close (no SL, no target)")
    print("=" * 70)

    all_symbol_trades = {}
    all_trades_combined = []

    for sym in TOP10:
        sys.stdout.write(f"\n  {sym['name']} ({sym['symbol']})... ")
        sys.stdout.flush()
        trades = backtest(sym["symbol"])
        all_symbol_trades[sym["name"]] = trades
        all_trades_combined.extend(trades)
        s = summary(trades)
        if s["total_trades"] > 0:
            print(f"{s['total_trades']:>3} trades | WR {s['win_rate']:>5.1f}% | Avg {s['avg_pnl_pct']:>6.2f}% | Cmpd {s['compound_return_pct']:>7.2f}%")
        else:
            print("0 trades")

    print(f"\n{'='*70}")
    print(f"  PER-SYMBOL SUMMARY")
    print(f"{'='*70}")
    print(f"  {'Symbol':<14} {'Trades':>6} {'WR%':>6} {'AvgPnL%':>8} {'Cmpd%':>8} {'AvgWin%':>8} {'AvgLoss%':>8} {'MaxLoss%':>8}")
    print(f"  {'-'*66}")
    for sym in TOP10:
        s = summary(all_symbol_trades[sym["name"]])
        if s["total_trades"] > 0:
            print(f"  {sym['name']:<14} {s['total_trades']:>6} {s['win_rate']:>5.1f}% {s['avg_pnl_pct']:>7.2f}% {s['compound_return_pct']:>7.2f}% {s['avg_win_pct']:>7.2f}% {s['avg_loss_pct']:>7.2f}% {s['max_loss_pct']:>7.2f}%")

    basket = summary(all_trades_combined)
    print(f"\n{'='*70}")
    print(f"  BASKET (all 10 symbols): {basket['total_trades']} trades")
    print(f"  Win Rate:     {basket['win_rate']}%")
    print(f"  Avg PnL:      {basket['avg_pnl_pct']}%")
    print(f"  Compound:     {basket['compound_return_pct']}%")
    print(f"  Max Loss:     {basket['max_loss_pct']}%")
    print(f"  Option P&L:   ₹{basket['total_option_pnl_rs']:,}")
    print(f"{'='*70}")

    # Compare with current strategy
    print(f"\n  COMPARISON: BB Squeeze vs Current EMA+HA (0.8/0.3)")
    print(f"  {'Metric':<20} {'BB Squeeze':>12} {'EMA+HA 0.8/0.3':>15}")
    print(f"  {'-'*47}")
    print(f"  {'Total Trades':<20} {basket['total_trades']:>12} {'~550':>15}")
    print(f"  {'Win Rate':<20} {basket['win_rate']:>11.1f}% {53.7:>14.1f}%")
    print(f"  {'Avg PnL':<20} {basket['avg_pnl_pct']:>11.2f}% {0.15:>14.2f}%")
    print(f"  {'Compound':<20} {basket['compound_return_pct']:>11.2f}% {36.86:>14.2f}%")
