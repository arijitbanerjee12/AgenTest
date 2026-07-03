"""HM C0 standalone on 20 stocks — ranked by compound return."""
from __future__ import annotations

# Data from last run: HM C0 (standalone, hourly 3mo, 0.8/0.3 exit)
DATA = [
    ("DMART",      47, 66.0, 22.01),
    ("BHARTIARTL", 50, 62.0, 20.28),
    ("ICICIBANK",  46, 65.2, 20.21),
    ("INFY",       44, 63.6, 19.13),
    ("BAJAJ-AUTO", 48, 58.3, 17.60),
    ("MARUTI",     45, 60.0, 17.48),
    ("HCLTECH",    49, 57.1, 17.35),
    ("BAJFINANCE", 47, 57.4, 16.77),
    ("WIPRO",      47, 57.4, 16.77),
    ("M&M",        48, 56.2, 16.42),
    ("BAJAJFINSV", 49, 55.1, 16.07),
    ("HDFCBANK",   46, 52.2, 13.33),
    ("AXISBANK",   44, 52.3, 12.77),
    ("KOTAKBANK",  42, 52.4, 12.21),
    ("SBIN",       45, 44.4,  8.79),
    ("BANKNIFTY",  46, 43.5,  8.30),
    ("ITC",        48, 41.7,  6.25),
    ("HINDUNILVR", 46, 39.1,  6.11),
    ("SENSEX",     46, 34.8,  3.09),
    ("NIFTY",      46, 32.6,  2.27),
]

data_sorted = sorted(DATA, key=lambda x: x[3], reverse=True)

print("=" * 65)
print("  HM C0 STANDALONE — RANKED by Compound Return")
print("  Hourly 3mo · Exit: 0.8% target / 0.3% stop")
print("=" * 65)
print(f"  {'Rank':<5} {'Stock':<14} {'Trades':>6} {'WR%':>6} {'Cmpd%':>8}")
print(f"  {'-'*39}")
for i, (sym, tr, wr, cmpd) in enumerate(data_sorted, 1):
    print(f"  {i:<5} {sym:<14} {tr:>6} {wr:>5.1f}% {cmpd:>7.2f}%")

# Groups
print(f"\n{'='*65}")
print(f"  TIERS")
print(f"{'='*65}")
print(f"  ★ TIER 1 (Cmpd > 18%):")
for sym, tr, wr, cmpd in data_sorted:
    if cmpd >= 18: print(f"    {sym:<14} {tr:>3}tr | WR {wr:>5.1f}% | Cmpd {cmpd:>+6.2f}%")

print(f"  ★ TIER 2 (Cmpd 14-18%):")
for sym, tr, wr, cmpd in data_sorted:
    if 14 <= cmpd < 18: print(f"    {sym:<14} {tr:>3}tr | WR {wr:>5.1f}% | Cmpd {cmpd:>+6.2f}%")

print(f"  ○ TIER 3 (Cmpd 8-14%):")
for sym, tr, wr, cmpd in data_sorted:
    if 8 <= cmpd < 14: print(f"    {sym:<14} {tr:>3}tr | WR {wr:>5.1f}% | Cmpd {cmpd:>+6.2f}%")

print(f"  ○ TIER 4 (Cmpd < 8%):")
for sym, tr, wr, cmpd in data_sorted:
    if cmpd < 8: print(f"    {sym:<14} {tr:>3}tr | WR {wr:>5.1f}% | Cmpd {cmpd:>+6.2f}%")

print(f"\n{'='*65}")
print(f"  TOP 10 for HM C0:")
for i, (sym, tr, wr, cmpd) in enumerate(data_sorted[:10], 1):
    print(f"  {i:<3} {sym:<14} {tr:>3}tr | WR {wr:>5.1f}% | Cmpd {cmpd:>+6.2f}%")
