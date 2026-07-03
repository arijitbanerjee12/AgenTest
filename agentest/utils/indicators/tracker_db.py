"""SQLite tracker for daily indicator performance — stored in Agentest_Reports/db/."""
from __future__ import annotations

import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Any

REPORTS_DIR = Path.home() / "Documents" / "Agentest_Reports"
DB_DIR = REPORTS_DIR / "db"
DB_PATH = DB_DIR / "agentest_tracker.db"

_COLUMNS_BTST = [
    ("symbol", "TEXT"), ("name", "TEXT"), ("category", "TEXT"), ("strategy", "TEXT"),
    ("signal", "TEXT"), ("reason", "TEXT"), ("priority", "TEXT"),
    ("close", "REAL"), ("ema_10", "REAL"), ("ema_20", "REAL"),
    ("ha_signal", "TEXT"), ("ha_strength", "INTEGER"),
    ("rsi9", "REAL"), ("speed", "REAL"), ("strength", "REAL"),
    ("vix", "REAL"), ("volume_confirmed", "INTEGER"),
    ("signal_date", "TEXT"), ("entry_time", "TEXT"),
]

_COLUMNS_LONGTERM = [
    ("symbol", "TEXT"), ("name", "TEXT"), ("category", "TEXT"),
    ("signal", "TEXT"), ("reason", "TEXT"), ("close", "REAL"),
    ("ema_10", "REAL"), ("ema_20", "REAL"),
    ("ha_signal", "TEXT"), ("ha_strength", "INTEGER"),
    ("signal_date", "TEXT"),
]


def _ensure_db():
    DB_DIR.mkdir(parents=True, exist_ok=True)


def _conn() -> sqlite3.Connection:
    _ensure_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create tables if they don't exist."""
    _ensure_db()
    conn = _conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS btst_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            category TEXT,
            strategy TEXT DEFAULT 'EMA+HA',
            signal TEXT,
            reason TEXT,
            priority TEXT,
            close REAL,
            ema_10 REAL,
            ema_20 REAL,
            ha_signal TEXT,
            ha_strength INTEGER,
            rsi9 REAL,
            speed REAL,
            strength REAL,
            vix REAL,
            volume_confirmed INTEGER DEFAULT 0,
            entry_time TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS longterm_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            category TEXT,
            signal TEXT,
            reason TEXT,
            close REAL,
            ema_10 REAL,
            ema_20 REAL,
            ha_signal TEXT,
            ha_strength INTEGER,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS signal_performance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            strategy TEXT,
            signal TEXT,
            entry_price REAL,
            next_open REAL,
            next_close REAL,
            next_high REAL,
            next_low REAL,
            pnl_pct REAL,
            result TEXT DEFAULT 'pending',
            hit_target INTEGER DEFAULT 0,
            hit_stop INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE INDEX IF NOT EXISTS idx_btst_date ON btst_signals(signal_date);
        CREATE INDEX IF NOT EXISTS idx_btst_symbol ON btst_signals(symbol);
        CREATE INDEX IF NOT EXISTS idx_longterm_date ON longterm_signals(signal_date);
        CREATE INDEX IF NOT EXISTS idx_perf_date ON signal_performance(signal_date);

        CREATE TABLE IF NOT EXISTS daily_pnl (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            pnl_rs REAL NOT NULL,
            source TEXT DEFAULT 'fno',
            note TEXT,
            created_at TEXT DEFAULT (datetime('now', 'localtime'))
        );
    """)
    conn.commit(); conn.close()
    print(f"  [DB] Initialized at {DB_PATH}")


def save_btst_signals(signals: list[dict], signal_date: str | None = None):
    """Save today's BTST signals to DB."""
    if not signals: return
    sd = signal_date or datetime.now().strftime("%Y-%m-%d")
    conn = _conn()
    count = 0
    for r in signals:
        if r.get("signal") in ("NO DATA", None): continue
        conn.execute("""
            INSERT INTO btst_signals
            (signal_date, symbol, name, category, strategy, signal, reason, priority,
             close, ema_10, ema_20, ha_signal, ha_strength,
             rsi9, speed, strength, vix, volume_confirmed, entry_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sd,
            r.get("symbol", "").replace(".NS", ""),
            r.get("name", ""),
            r.get("category", ""),
            r.get("strategy", "EMA+HA"),
            r.get("signal", ""),
            r.get("reason", ""),
            r.get("priority", ""),
            r.get("close"),
            r.get("ema_10"),
            r.get("ema_20"),
            r.get("ha_signal", ""),
            r.get("ha_strength"),
            r.get("rsi9"),
            r.get("speed"),
            r.get("strength"),
            r.get("vix"),
            1 if r.get("volume_confirmed") else 0,
            r.get("timestamp", ""),
        ))
        count += 1
    conn.commit(); conn.close()
    print(f"  [DB] Saved {count} BTST signals for {sd}")


def save_longterm_signals(signals: list[dict], signal_date: str | None = None):
    """Save today's long-term scan signals to DB."""
    if not signals: return
    sd = signal_date or datetime.now().strftime("%Y-%m-%d")
    conn = _conn()
    count = 0
    for r in signals:
        if r.get("action") in (None, ""): continue
        conn.execute("""
            INSERT INTO longterm_signals
            (signal_date, symbol, name, category, signal, reason, close,
             ema_10, ema_20, ha_signal, ha_strength)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            sd,
            r.get("symbol", "").replace(".NS", ""),
            r.get("name", ""),
            r.get("category", ""),
            r.get("action", r.get("signal", "")),
            r.get("reason", ""),
            r.get("close"),
            r.get("ema_10"),
            r.get("ema_20"),
            r.get("ha_signal", ""),
            r.get("ha_strength"),
        ))
        count += 1
    conn.commit(); conn.close()
    print(f"  [DB] Saved {count} long-term signals for {sd}")


def log_daily_pnl(pnl_rs: float, source: str = "fno", note: str = "", trade_date: str | None = None):
    """Log daily P&L to the tracking DB."""
    td = trade_date or datetime.now().strftime("%Y-%m-%d")
    conn = _conn()
    conn.execute("INSERT INTO daily_pnl (trade_date, pnl_rs, source, note) VALUES (?, ?, ?, ?)",
                 (td, pnl_rs, source, note))
    conn.commit()
    conn.close()
    print(f"  [DB] Logged P&L: ₹{pnl_rs:+,} on {td} ({source})")


def get_signals_by_date(signal_date: str, strategy: str | None = None) -> list[dict]:
    """Retrieve signals for a given date."""
    conn = _conn()
    if strategy:
        cur = conn.execute("SELECT * FROM btst_signals WHERE signal_date=? AND strategy=? ORDER BY symbol", (signal_date, strategy))
    else:
        cur = conn.execute("SELECT * FROM btst_signals WHERE signal_date=? ORDER BY strategy, symbol", (signal_date,))
    rows = cur.fetchall()
    conn.close()
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


def get_accuracy_summary(strategy: str | None = None) -> list[dict]:
    """Aggregate accuracy per day per strategy for BUY/SELL signals."""
    conn = _conn()
    query = """
        SELECT signal_date, strategy,
               COUNT(*) as total,
               SUM(CASE WHEN signal='BUY' THEN 1 ELSE 0 END) as buys,
               SUM(CASE WHEN signal='SELL' THEN 1 ELSE 0 END) as sells
        FROM btst_signals
        WHERE signal IN ('BUY','SELL')
    """
    params = []
    if strategy:
        query += " AND strategy=?"
        params.append(strategy)
    query += " GROUP BY signal_date, strategy ORDER BY signal_date DESC LIMIT 30"
    cur = conn.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in rows]


def update_performance(signal_date: str, results: list[dict]):
    """Store next-day performance data for BTST signals."""
    conn = _conn()
    count = 0
    for r in results:
        conn.execute("""
            INSERT INTO signal_performance
            (signal_date, symbol, name, strategy, signal, entry_price,
             next_open, next_close, next_high, next_low, pnl_pct, result,
             hit_target, hit_stop)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            signal_date,
            r.get("symbol", ""),
            r.get("name", ""),
            r.get("strategy", "EMA+HA"),
            r.get("signal", ""),
            r.get("entry_price"),
            r.get("next_open"),
            r.get("next_close"),
            r.get("next_high"),
            r.get("next_low"),
            r.get("pnl_pct"),
            r.get("result", "pending"),
            1 if r.get("hit_target") else 0,
            1 if r.get("hit_stop") else 0,
        ))
        count += 1
    conn.commit(); conn.close()
    print(f"  [DB] Updated performance for {count} signals from {signal_date}")


def get_running_accuracy(strategy: str | None = None, days: int = 90) -> dict:
    """Get running accuracy stats for the last N days."""
    conn = _conn()
    params: list[Any] = []
    q = """
        SELECT strategy, signal,
               COUNT(*) as total,
               ROUND(AVG(pnl_pct), 2) as avg_pnl
        FROM signal_performance
        WHERE signal IN ('BUY','SELL')
        AND signal_date >= date('now', ?)
    """
    params.append(f"-{days} days")
    if strategy:
        q += " AND strategy=?"
        params.append(strategy)
    q += " GROUP BY strategy, signal ORDER BY strategy, signal"
    cur = conn.execute(q, params)
    rows = cur.fetchall()
    conn.close()
    return [dict(zip([d[0] for d in cur.description], r)) for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"  [DB] Database ready at {DB_PATH}")
