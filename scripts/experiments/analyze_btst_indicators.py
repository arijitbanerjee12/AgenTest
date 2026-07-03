"""Analyze all BTST signals from yesterday — how each indicator performed."""
from pathlib import Path
import pandas as pd
import yfinance as yf

REPORTS = Path.home() / "Documents" / "Agentest_Reports"
file = REPORTS / "2026-06-21" / "BTST_TodaySignals_20260621_221225.xlsx"

df = pd.read_excel(file, header=None)

records = []
for i in range(3, 28):
    sym = str(df.iloc[i, 0]) if pd.notna(df.iloc[i, 0]) else None
    sig = str(df.iloc[i, 1]) if pd.notna(df.iloc[i, 1]) else None
    opt = str(df.iloc[i, 2]) if pd.notna(df.iloc[i, 2]) else ""
    close = df.iloc[i, 3]
    reason = str(df.iloc[i, 4]) if pd.notna(df.iloc[i, 4]) else ""
    ha_sig = str(df.iloc[i, 5]) if pd.notna(df.iloc[i, 5]) else ""
    ha_str = df.iloc[i, 6] if pd.notna(df.iloc[i, 6]) else 0
    vix = df.iloc[i, 7] if pd.notna(df.iloc[i, 7]) else ""
    vol = str(df.iloc[i, 8]) if pd.notna(df.iloc[i, 8]) else ""
    prem = df.iloc[i, 9] if pd.notna(df.iloc[i, 9]) else ""
    cat = str(df.iloc[i, 10]) if pd.notna(df.iloc[i, 10]) else ""

    if sym and sig:
        strategy = "HM" if "HM" in reason else "EMA+HA"
        # Ensure .NS suffix for NSE stocks (yfinance requirement)
        raw_sym = sym.replace(".NS", "").replace("^", "")
        if "^" in sym:
            yf_sym = sym
        elif ".NS" in sym:
            yf_sym = sym
        else:
            yf_sym = sym + ".NS"  # NSE stocks usually without suffix in Excel
        records.append({
            "name": raw_sym,
            "symbol": yf_sym,
            "signal": sig,
            "ha_signal": ha_sig,
            "ha_strength": ha_str,
            "reason": reason,
            "strategy": strategy,
            "close": close,
        })

print(f"Loaded {len(records)} BTST signals")

def get_movement(symbol):
    df2 = yf.download(symbol, period="2d", interval="15m", progress=False, auto_adjust=True)
    if df2.empty or len(df2) < 5:
        return None
    if isinstance(df2.columns, pd.MultiIndex):
        df2.columns = [c[0] for c in df2.columns]
    o = float(df2["Close"].iloc[0])
    l = float(df2["Close"].iloc[-1])
    lo = float(df2["Low"].min())
    hi = float(df2["High"].max())
    return {"open": o, "last": l, "pct": round((l/o - 1)*100, 2), "low": round((lo/o - 1)*100, 2), "high": round((hi/o - 1)*100, 2)}

# Fetch all movements
for r in records:
    m = get_movement(r["symbol"])
    if m:
        r["pct"] = m["pct"]
        r["low_pct"] = m["low"]
        r["high_pct"] = m["high"]
    else:
        r["pct"] = None

# Analysis by HA signal type
print("\n=== BY HA SIGNAL DIRECTION (EMA+HA only) ===")
ema = [r for r in records if r["strategy"] == "EMA+HA" and r["pct"] is not None]
for ha_type in ["strong_buy", "buy", "weak_buy", "weak_sell", "sell", "strong_sell", ""]:
    grp = [r for r in ema if r["ha_signal"] == ha_type]
    if not grp:
        continue
    label = ha_type if ha_type else "(no ha_signal)"
    avg = sum(r["pct"] for r in grp) / len(grp)
    correct = []
    for r in grp:
        if r["signal"] == "BUY":
            correct.append(r["pct"] > 0)
        elif r["signal"] == "SELL":
            correct.append(r["pct"] < 0)
        elif r["signal"] == "HOLD":
            correct.append(abs(r["pct"]) < 1.5)
        elif r["signal"] == "WATCH":
            correct.append(True)  # WATCH is neutral
        elif r["signal"] == "SKIP":
            correct.append(True)  # SKIP is neutral
    cr = sum(correct) / len(correct) * 100 if correct else 0
    print(f"\n  {label:<15} ({len(grp)} signals) | Avg day chg: {avg:+.2f}% | Accuracy: {cr:.0f}%")
    for r in grp:
        st = "✅" if (r["signal"] == "BUY" and r["pct"] > 0) or (r["signal"] == "SELL" and r["pct"] < 0) or (r["signal"] in ("HOLD","WATCH","SKIP") and abs(r["pct"]) < 1.5) else "❌"
        st = "✅" if r["signal"] in ("WATCH","SKIP") else st
        if r["ha_signal"] == "strong_buy":
            ha_label = "🟢STRONG_BUY"
        elif r["ha_signal"] == "buy":
            ha_label = "🟢BUY"
        elif r["ha_signal"] == "weak_buy":
            ha_label = "🟢weak_buy"
        elif r["ha_signal"] == "sell":
            ha_label = "🔴SELL"
        elif r["ha_signal"] == "weak_sell":
            ha_label = "🔴weak_sell"
        elif r["ha_signal"] == "strong_sell":
            ha_label = "🔴STRONG_SELL"
        else:
            ha_label = "⚪no_signal"
        print(f"    {st} {r['name']:<14} {r['signal']:<6} {ha_label:<20} HA_str={r['ha_strength']:<3} Chg={r['pct']:+.2f}%")

# Summary by final signal
print("\n\n=== BY FINAL SIGNAL ===")
for sig_type in ["BUY", "SELL", "HOLD", "WATCH", "SKIP"]:
    grp = [r for r in records if r["signal"] == sig_type and r["pct"] is not None]
    if not grp:
        continue
    pcts = [r["pct"] for r in grp]
    avg = sum(pcts) / len(pcts)
    if sig_type == "BUY":
        correct = sum(1 for p in pcts if p > 0)
    elif sig_type == "SELL":
        correct = sum(1 for p in pcts if p < 0)
    else:
        correct = len(pcts)
    print(f"\n  {sig_type:<6} ({len(grp)} signals) | Avg: {avg:+.2f}% | Correct: {correct}/{len(grp)} ({correct/len(grp)*100:.0f}%)")
    for r in grp:
        st = "✅" if (sig_type == "BUY" and r["pct"] > 0) or (sig_type == "SELL" and r["pct"] < 0) or sig_type in ("HOLD","WATCH","SKIP") else "❌"
        print(f"    {st} {r['name']:<14} ({r['strategy']:<8}) Chg={r['pct']:+.2f}% | {r['reason'][:45]}")

# Per-strategy breakdown
print("\n\n=== BY STRATEGY ===")
for strat in ["EMA+HA", "HM"]:
    grp = [r for r in records if r["strategy"] == strat and r["pct"] is not None]
    if not grp:
        continue
    pcts = [r["pct"] for r in grp]
    avg = sum(pcts) / len(pcts)
    print(f"\n{strat} ({len(grp)} signals) | Avg day chg: {avg:+.2f}%")
    for r in grp:
        print(f"    {r['name']:<14} {r['signal']:<6} Chg={r['pct']:+.2f}%")
