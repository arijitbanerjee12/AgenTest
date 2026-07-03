"""Company-wise comparison table: EMA+HA vs HM vs combined vs standalone."""
from __future__ import annotations

# Data from last run on hourly 3mo with 0.8/0.3 exit
DATA = [
    ("NIFTY",       32, 37.5,  3.25,  21, 33.3,  1.83,  50, 34.0,  3.29),
    ("SENSEX",      31, 38.7,  3.18,  22, 31.8,  1.08,  50, 36.0,  4.11),
    ("BANKNIFTY",   35, 45.7,  7.14,  20, 30.0,  0.75,  50, 44.0,  9.38),
    ("HDFCBANK",    30, 53.3,  8.92,  19, 47.4,  4.25,  50, 54.0, 15.72),
    ("ICICIBANK",   35, 65.7, 15.07,  20, 75.0, 10.26,  50, 64.0, 21.41),
    ("AXISBANK",    31, 67.7, 14.72,  19, 63.2,  7.74,  47, 51.1, 12.99),
    ("KOTAKBANK",   26, 57.7,  9.03,  13, 53.8,  3.85,  46, 54.3, 14.58),
    ("SBIN",        35, 60.0, 13.35,  21, 57.1,  7.10,  49, 46.9, 11.09),
    ("BAJFINANCE",  31, 58.1, 11.00,  20, 50.0,  5.09,  51, 58.8, 19.24),
    ("BAJAJFINSV",  39, 51.3, 10.77,  21, 52.4,  5.93,  52, 53.8, 16.30),
    ("INFY",        29, 55.2,  9.25,  18, 66.7,  8.07,  47, 66.0, 22.01),
    ("HCLTECH",     26, 57.7,  9.03,  13, 69.2,  6.15,  53, 58.5, 19.83),
    ("WIPRO",       31, 45.2,  6.23,  19, 42.1,  3.12,  51, 56.9, 17.94),
    ("HINDUNILVR",  36, 55.6, 11.77,  24, 41.7,  3.83,  49, 40.8,  7.49),
    ("ITC",         32, 46.9,  6.02,  19, 47.4,  3.53,  52, 42.3,  7.31),
    ("DMART",       36, 52.8, 10.55,  18, 50.0,  4.57,  50, 66.0, 23.60),
    ("M&M",         31, 61.3, 12.23,  20, 60.0,  7.42,  52, 55.8, 17.58),
    ("MARUTI",      28, 57.1,  9.57,  17, 64.7,  7.21,  48, 62.5, 20.32),
    ("BAJAJ-AUTO",  37, 51.4, 10.22,  22, 50.0,  5.61,  52, 55.8, 17.48),
    ("BHARTIARTL",  31, 51.6,  8.18,  16, 62.5,  6.36,  54, 63.0, 22.82),
]

def fmt(v, d=1): return f"{v:.{d}f}"
def pick_best(b_wr, b_cmpd, c_wr, c_cmpd):
    """Simple heuristic: pick by compound return."""
    return "C" if c_cmpd > b_cmpd else "A"

print("=" * 145)
print("  COMPANY-WISE COMPARISON: EMA+HA (A) | EMA+HA+HM (B) | HM Standalone (C)")
print("  Hourly 3mo | Exit: 0.8% target / 0.3% stop | Best = highest compound")
print("=" * 145)
print(f"  {'Company':<14} {'A-Tr':>5} {'A-WR':>6} {'A-Cmpd':>8} ", end="")
print(f"{'B-Tr':>5} {'B-WR':>6} {'B-Cmpd':>8} ", end="")
print(f"{'C-Tr':>5} {'C-WR':>6} {'C-Cmpd':>8} {'Best':>5}")
print(f"  {'-'*96}")
a_wins, c_wins = 0, 0
for sym, at, aw, ac, bt, bw, bc, ct, cw, cc in DATA:
    best = pick_best(aw, ac, cw, cc)
    if best == "C": c_wins += 1
    else: a_wins += 1
    print(f"  {sym:<14} {at:>5} {fmt(aw):>6}% {fmt(ac):>8}% {bt:>5} {fmt(bw):>6}% {fmt(bc):>8}% {ct:>5} {fmt(cw):>6}% {fmt(cc):>8}% {best:>5}")

# Totals
print(f"  {'─'*96}")
print(f"  {'TOTAL':<14} {642:>5} {53.4:>5}% {506.09:>7}% {382:>5} {51.6:>5}% {173.51:>7}% {1003:>5} {53.2:>5}% {1554.09:>7}%")

print(f"\n  Best strategy count: A (EMA+HA) = {a_wins}/20 | C (HM alone) = {c_wins}/20")
print(f"  B (HM filter) never best — removes trades without improving quality.")

print("\n  NOTES for each company:")
print(f"  {'─'*120}")
for sym, at, aw, ac, bt, bw, bc, ct, cw, cc in DATA:
    dc = cc - ac
    notes = []
    if dc > 5: notes.append(f"HM beats EMA+HA by {fmt(dc)}%")
    elif dc < -5: notes.append(f"EMA+HA beats HM by {fmt(-dc)}%")
    else: notes.append(f"Comparable (Δ{fmt(dc)}%)")
    if ct > at * 1.3: notes.append(f"HM has {ct}/{at} trades ({int(ct/at*100-100)}% more)")
    print(f"  {sym:<14} → Cmpd: A={fmt(ac)}% C={fmt(cc)}% | {' | '.join(notes)}")
