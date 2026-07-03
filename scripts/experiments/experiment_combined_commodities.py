"""Experiment: Combined HA + HM + EMA Crossover for commodity trend riding."""
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

# ── Indicator helpers ──
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

def compute_all_indicators(df):
    d = df.copy()
    # EMA
    d["EMA_10"] = d["Close"].ewm(span=10, adjust=False).mean()
    d["EMA_20"] = d["Close"].ewm(span=20, adjust=False).mean()
    # HA
    ha = compute_heikin_ashi(d)
    d["HA_Close"] = ha["HA_Close"]
    d["HA_Open"] = ha["HA_Open"]
    d["HA_green"] = d["HA_Close"] >= d["HA_Open"]
    # HM
    d["RSI9"] = rsi9(d["Close"])
    d["Speed"] = d["RSI9"].ewm(span=3, adjust=False).mean()
    d["Strength"] = wma(d["RSI9"], 21)
    return d

def hm_bullish(row):
    """HM: Strength below both Speed and RSI9 = bullish."""
    if pd.isna(row["Strength"]) or pd.isna(row["Speed"]) or pd.isna(row["RSI9"]):
        return False
    return row["Strength"] < row["Speed"] and row["Strength"] < row["RSI9"]

def hm_bearish(row):
    """HM: Strength above both Speed and RSI9 = bearish."""
    if pd.isna(row["Strength"]) or pd.isna(row["Speed"]) or pd.isna(row["RSI9"]):
        return False
    return row["Strength"] > row["Speed"] and row["Strength"] > row["RSI9"]

def combined_signal(df, i):
    """2/3 majority signal: HA trend + EMA crossover + HM."""
    if i < 22:
        return 0  # neutral
    row = df.iloc[i]
    
    ha_bull = bool(row["HA_green"])
    ha_bear = not ha_bull
    ema_bull = row["EMA_10"] > row["EMA_20"]
    ema_bear = row["EMA_10"] < row["EMA_20"]
    hm_bull = hm_bullish(row)
    hm_bear = hm_bearish(row)
    
    bull_votes = sum([ha_bull, ema_bull, hm_bull])
    bear_votes = sum([ha_bear, ema_bear, hm_bear])
    
    if bull_votes >= 2:
        return 1  # bullish
    elif bear_votes >= 2:
        return -1  # bearish
    return 0

def backtest_combined(df, stop_pct=1.5, trail_pct=0.8, exit_on_flip=False):
    """Backtest combined 2/3 signal strategy.
    
    Entry: 2/3 indicators agree on direction.
    Exit: trailing stop, or optionally when 2/3 flip against.
    """
    df = compute_all_indicators(df)
    
    trades = []
    position = None
    entry_price = 0
    entry_idx = 0
    peak_price = 0
    trail_active = False
    
    for i in range(22, len(df)):
        sig = combined_signal(df, i)
        current_price = float(df["Close"].iloc[i])
        low = float(df["Low"].iloc[i])
        high = float(df["High"].iloc[i])
        
        if position is None:
            if sig == 1 and i > 22:  # BUY
                entry_price = current_price
                entry_idx = i
                peak_price = entry_price
                trail_active = False
                position = {"entry": entry_price, "entry_idx": i, "action": "BUY", "sig_at_entry": sig}
            elif sig == -1 and i > 22:  # SELL (short)
                entry_price = current_price
                entry_idx = i
                peak_price = entry_price
                trail_active = False
                position = {"entry": entry_price, "entry_idx": i, "action": "SELL", "sig_at_entry": sig}
        
        else:
            if position["action"] == "BUY":
                # Track peak
                if current_price > peak_price:
                    peak_price = current_price
                    if peak_price / entry_price - 1 >= 0.01:  # 1% profit → activate trailing
                        trail_active = True
                
                # Stop loss check
                stop_price = entry_price * (1 - stop_pct / 100)
                if low <= stop_price:
                    exit_price = stop_price
                    pnl = round((exit_price / entry_price - 1) * 100, 2)
                    trades.append({**position, "exit": exit_price, "pnl_pct": pnl, "exit_reason": f"stop_{stop_pct}pct"})
                    position = None
                    continue
                
                # Trailing stop
                if trail_active:
                    trail_stop = peak_price * (1 - trail_pct / 100)
                    if low <= trail_stop:
                        exit_price = trail_stop
                        pnl = round((exit_price / entry_price - 1) * 100, 2)
                        trades.append({**position, "exit": exit_price, "pnl_pct": pnl, "exit_reason": f"trail_{trail_pct}pct"})
                        position = None
                        continue
                
                # Exit on flip
                if exit_on_flip and sig <= -1:  # 2/3 bearish → exit long
                    exit_price = current_price
                    pnl = round((exit_price / entry_price - 1) * 100, 2)
                    trades.append({**position, "exit": exit_price, "pnl_pct": pnl, "exit_reason": "flip_bear"})
                    position = None
                    continue
            
            elif position["action"] == "SELL":
                low_price = entry_price  # For short: track lowest
                if current_price < low_price:
                    low_price = current_price
                # For short, we track the "peak" in reverse
                # Simplified: just use stop loss for shorts
                stop_price = entry_price * (1 + stop_pct / 100)
                if high >= stop_price:
                    exit_price = stop_price
                    pnl = round((entry_price / exit_price - 1) * 100, 2)
                    trades.append({**position, "exit": exit_price, "pnl_pct": pnl, "exit_reason": f"stop_{stop_pct}pct"})
                    position = None
                    continue
                
                if exit_on_flip and sig >= 1:  # 2/3 bullish → exit short
                    exit_price = current_price
                    pnl = round((entry_price / exit_price - 1) * 100, 2)
                    trades.append({**position, "exit": exit_price, "pnl_pct": pnl, "exit_reason": "flip_bull"})
                    position = None
                    continue
    
    # Close open at end
    if position is not None:
        exit_price = float(df["Close"].iloc[-1])
        if position["action"] == "BUY":
            pnl = round((exit_price / position["entry"] - 1) * 100, 2)
        else:
            pnl = round((position["entry"] / exit_price - 1) * 100, 2)
        trades.append({**position, "exit": exit_price, "pnl_pct": pnl, "exit_reason": "end_data"})
    
    if not trades:
        return {"trades": 0, "win_rate": 0, "avg_pnl": 0, "compound": 0, "total_pnl": 0}
    
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    
    compound = 1.0
    for t in trades:
        compound *= (1 + t["pnl_pct"] / 100)
    compound_pct = round((compound - 1) * 100, 2)
    
    reasons = defaultdict(int)
    for t in trades:
        r = t.get("exit_reason", "unknown")
        reasons[r] += 1
    
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
        "exit_reasons": dict(reasons),
    }

from collections import defaultdict

# ── Run experiment with multiple variants ──
print(f"╔{'═'*80}╗")
print(f"║  Combined Strategy: HA + HM + EMA Crossover (2/3 majority) — Commodities")
print(f"║  Entry: 2/3 indicators agree | Exit: trailing stop + optional signal flip")
print(f"╚{'═'*80}╝")

variants = [
    {"name": "Trail0.5_FlipOFF", "stop": 1.5, "trail": 0.5, "flip": False},
    {"name": "Trail1.0_FlipOFF", "stop": 2.0, "trail": 1.0, "flip": False},
    {"name": "Trail0.5_FlipON",  "stop": 1.5, "trail": 0.5, "flip": True},
    {"name": "Trail1.0_FlipON",  "stop": 2.0, "trail": 1.0, "flip": True},
    {"name": "NoTrail_FlipON",   "stop": 2.0, "trail": 99,  "flip": True},  # no trail, exit on flip
    {"name": "NoTrail_FlipOFF",  "stop": 1.5, "trail": 99,  "flip": False}, # stop only
]

for key, c in COMMODITIES.items():
    print(f"\n{'═'*80}")
    print(f"  {c['name']} ({c['symbol']})")
    print(f"{'═'*80}")
    
    df = fetch_data(c["symbol"], "1h", "3mo")
    if df.empty or len(df) < 100:
        print(f"  ⚠ No data")
        continue
    print(f"  Data: {len(df)} hourly candles ({pd.Timestamp(df.index[-1]).strftime('%d %b')} latest)")
    
    for v in variants:
        bt = backtest_combined(df.copy(), stop_pct=v["stop"], trail_pct=v["trail"], exit_on_flip=v["flip"])
        print(f"\n  [{v['name']:<18}] ", end="")
        if bt["trades"] > 0:
            print(f"Trades: {bt['trades']:>3} | WR: {bt['win_rate']:>5.1f}% | "
                  f"Avg: {bt['avg_pnl']:>+6.2f}% | Cmpd: {bt['compound']:>+8.2f}% | "
                  f"Best: {bt['max_win']:>+5.2f}% / Worst: {bt['max_loss']:>+5.2f}% | "
                  f"Exits: {bt['exit_reasons']}")
        else:
            print(f"0 trades")
    
    # Today's combined signal
    df_sig = compute_all_indicators(df.copy())
    if len(df_sig) > 22:
        i = len(df_sig) - 1
        sig = combined_signal(df_sig, i)
        row = df_sig.iloc[i]
        ha_dir = "🟢" if row["HA_green"] else "🔴"
        ema_dir = "🟢" if row["EMA_10"] > row["EMA_20"] else "🔴"
        hm_dir = "🟢" if hm_bullish(row) else ("🔴" if hm_bearish(row) else "⚪")
        
        sig_text = {1: "🟢 BULLISH (2/3)", -1: "🔴 BEARISH (2/3)", 0: "⚪ MIXED (≤1)"}
        print(f"\n  TODAY'S COMBINED SIGNAL: {sig_text.get(sig, '?')}")
        print(f"  Votes: HA={ha_dir}  EMA={ema_dir}  HM={hm_dir}  |  "
              f"Close=${float(row['Close']):.2f}  RSI9={float(row['RSI9']):.2f}  "
              f"Speed={float(row['Speed']):.2f}  Strength={float(row['Strength']):.2f}")
        print(f"  EMA10=${float(row['EMA_10']):.2f}  EMA20=${float(row['EMA_20']):.2f}  "
              f"HA_Open=${float(row['HA_Open']):.2f}  HA_Close=${float(row['HA_Close']):.2f}")

print(f"\n{'═'*80}")
print(f"  BEST CONFIG PER COMMODITY:")
print(f"{'═'*80}")
