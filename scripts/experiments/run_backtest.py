"""Backtest EMA 10/20 + HA — Large caps only, daily, multi-threaded."""

from __future__ import annotations
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agentest.utils.indicators.backtest import backtest_symbol, export_results
from collections import defaultdict

CSV_DIR = Path("tests/data/stocks")


def load_symbols() -> list[str]:
    path = CSV_DIR / "nifty50_large_cap.csv"
    df = pd.read_csv(path)
    return df[df.columns[0]].dropna().str.strip().str.upper().tolist()


def print_company_stats(results: dict):
    print(f"  {'Symbol':<22} {'Trades':>7} {'Wins':>5} {'Win%':>7} {'Avg%':>8} {'Edge%':>9} {'Cmpd%':>9}")
    print(f"  {'-'*22} {'-'*7} {'-'*5} {'-'*7} {'-'*8} {'-'*9} {'-'*9}")
    for p in results["symbol_stats"]:
        print(f"  {p['symbol']:<22} {p['trades']:>7} {p['wins']:>5} {p['win_rate']:>6}% {p['avg_pnl']:>7.2f}% {p['cum_pnl']:>8.2f}% {p['compound_return']:>8.2f}%")


def main():
    print("=" * 55)
    print("  Backtest — EMA 10/20 + HA (Long Only, Daily)")
    print("  Large Cap Nifty 50 — multi-threaded (6 workers)")
    print("=" * 55)

    symbols = load_symbols()
    print(f"  Loaded {len(symbols)} large cap symbols")
    print()

    all_trades: list[dict] = []
    perf_by_symbol: dict[str, list[float]] = defaultdict(list)
    by_category: dict[str, list[dict]] = defaultdict(list)

    with ThreadPoolExecutor(max_workers=6) as executor:
        fut_map = {executor.submit(backtest_symbol, sym, "large_cap"): sym for sym in symbols}
        done = 0
        for fut in as_completed(fut_map):
            sym = fut_map[fut]
            trades = fut.result()
            for t in trades:
                all_trades.append(t)
                by_category["large_cap"].append(t)
                perf_by_symbol[t["symbol"]].append(t["pnl_pct"])
            done += 1
            if done % 10 == 0 or done == len(symbols):
                print(f"  Progress: {done}/{len(symbols)} symbols", end="\r")
    print()

    trades_list = by_category["large_cap"]
    wins = [t for t in trades_list if t["pnl_pct"] > 0]
    losses = [t for t in trades_list if t["pnl_pct"] <= 0]
    total = len(trades_list)
    win_rate = round(len(wins) / total * 100, 1) if total else 0
    avg_pnl = round(sum(t["pnl_pct"] for t in trades_list) / total, 2) if total else 0
    sum_pnl = round(sum(t["pnl_pct"] for t in trades_list), 2)
    gross_profit = sum(t["pnl_pct"] for t in wins) if wins else 0
    gross_loss = abs(sum(t["pnl_pct"] for t in losses)) if losses else 0
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss else float("inf")

    cost_per_trade = 0.15
    cost_drag = round(total * cost_per_trade, 2)
    adj_sum_pnl = round(sum_pnl - cost_drag, 2)

    results = {
        "trades": all_trades,
        "categories": {
            "large_cap": dict(
                total_trades=total, wins=len(wins), win_rate=win_rate,
                avg_pnl=avg_pnl, sum_pnl=sum_pnl, profit_factor=profit_factor,
            )
        },
        "overall": dict(
            total_trades=total, wins=len(wins), win_rate=win_rate,
            avg_pnl=avg_pnl, sum_pnl=sum_pnl, profit_factor=profit_factor,
        ),
    }

    sym_perf = []
    for sym, pnls in perf_by_symbol.items():
        compound = 1.0
        sym_wins = sum(1 for p in pnls if p > 0)
        for p in pnls:
            compound *= 1 + p / 100
        compound_return = round((compound - 1) * 100, 2)
        sym_perf.append(dict(
            symbol=sym, trades=len(pnls), wins=sym_wins,
            win_rate=round(sym_wins / len(pnls) * 100, 1) if pnls else 0,
            avg_pnl=round(sum(pnls) / len(pnls), 2),
            cum_pnl=round(sum(pnls), 2),
            compound_return=compound_return,
        ))
    sym_perf.sort(key=lambda x: x["compound_return"], reverse=True)
    results["top_performers"] = sym_perf[:20]
    results["worst_performers"] = sym_perf[-20:]
    results["symbol_stats"] = sym_perf

    print("=" * 55)
    print("  RESULTS (Daily, Long Only)")
    print("=" * 55)
    print(f"  Total Trades   : {total}")
    print(f"  Wins           : {len(wins)}")
    print(f"  Win Rate       : {win_rate}%")
    print(f"  Avg P&L        : {avg_pnl:.2f}%")
    print(f"  Total Edge     : {sum_pnl:.2f}%")
    print(f"  Profit Factor  : {profit_factor}")
    print(f"  Cost Drag      : {cost_drag:.2f}% (0.15%/trade)")
    print(f"  Edge After Cost: {adj_sum_pnl:.2f}%")
    print()

    print("=" * 55)
    print("  COMPANY-WISE STATS")
    print("=" * 55)
    print_company_stats(results)
    print()

    # Projections for 1 lakh
    compounds = [p["compound_return"] for p in sym_perf]
    positive = [c for c in compounds if c > 0]
    avg_cmpd = sum(compounds) / len(compounds)
    avg_top10 = sum(sorted(compounds, reverse=True)[:10]) / 10
    ann_avg = ((1 + avg_cmpd/100)**(12/18) - 1) * 100
    ann_top10 = ((1 + avg_top10/100)**(12/18) - 1) * 100

    print("=" * 55)
    print("  REALISTIC PROJECTION — ₹1,00,000")
    print("=" * 55)
    print(f"  Stocks with positive return: {len(positive)}/{len(compounds)}")
    print(f"  Avg compound return per stock: {avg_cmpd:.2f}% over 18 months ({ann_avg:.1f}% annualized)")
    print(f"  Avg of top 10 stocks: {avg_top10:.2f}% over 18 months ({ann_top10:.1f}% annualized)")
    print()
    print(f"  1. Avg stock (buy & hold): ₹{100000 * (1 + avg_cmpd/100)::,.0f}")
    print(f"  2. Top 10 stocks equally  : ₹{100000 * (1 + avg_top10/100):,:.0f}")
    cap = 100000
    for yr in range(1, 4):
        cap *= (1.0067)**50  # avg 0.67% per trade
        print(f"  {yr}yr active (50 trades/yr @ 0.67%): ₹{cap:,.0f}")
    print()

    path = export_results(results)
    print(f"  Report saved: {path}")


if __name__ == "__main__":
    main()
