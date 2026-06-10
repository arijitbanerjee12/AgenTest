"""BTST (Buy Today, Sell Tomorrow) — hourly/15m last-hour signal + backtest with options P&L."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

from agentest.utils.indicators.ema import compute_ema
from agentest.utils.indicators.heikin_ashi import compute_heikin_ashi

REPORTS_DIR = Path.home() / "Documents" / "Agentest_Reports"
TODAY_REPORT = None  # Set after generate_today_signal_report() runs

# ── Best-performing symbols from initial backtest ──

BTST_SYMBOLS: list[dict] = [
    {"name": "ICICIBANK", "symbol": "ICICIBANK.NS", "category": "large_cap"},
    {"name": "BANKNIFTY", "symbol": "^NSEBANK",     "category": "index"},
    {"name": "HDFCBANK",  "symbol": "HDFCBANK.NS",  "category": "large_cap"},
    {"name": "SBIN",      "symbol": "SBIN.NS",      "category": "large_cap"},
    {"name": "NIFTY",     "symbol": "^NSEI",        "category": "index"},
    {"name": "SENSEX",    "symbol": "^BSESN",       "category": "index"},
    {"name": "BHARTIARTL","symbol": "BHARTIARTL.NS","category": "large_cap"},
    {"name": "M&M",       "symbol": "M&M.NS",       "category": "large_cap"},
    {"name": "HDFCLIFE",  "symbol": "HDFCLIFE.NS",  "category": "large_cap"},
    {"name": "LT",        "symbol": "LT.NS",        "category": "large_cap"},
    {"name": "BAJFINANCE","symbol": "BAJFINANCE.NS","category": "large_cap"},
]

OPTION_MULTIPLIER = 18


def fetch_data(symbol: str, interval: str = "1h", period: str = "3mo") -> pd.DataFrame:
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.capitalize() for c in df.columns]
    return df


def _ha_signal_at_index(ha: pd.DataFrame, idx: int) -> dict:
    if idx < 2:
        return {"signal": "unknown", "strength": 0}
    last = ha.iloc[idx]
    prev = ha.iloc[idx - 1]
    prev2 = ha.iloc[idx - 2]
    is_green = last["HA_Close"] > last["HA_Open"]
    is_red = last["HA_Close"] < last["HA_Open"]
    hi = last["HA_High"]
    lo = last["HA_Low"]
    denom = hi - lo + 1e-9
    no_upper_wick = abs(hi - max(last["HA_Open"], last["HA_Close"])) < 0.01 * denom
    no_lower_wick = abs(min(last["HA_Open"], last["HA_Close"]) - lo) < 0.01 * denom
    prev_green = prev["HA_Close"] > prev["HA_Open"]
    prev2_green = prev2["HA_Close"] > prev2["HA_Open"]
    consecutive_green = is_green and prev_green and prev2_green
    consistent_bullish = is_green and prev_green
    if is_green and no_upper_wick and consecutive_green:
        return {"signal": "strong_buy", "strength": 3}
    if is_green and consistent_bullish:
        return {"signal": "buy", "strength": 2}
    if is_green:
        return {"signal": "weak_buy", "strength": 1}
    if is_red and no_lower_wick and not prev_green and not prev2_green:
        return {"signal": "strong_sell", "strength": -3}
    if is_red and not prev_green:
        return {"signal": "sell", "strength": -2}
    if is_red:
        return {"signal": "weak_sell", "strength": -1}
    return {"signal": "neutral", "strength": 0}


def _scan_signal(ema_short: pd.Series, ema_long: pd.Series, ha_signal: dict) -> dict:
    """Replicate scan_combined logic inline (no external dep)."""
    if len(ema_short) < 2 or len(ema_long) < 2:
        return {"action": "SKIP", "reason": "Insufficient data", "priority": "LOW"}
    curr_s = ema_short.iloc[-1]
    curr_l = ema_long.iloc[-1]
    prev_s = ema_short.iloc[-2]
    prev_l = ema_long.iloc[-2]
    ha_st = ha_signal.get("strength", 0)

    crossed_up = prev_s <= prev_l and curr_s > curr_l
    is_above = curr_s > curr_l
    near_cross_up = not is_above and (curr_l - curr_s) / (curr_l + 1e-9) < 0.02
    crossed_down = prev_s >= prev_l and curr_s < curr_l
    is_below = curr_s < curr_l
    near_cross_down = is_below and (curr_l - curr_s) / (curr_l + 1e-9) < 0.02

    # BUY checks
    if crossed_up and ha_st >= 2:
        return {"action": "BUY", "reason": "Crossed + HA strong buy", "priority": "HIGH"}
    if crossed_up:
        return {"action": "WATCH", "reason": "Crossed but HA weak", "priority": "MEDIUM"}
    if near_cross_up and ha_st >= 2:
        return {"action": "BUY", "reason": "Near cross + HA strong buy", "priority": "HIGH"}
    if ha_st >= 2 and is_above:
        return {"action": "HOLD", "reason": "Above EMA + HA bullish", "priority": "MEDIUM"}

    # SELL checks
    if crossed_down and ha_st <= -2:
        return {"action": "SELL", "reason": "Bearish cross + HA strong sell", "priority": "HIGH"}
    if crossed_down:
        return {"action": "SELL", "reason": "Bearish cross", "priority": "HIGH"}
    if near_cross_down and ha_st <= -2:
        return {"action": "SELL", "reason": "Near bearish cross + HA strong sell", "priority": "HIGH"}
    if ha_st <= -2 and is_below:
        return {"action": "SELL", "reason": "Below EMA + HA bearish", "priority": "MEDIUM"}
    if ha_st <= -2:
        return {"action": "SELL", "reason": "HA strong sell", "priority": "HIGH"}

    return {"action": "SKIP", "reason": "No signal", "priority": "LOW"}


def _last_candle_signal(df: pd.DataFrame, ha: pd.DataFrame, iloc_pos: int) -> dict | None:
    """Compute signal for a specific candle position."""
    if iloc_pos < 2:
        return None
    ema_short = df["EMA_10"]
    ema_long = df["EMA_20"]
    if pd.isna(ema_short.iloc[iloc_pos]) or pd.isna(ema_long.iloc[iloc_pos]):
        return None
    ha_sig = _ha_signal_at_index(ha, iloc_pos)
    scan = _scan_signal(ema_short.iloc[:iloc_pos + 1], ema_long.iloc[:iloc_pos + 1], ha_sig)
    return scan


def backtest_btst(
    symbol: str,
    category: str,
    period: str = "3mo",
    interval: str = "1h",
    exit_timing: str = "close",
) -> list[dict]:
    """
    BTST backtest with configurable interval and exit timing.

    Parameters
    ----------
    exit_timing : "close" (next day last close) or "open" (next day first open)
    """
    df = fetch_data(symbol, interval, period)
    if df.empty:
        return []

    df["EMA_10"] = compute_ema(df["Close"], 10)
    df["EMA_20"] = compute_ema(df["Close"], 20)
    ha = compute_heikin_ashi(df)

    df["date"] = df.index.date
    day_groups = list(df.groupby("date"))

    # Build day-level data: close, open, signal
    day_info: list[dict] = []
    for date, day_df in day_groups:
        day_df = day_df.sort_index()
        last_global_idx = day_df.index[-1]
        iloc_pos = df.index.get_loc(last_global_idx)
        close = float(day_df["Close"].iloc[-1])
        open_price = float(day_df["Open"].iloc[0])

        sig = _last_candle_signal(df, ha, iloc_pos)
        day_info.append({
            "date": str(date),
            "close": close,
            "open": open_price,
            "action": sig["action"] if sig else "SKIP",
            "reason": sig["reason"] if sig else "No signal",
            "crossover": "no_crossover",
            "ha_signal": _ha_signal_at_index(ha, iloc_pos)["signal"] if iloc_pos >= 2 else "unknown",
            "ema_10": round(float(df["EMA_10"].iloc[iloc_pos]), 2) if pd.notna(df["EMA_10"].iloc[iloc_pos]) else 0,
            "ema_20": round(float(df["EMA_20"].iloc[iloc_pos]), 2) if pd.notna(df["EMA_20"].iloc[iloc_pos]) else 0,
        })

    # Generate trades: enter on signal day, exit next trading day
    trades = []
    for i in range(len(day_info) - 1):
        entry = day_info[i]
        if entry["action"] not in ("BUY", "SELL"):
            continue
        next_day = day_info[i + 1]
        entry_price = entry["close"]
        exit_price = next_day["open"] if exit_timing == "open" else next_day["close"]

        pnl_pct = (exit_price - entry_price) / entry_price * 100
        if entry["action"] == "SELL":
            pnl_pct = -pnl_pct

        win = pnl_pct > 0
        option_pnl = pnl_pct * OPTION_MULTIPLIER
        option_pnl = max(min(option_pnl, 45), -45)

        trades.append({
            "symbol": symbol,
            "category": category,
            "entry_date": entry["date"],
            "exit_date": next_day["date"],
            "action": entry["action"],
            "reason": entry["reason"],
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "pnl_pct": round(pnl_pct, 2),
            "win": win,
            "option_pnl_pct": round(option_pnl, 2),
            "exit_timing": exit_timing,
            "crossover": entry["crossover"],
            "ha_signal": entry["ha_signal"],
            "ema_10": entry["ema_10"],
            "ema_20": entry["ema_20"],
        })
    return trades


def compute_summary(trades: list[dict]) -> dict:
    """Compute summary stats from a list of trades."""
    n = len(trades)
    if n == 0:
        return {"total_trades": 0}
    wins = [t for t in trades if t.get("win")]
    losses = [t for t in trades if not t.get("win")]
    win_rate = len(wins) / n * 100 if n else 0
    total_pnl = sum(t["pnl_pct"] for t in trades)
    avg_pnl = total_pnl / n if n else 0
    avg_win = sum(t["pnl_pct"] for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t["pnl_pct"] for t in losses) / len(losses) if losses else 0
    total_option_pnl = sum(t["option_pnl_pct"] for t in trades)
    avg_option_pnl = total_option_pnl / n if n else 0
    max_win = max(t["pnl_pct"] for t in trades) if trades else 0
    max_loss = min(t["pnl_pct"] for t in trades) if trades else 0
    compound = 1.0
    for t in trades:
        compound *= (1 + t["pnl_pct"] / 100)
    compound_return = (compound - 1) * 100
    return {
        "total_trades": n, "win_rate": round(win_rate, 1),
        "wins": len(wins), "losses": len(losses),
        "total_pnl_pct": round(total_pnl, 2),
        "avg_pnl_pct": round(avg_pnl, 2),
        "avg_win_pct": round(avg_win, 2),
        "avg_loss_pct": round(avg_loss, 2),
        "max_win_pct": round(max_win, 2),
        "max_loss_pct": round(max_loss, 2),
        "compound_return_pct": round(compound_return, 2),
        "total_option_pnl_pct": round(total_option_pnl, 2),
        "avg_option_pnl_pct": round(avg_option_pnl, 2),
    }


def run_btst_backtest(
    symbols: list[dict] | None = None,
    period: str = "3mo",
    interval: str = "1h",
    exit_timing: str = "close",
) -> dict:
    """Run BTST backtest on given symbols (uses BTST_SYMBOLS if None)."""
    symbols = symbols or BTST_SYMBOLS
    all_trades: list[dict] = []
    for sym in symbols:
        print(f"  {sym['name']} ({sym['symbol']})...")
        trades = backtest_btst(sym["symbol"], sym["category"], period, interval, exit_timing)
        for t in trades:
            t["display_name"] = sym["name"]
        all_trades.extend(trades)

    by_name: dict[str, list[dict]] = {}
    for t in all_trades:
        by_name.setdefault(t["display_name"], []).append(t)

    per_symbol = {n: compute_summary(ts) for n, ts in sorted(by_name.items())}
    overall = compute_summary(all_trades)

    return {"overall": overall, "per_symbol": per_symbol, "trades": all_trades,
            "symbols_run": [s["name"] for s in symbols],
            "config": {"period": period, "interval": interval, "exit_timing": exit_timing}}


def compare_exit_strategies(
    symbols: list[dict] | None = None,
    period: str = "3mo",
    interval: str = "1h",
) -> dict:
    """Run backtest with both exit_timing="close" and "open", return comparison."""
    results_close = run_btst_backtest(symbols, period, interval, "close")
    results_open = run_btst_backtest(symbols, period, interval, "open")
    return {"close": results_close, "open": results_open}


def get_today_signal(symbol: str, name: str, category: str, interval: str = "15m") -> dict | None:
    """Get BTST signal for today based on last candle of latest data."""
    period = "5d" if interval == "15m" else "10d"
    df = fetch_data(symbol, interval, period)
    if df.empty or len(df) < 25:
        return None
    df["EMA_10"] = compute_ema(df["Close"], 10)
    df["EMA_20"] = compute_ema(df["Close"], 20)
    ha = compute_heikin_ashi(df)
    last_idx = len(df) - 1
    sig = _last_candle_signal(df, ha, last_idx)
    if sig is None:
        return None
    return {
        "name": name,
        "symbol": symbol,
        "category": category,
        "signal": sig["action"],
        "reason": sig["reason"],
        "priority": sig.get("priority", "LOW"),
        "close": round(float(df["Close"].iloc[-1]), 2),
        "ema_10": round(float(df["EMA_10"].iloc[-1]), 2),
        "ema_20": round(float(df["EMA_20"].iloc[-1]), 2),
        "ha_signal": _ha_signal_at_index(ha, last_idx)["signal"],
        "timestamp": str(df.index[-1]),
        "interval": interval,
    }


def generate_btst_report(results: dict, path: Path | None = None) -> Path:
    """Generate Excel report from BTST backtest results."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    hf = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    hfont = Font(bold=True, color="FFFFFF", size=11)
    tb = Border(left=Side(style="thin"), right=Side(style="thin"),
                top=Side(style="thin"), bottom=Side(style="thin"))
    gf = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    rf = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    def wc(ws, row, col, val, font=None, fill=None):
        c = ws.cell(row=row, column=col, value=val)
        if font: c.font = font
        if fill: c.fill = fill
        c.border = tb
        c.alignment = Alignment(horizontal="center", vertical="center")

    ts = datetime.now()
    folder = path or REPORTS_DIR / ts.strftime("%Y%m%d_%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    cfg = results.get("config", {})
    exit_label = cfg.get("exit_timing", "close")
    fname = f"BTST_Backtest_{exit_label}_{ts.strftime('%Y%m%d_%H%M%S')}.xlsx"
    out = folder / fname

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws.cell(row=1, column=1, value=f"BTST Backtest — Exit at {exit_label.upper()}").font = Font(bold=True, size=14)
    ws.cell(row=2, column=1, value=f"Config: {cfg.get('interval','1h')} / {cfg.get('period','3mo')}").font = Font(size=10, italic=True)
    ws.cell(row=3, column=1, value=f"Generated: {ts:%Y-%m-%d %H:%M:%S}").font = Font(size=10, italic=True)

    o = results["overall"]
    row = 5
    for c, h in enumerate(["Metric", "Value"], 1):
        wc(ws, row, c, h, font=hfont, fill=hf)
    row += 1
    for k, v in [
        ("Total Trades", o["total_trades"]),
        ("Win Rate (%)", f"{o['win_rate']}%"),
        ("Wins", o["wins"]), ("Losses", o["losses"]),
        ("Total P&L (%)", f"{o['total_pnl_pct']}%"),
        ("Avg P&L per Trade (%)", f"{o['avg_pnl_pct']}%"),
        ("Avg Win (%)", f"{o['avg_win_pct']}%"),
        ("Avg Loss (%)", f"{o['avg_loss_pct']}%"),
        ("Max Win (%)", f"{o['max_win_pct']}%"),
        ("Max Loss (%)", f"{o['max_loss_pct']}%"),
        ("Compound Return (%)", f"{o['compound_return_pct']}%"),
        ("Total Option P&L (%)", f"{o['total_option_pnl_pct']}%"),
        ("Avg Option P&L (%)", f"{o['avg_option_pnl_pct']}%"),
    ]:
        wc(ws, row, 1, k); wc(ws, row, 2, v); row += 1

    ws2 = wb.create_sheet("Per Symbol")
    sh = ["Symbol", "Trades", "WR%", "Wins", "Loss", "Avg P&L%", "Avg Win%", "Avg Loss%", "Compound%", "Opt P&L%"]
    for c, h in enumerate(sh, 1):
        wc(ws2, 1, c, h, font=hfont, fill=hf)
    for i, (sym, s) in enumerate(sorted(results["per_symbol"].items()), 2):
        vals = [sym, s["total_trades"], f"{s['win_rate']}%", s["wins"], s["losses"],
                f"{s['avg_pnl_pct']}%", f"{s['avg_win_pct']}%", f"{s['avg_loss_pct']}%",
                f"{s['compound_return_pct']}%", f"{s['total_option_pnl_pct']}%"]
        for c, val in enumerate(vals, 1):
            is_pos = (isinstance(val, str) and val.startswith("+")) or (isinstance(val, (int, float)) and val > 0)
            wc(ws2, i, c, val, fill=gf if is_pos else None)

    ws3 = wb.create_sheet("All Trades")
    th = ["Symbol", "Entry", "Exit", "Action", "Reason", "Entry$", "Exit$", "P&L%", "Win", "Opt%"]
    for c, h in enumerate(th, 1):
        wc(ws3, 1, c, h, font=hfont, fill=hf)
    for i, t in enumerate(results["trades"], 2):
        fill = gf if t.get("win") else rf
        for c, val in enumerate([
            t.get("display_name", t["symbol"]), t["entry_date"], t["exit_date"],
            t["action"], t["reason"], t["entry_price"], t["exit_price"],
            f"{t['pnl_pct']}%", "W" if t.get("win") else "L", f"{t['option_pnl_pct']}%",
        ], 1):
            wc(ws3, i, c, val, fill=fill)

    wb.save(out)
    return out


def generate_today_signal_report(signals: list[dict], folder: Path | None = None) -> Path:
    """Generate an Excel report for today's BTST signals (not backtest)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    hf = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    hfont = Font(bold=True, color="FFFFFF", size=11)
    tb = Border(left=Side(style="thin"), right=Side(style="thin"),
                top=Side(style="thin"), bottom=Side(style="thin"))
    gf = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    rf = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    def wc(ws, row, col, val, font=None, fill=None):
        c = ws.cell(row=row, column=col, value=val)
        if font: c.font = font
        if fill: c.fill = fill
        c.border = tb
        c.alignment = Alignment(horizontal="center", vertical="center")

    ts = datetime.now()
    folder = folder or REPORTS_DIR / ts.strftime("%Y%m%d_%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"BTST_TodaySignals_{ts.strftime('%Y%m%d_%H%M%S')}.xlsx"
    out = folder / fname

    wb = Workbook()
    ws = wb.active
    ws.title = "BTST Today Signals"
    ws.cell(row=1, column=1, value=f"BTST Today's Signals — {ts:%Y-%m-%d %H:%M}").font = Font(bold=True, size=14)
    ws.cell(row=2, column=1, value="15m interval data — exit next-day close").font = Font(size=10, italic=True)

    headers = ["Symbol", "Signal", "Options Action", "Close", "Reason", "HA Signal", "EMA 10", "EMA 20", "Category"]
    for c, h in enumerate(headers, 1):
        wc(ws, 4, c, h, font=hfont, fill=hf)

    for i, r in enumerate(signals, 5):
        action = r.get("signal", "NO DATA")
        if action == "NO DATA":
            fill = None
            opt = "NO DATA"
        elif action == "BUY":
            fill = gf
            opt = "BUY Call ATM"
        elif action == "SELL":
            fill = rf
            opt = "BUY Put ATM"
        else:
            fill = None
            opt = "Wait"
        vals = [
            r.get("name", ""),
            action,
            opt,
            r.get("close", ""),
            r.get("reason", ""),
            r.get("ha_signal", ""),
            r.get("ema_10", ""),
            r.get("ema_20", ""),
            r.get("category", ""),
        ]
        for c, val in enumerate(vals, 1):
            wc(ws, i, c, val, fill=fill)

    # Options note at bottom
    note_row = len(signals) + 7
    ws.cell(row=note_row, column=1, value="Options note: ATM option ~18x multiplier. 0.5% underlying move → ~9% option P&L.").font = Font(italic=True, size=10)
    ws.cell(row=note_row + 1, column=1, value="BUY → buy ATM Call. SELL → buy ATM Put. Target next-day close.").font = Font(italic=True, size=10)

    for col in range(1, len(headers) + 1):
        ws.column_dimensions[chr(64 + col)].width = 18

    wb.save(out)

    global TODAY_REPORT
    TODAY_REPORT = out
    return out
