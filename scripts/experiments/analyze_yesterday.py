"""Analyze yesterday's BTST signals vs today's price movement."""
from pathlib import Path
import pandas as pd
import yfinance as yf

REPORTS = Path.home() / "Documents" / "Agentest_Reports"
file = REPORTS / "2026-06-21" / "BTST_TodaySignals_20260621_221225.xlsx"

df = pd.read_excel(file, header=None)
# data starts at row 3 (0-indexed), cols: 0=Symbol, 1=Signal, 2=OptAct, 3=Close, 4=Reason
records = []
for i in range(3, 28):
    sym = df.iloc[i, 0]
    sig = df.iloc[i, 1]
    close = df.iloc[i, 3]
    reason = str(df.iloc[i, 4]) if pd.notna(df.iloc[i, 4]) else ""
    # Determine strategy: HM reason contains "HM"
    strategy = "HM" if "HM" in reason else "EMA+HA"
    if pd.notna(sym) and pd.notna(sig):
        records.append({"name": str(sym), "symbol": str(sym) + ".NS" if "." not in str(sym) and "^" not in str(sym) else str(sym), "signal": str(sig), "close": close, "strategy": strategy, "reason": reason})

print(f"Loaded {len(records)} signals from yesterday")
for r in records:
    print(f"  {r['name']:<14} {r['signal']:<6} {r['strategy']:<8} {r['close']} — {r['reason'][:50]}")

print("\n\n=== TODAY'S (Jun 22) MOVEMENT ===")
for r in records:
    sym = r["symbol"]
    name = r["name"]
    sig = r["signal"]
    strat = r["strategy"]
    
    df2 = yf.download(sym, period="2d", interval="15m", progress=False, auto_adjust=True)
    if df2.empty or len(df2) < 5:
        print(f"  {name:<14} {sig:<6} {strat:<8} NO DATA today")
        r["result"] = "NO_DATA"
        r["pct"] = 0
        continue
    if isinstance(df2.columns, pd.MultiIndex):
        df2.columns = [c[0] for c in df2.columns]
    
    open_p = float(df2["Close"].iloc[0])
    last_p = float(df2["Close"].iloc[-1])
    pct = round((last_p / open_p - 1) * 100, 2)
    low_p = float(df2["Low"].min())
    high_p = float(df2["High"].max())
    
    # Correctness: BUY=price went up, SELL=price went down, HOLD/WATCH=within 1% range
    if sig == "BUY":
        correct = pct > 0
    elif sig == "SELL":
        correct = pct < 0
    else:
        correct = abs(pct) < 1.5  # HOLD/WATCH are neutral
    
    r["result"] = "CORRECT" if correct else "WRONG"
    r["pct"] = pct
    r["range"] = round((high_p / low_p - 1) * 100, 2)
    mark = "✅" if correct else "❌"
    print(f"  {mark} {name:<14} {sig:<6} {strat:<8} Open={open_p:.2f} Last={last_p:.2f} Chg={pct:+.2f}% (range {r['range']:.2f}%)")

print("\n\n=== ACCURACY SUMMARY ===")
correct = [r for r in records if r.get("result") == "CORRECT"]
wrong = [r for r in records if r.get("result") == "WRONG"]
print(f"Total: {len(records)} | Correct: {len(correct)} ({len(correct)/len(records)*100:.0f}%) | Wrong: {len(wrong)} ({len(wrong)/len(records)*100:.0f}%)")

for strat_name in ("EMA+HA", "HM"):
    grp = [r for r in records if r["strategy"] == strat_name]
    gc = [r for r in grp if r.get("result") == "CORRECT"]
    gw = [r for r in grp if r.get("result") == "WRONG"]
    if not grp: continue
    print(f"\n{strat_name} ({len(grp)} signals): {len(gc)} correct ({len(gc)/len(grp)*100:.0f}%) / {len(gw)} wrong")
    for r in grp:
        m = "✅" if r.get("result")=="CORRECT" else "❌"
        print(f"  {m} {r['name']:<14} {r['signal']:<6} {r.get('pct',0):+.2f}%")

for sig_type in ("BUY", "SELL", "HOLD", "WATCH"):
    grp = [r for r in records if r["signal"] == sig_type]
    gc = [r for r in grp if r.get("result") == "CORRECT"]
    if grp:
        print(f"\n{sig_type}: {len(gc)}/{len(grp)} correct ({len(gc)/len(grp)*100:.0f}%)")
