"""Analyze yesterday's long-term signals vs today's close."""
from pathlib import Path
import pandas as pd
import yfinance as yf

REPORTS = Path.home() / "Documents" / "Agentest_Reports"
file = REPORTS / "2026-06-21" / "FocusScan_20260621_221206.xlsx"

df = pd.read_excel(file, sheet_name="AI Analysis", header=0)
print(f"Loaded {len(df)} signals")
print(f"Signal distribution:\n{df['Technical Action'].value_counts()}")

buys = df[df["Technical Action"] == "BUY"].copy()
sells = df[df["Technical Action"] == "SELL"].copy()
print(f"\nBUY: {len(buys)} | SELL: {len(sells)}")

def get_movement(symbol):
    df2 = yf.download(symbol, period="2d", interval="15m", progress=False, auto_adjust=True)
    if df2.empty or len(df2) < 5:
        return None
    if isinstance(df2.columns, pd.MultiIndex):
        df2.columns = [c[0] for c in df2.columns]
    o = float(df2["Close"].iloc[0])
    l = float(df2["Close"].iloc[-1])
    low = float(df2["Low"].min())
    high = float(df2["High"].max())
    return {"open": o, "last": l, "pct": round((l/o - 1)*100, 2), "low": round((low/o - 1)*100, 2), "high": round((high/o - 1)*100, 2)}

print("\n=== BUY SIGNALS — How they're holding ===")
for _, row in buys.iterrows():
    sym = row["Symbol"]
    name = sym.replace(".NS", "")
    verdict = str(row.get("AI Verdict", ""))
    reason = str(row.get("Verdict Reason", ""))[:60]
    m = get_movement(sym)
    if not m:
        print(f"  {name:<18} NO DATA")
    else:
        st = "✅" if m["pct"] > 0 else "❌"
        print(f"  {st} {name:<18} Open={m['open']:<10.2f} Now={m['last']:<10.2f} Chg={m['pct']:+.2f}% (low={m['low']:.2f}% high={m['high']:.2f}%) | {verdict}")

print("\n=== SELL SIGNALS — How they're holding ===")
for _, row in sells.iterrows():
    sym = row["Symbol"]
    name = sym.replace(".NS", "")
    verdict = str(row.get("AI Verdict", ""))
    reason = str(row.get("Verdict Reason", ""))[:60]
    m = get_movement(sym)
    if not m:
        print(f"  {name:<18} NO DATA")
    else:
        st = "✅" if m["pct"] < 0 else "❌"
        print(f"  {st} {name:<18} Open={m['open']:<10.2f} Now={m['last']:<10.2f} Chg={m['pct']:+.2f}% (low={m['low']:.2f}% high={m['high']:.2f}%) | {verdict}")

# Summary
print("\n\n=== SUMMARY ===")
buy_vals = []
for _, row in buys.iterrows():
    m = get_movement(row["Symbol"])
    if m: buy_vals.append(m["pct"])
sell_vals = []
for _, row in sells.iterrows():
    m = get_movement(row["Symbol"])
    if m: sell_vals.append(m["pct"])

if buy_vals:
    wins = sum(1 for p in buy_vals if p > 0)
    print(f"BUY signals: {wins}/{len(buy_vals)} up ({wins/len(buy_vals)*100:.0f}%) | Avg: {sum(buy_vals)/len(buy_vals):+.2f}% | Best: {max(buy_vals):+.2f}% Worst: {min(buy_vals):+.2f}%")
    for i, (_, row) in enumerate(buys.iterrows()):
        if i < len(buy_vals):
            st = "✅" if buy_vals[i] > 0 else "❌"
            print(f"  {st} {row['Symbol'].replace('.NS',''):<18} {buy_vals[i]:+.2f}%")

if sell_vals:
    wins = sum(1 for p in sell_vals if p < 0)
    print(f"\nSELL signals: {wins}/{len(sell_vals)} down ({wins/len(sell_vals)*100:.0f}%) | Avg: {sum(sell_vals)/len(sell_vals):+.2f}% | Best: {min(sell_vals):+.2f}% Worst: {max(sell_vals):+.2f}%")
    for i, (_, row) in enumerate(sells.iterrows()):
        if i < len(sell_vals):
            st = "✅" if sell_vals[i] < 0 else "❌"
            print(f"  {st} {row['Symbol'].replace('.NS',''):<18} {sell_vals[i]:+.2f}%")
