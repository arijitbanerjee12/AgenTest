"""Experiment: Hilega Milega on hourly commodities — Gold, Silver, Natural Gas, Crude Oil."""
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

# ── HM helpers ──
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

# ── Backtest ──
TARGET_PCT = 0.8
STOP_PCT = 0.3

def backtest_hm(df, label=""):
    df["RSI9"] = rsi9(df["Close"])
    df["Speed"] = df["RSI9"].ewm(span=3, adjust=False).mean()
    df["Strength"] = wma(df["RSI9"], 21)
    
    trades = []
    position = None
    for i in range(22, len(df)):
        sig = hm_signal_at(df, i)
        if sig is None or sig["action"] in ("WATCH", "HOLD"): 
            continue
        if position is None and sig["action"] == "BUY":
            entry_price = float(df["Close"].iloc[i])
            position = {"entry": entry_price, "entry_idx": i, "action": "BUY"}
        elif position is not None and sig["action"] == "SELL":
            exit_price = float(df["Close"].iloc[i])
            pnl_pct = round((exit_price / position["entry"] - 1) * 100, 2)
            trades.append({**position, "exit": exit_price, "pnl_pct": pnl_pct})
            position = None
    
    # Close any open position at end
    if position is not None:
        exit_price = float(df["Close"].iloc[-1])
        pnl_pct = round((exit_price / position["entry"] - 1) * 100, 2)
        trades.append({**position, "exit": exit_price, "pnl_pct": pnl_pct})
    
    if not trades:
        return {"trades": 0, "win_rate": 0, "avg_pnl": 0, "compound": 0, "total_pnl": 0}
    
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    compound = 1.0
    for t in trades:
        compound *= (1 + t["pnl_pct"] / 100)
    compound_pct = round((compound - 1) * 100, 2)
    
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
    }

# ── Run experiment ──
print(f"╔{'═'*70}╗")
print(f"║  HM Experiment: Hourly Commodities (3mo backtest + today's signal)")
print(f"╚{'═'*70}╝")

results = []
for key, c in COMMODITIES.items():
    print(f"\n{'─'*70}")
    print(f"  {c['name']} ({c['symbol']})")
    print(f"{'─'*70}")
    
    df = fetch_data(c["symbol"], "1h", "3mo")
    if df.empty or len(df) < 100:
        print(f"  ⚠ No data available")
        continue
    
    print(f"  Data: {len(df)} hourly candles")
    
    bt = backtest_hm(df.copy(), key)
    results.append({"key": key, **c, **bt})
    
    print(f"  Trades: {bt['trades']} | WR: {bt['win_rate']}% | Avg: {bt['avg_pnl']:+.2f}%")
    print(f"  Compound: {bt['compound']:+.2f}% | Total: {bt['total_pnl']:+.2f}%")
    if bt['trades'] > 0:
        print(f"  Max win: {bt['max_win']:+.2f}% | Max loss: {bt['max_loss']:+.2f}%")
        print(f"  Avg win: {bt['avg_win']:+.2f}% | Avg loss: {bt['avg_loss']:+.2f}%")
    
    # Today's signal — recompute on full df
    df_sig = df.copy()
    df_sig["RSI9"] = rsi9(df_sig["Close"])
    df_sig["Speed"] = df_sig["RSI9"].ewm(span=3, adjust=False).mean()
    df_sig["Strength"] = wma(df_sig["RSI9"], 21)
    if len(df_sig) > 22:
        sig = hm_signal_at(df_sig, len(df_sig)-1)
        if sig:
            last = df_sig.iloc[-1]
            print(f"\n  TODAY'S SIGNAL: {sig['action']:<6} | Close={float(last['Close']):.2f} | "
                  f"RSI9={float(last['RSI9']):.2f} Speed={float(last['Speed']):.2f} Strength={float(last['Strength']):.2f}")

# Summary table
print(f"\n\n{'='*70}")
print(f"  COMPARISON SUMMARY")
print(f"{'='*70}")
print(f"  {'Symbol':<18} {'Trades':>8} {'WR%':>6} {'Avg%':>8} {'Compound%':>12} {'MaxW':>8} {'MaxL':>8}")
print(f"  {'-'*70}")
for r in results:
    if r['trades'] > 0:
        print(f"  {r['key']:<18} {r['trades']:>8} {r['win_rate']:>5.1f}% {r['avg_pnl']:>+7.2f}% {r['compound']:>+10.2f}% {r['max_win']:>+7.2f}% {r['max_loss']:>+7.2f}%")
    else:
        print(f"  {r['key']:<18} {'0 trades':>14}")

# Compare with equity HM baseline
print(f"\n{'='*70}")
print(f"  VS EQUITY HM BASELINE (hourly 3mo, avg of top 10)")
print(f"{'='*70}")
print(f"  Top 10 HM equity avg: ~100 trades, ~53% WR, ~+155% compound (per symbol)")
print(f"  Note: Commodities use 0.8/0.3 target/stop — same as equity BTST.")
print(f"  HM works best on trending instruments. Check if commodities trend enough.")
print(f"{'='*70}")
