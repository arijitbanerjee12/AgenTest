from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path

JOURNAL_DIR = Path("tests/data/journal")
JOURNAL_FILE = JOURNAL_DIR / "trade_journal.csv"

FIELDS = [
    "timestamp", "strategy", "symbol", "category", "action", "reason",
    "entry_date", "exit_date", "entry_price", "exit_price", "exit_reason",
    "pnl_pct", "win", "ha_strength", "ha_signal",
    "volume_confirmed", "volume_ratio", "vix",
    "position_size_pct", "premium_rs", "option_pnl_rs",
    "followed_rules",
]


def _ensure_file():
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    if not JOURNAL_FILE.exists():
        with open(JOURNAL_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(FIELDS)


def log_trade(trade: dict, strategy: str = "btst") -> None:
    _ensure_file()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = {
        "timestamp": now,
        "strategy": strategy,
        "symbol": trade.get("display_name", trade.get("symbol", "")),
        "category": trade.get("category", ""),
        "action": trade.get("action", ""),
        "reason": trade.get("reason", ""),
        "entry_date": trade.get("entry_date", ""),
        "exit_date": trade.get("exit_date", ""),
        "entry_price": trade.get("entry_price", ""),
        "exit_price": trade.get("exit_price", ""),
        "exit_reason": trade.get("exit_reason", ""),
        "pnl_pct": trade.get("pnl_pct", ""),
        "win": "W" if trade.get("win") else "L",
        "ha_strength": trade.get("ha_strength", ""),
        "ha_signal": trade.get("ha_signal", ""),
        "volume_confirmed": trade.get("volume_confirmed", ""),
        "volume_ratio": trade.get("volume_ratio", ""),
        "vix": trade.get("vix_at_entry", ""),
        "position_size_pct": trade.get("position_size_pct", ""),
        "premium_rs": trade.get("premium_rs", ""),
        "option_pnl_rs": trade.get("option_pnl_rs", ""),
        "followed_rules": "yes",
    }
    with open(JOURNAL_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writerow(row)


def log_trades(trades: list[dict], strategy: str = "btst") -> int:
    count = 0
    for t in trades:
        log_trade(t, strategy)
        count += 1
    return count


def load_journal() -> list[dict]:
    if not JOURNAL_FILE.exists():
        return []
    with open(JOURNAL_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def journal_summary() -> dict:
    rows = load_journal()
    n = len(rows)
    if n == 0:
        return {"total_trades": 0}
    wins = [r for r in rows if r.get("win") == "W"]
    losses = [r for r in rows if r.get("win") == "L"]
    win_rate = len(wins) / n * 100 if n else 0
    pnls = [float(r.get("pnl_pct", 0)) for r in rows if r.get("pnl_pct")]
    avg_pnl = sum(pnls) / len(pnls) if pnls else 0
    by_symbol: dict[str, dict] = {}
    for r in rows:
        sym = r.get("symbol", "?")
        if sym not in by_symbol:
            by_symbol[sym] = {"trades": 0, "wins": 0}
        by_symbol[sym]["trades"] += 1
        if r.get("win") == "W":
            by_symbol[sym]["wins"] += 1
    for sym, d in by_symbol.items():
        d["win_rate"] = round(d["wins"] / d["trades"] * 100, 1) if d["trades"] else 0
    return {
        "total_trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 1),
        "avg_pnl_pct": round(avg_pnl, 2),
        "by_symbol": by_symbol,
    }
