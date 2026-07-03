"""BTST (Buy Today, Sell Tomorrow) — hourly/15m last-hour signal + backtest with options P&L."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

from agentest.utils.indicators.ema import compute_ema
from agentest.utils.indicators.heikin_ashi import compute_heikin_ashi, check_volume
from agentest.utils.indicators.hm import compute_hm_indicators, detect_hm_signal
from agentest.utils.indicators.journal import log_trades
from agentest.utils.indicators.data import fetch_data as _fetch_data

REPORTS_DIR = Path.home() / "Documents" / "Agentest_Reports"
TODAY_REPORT = None  # Set after generate_today_signal_report() runs

INDEX_NAMES = {"NIFTY", "SENSEX", "BANKNIFTY"}

# ── Best-performing symbols from initial backtest ──

BTST_SYMBOLS: list[dict] = [
    {"name": "BAJAJFINSV","symbol": "BAJAJFINSV.NS","category": "large_cap", "sector": "Financial Services"},
    {"name": "BEL",      "symbol": "BEL.NS",       "category": "large_cap", "sector": "Defense & Aerospace"},
    {"name": "KOTAKBANK","symbol": "KOTAKBANK.NS",  "category": "large_cap", "sector": "Banking"},
    {"name": "COALINDIA","symbol": "COALINDIA.NS",  "category": "large_cap", "sector": "Mining (PSU)"},
    {"name": "M&M",      "symbol": "M&M.NS",        "category": "large_cap", "sector": "Automotive"},
    {"name": "DMART",    "symbol": "DMART.NS",      "category": "large_cap", "sector": "Retail"},
    {"name": "DRREDDY",  "symbol": "DRREDDY.NS",    "category": "large_cap", "sector": "Pharma"},
    {"name": "JSWSTEEL", "symbol": "JSWSTEEL.NS",   "category": "large_cap", "sector": "Steel"},
    {"name": "BHARTIARTL","symbol": "BHARTIARTL.NS","category": "large_cap", "sector": "Telecom"},
    {"name": "HDFCLIFE", "symbol": "HDFCLIFE.NS",   "category": "large_cap", "sector": "Insurance"},
    {"name": "SBIN",     "symbol": "SBIN.NS",       "category": "large_cap", "sector": "Banking (PSU)"},
    {"name": "BAJAJ-AUTO","symbol": "BAJAJ-AUTO.NS","category": "large_cap", "sector": "Automotive"},
    {"name": "BANKNIFTY","symbol": "^NSEBANK",      "category": "index",     "sector": "Index"},
    {"name": "NIFTY",    "symbol": "^NSEI",         "category": "index",     "sector": "Index"},
    {"name": "SENSEX",   "symbol": "^BSESN",        "category": "index",     "sector": "Index"},
    {"name": "NTPC",     "symbol": "NTPC.NS",       "category": "large_cap", "sector": "Power"},
    {"name": "ICICIBANK","symbol": "ICICIBANK.NS",  "category": "large_cap", "sector": "Banking"},
]

BTST_SYMBOLS_SECTOR: list[dict] = [
    # ── Indices ──
    {"name": "NIFTY",        "symbol": "^NSEI",      "category": "index",      "sector": "Index"},
    {"name": "SENSEX",       "symbol": "^BSESN",     "category": "index",      "sector": "Index"},
    {"name": "BANKNIFTY",    "symbol": "^NSEBANK",   "category": "index",      "sector": "Index"},

    # ── Banking (Private) ──
    {"name": "HDFCBANK",     "symbol": "HDFCBANK.NS",   "category": "large_cap", "sector": "Banking"},
    {"name": "ICICIBANK",    "symbol": "ICICIBANK.NS",  "category": "large_cap", "sector": "Banking"},
    {"name": "AXISBANK",     "symbol": "AXISBANK.NS",   "category": "large_cap", "sector": "Banking"},
    {"name": "KOTAKBANK",    "symbol": "KOTAKBANK.NS",  "category": "large_cap", "sector": "Banking"},

    # ── Banking (PSU) ──
    {"name": "SBIN",         "symbol": "SBIN.NS",       "category": "large_cap", "sector": "Banking (PSU)"},

    # ── NBFC / Financial Services ──
    {"name": "BAJFINANCE",   "symbol": "BAJFINANCE.NS", "category": "large_cap", "sector": "NBFC"},
    {"name": "BAJAJFINSV",   "symbol": "BAJAJFINSV.NS", "category": "large_cap", "sector": "Financial Services"},

    # ── IT ──
    {"name": "INFY",         "symbol": "INFY.NS",       "category": "large_cap", "sector": "IT"},
    {"name": "HCLTECH",      "symbol": "HCLTECH.NS",    "category": "large_cap", "sector": "IT"},
    {"name": "WIPRO",        "symbol": "WIPRO.NS",      "category": "large_cap", "sector": "IT"},

    # ── FMCG ──
    {"name": "HINDUNILVR",   "symbol": "HINDUNILVR.NS", "category": "large_cap", "sector": "FMCG"},
    {"name": "ITC",          "symbol": "ITC.NS",         "category": "large_cap", "sector": "FMCG"},
    {"name": "DMART",        "symbol": "DMART.NS",       "category": "large_cap", "sector": "Retail"},
    {"name": "GRASIM",       "symbol": "GRASIM.NS",      "category": "large_cap", "sector": "Cement & Textiles"},

    # ── Auto ──
    {"name": "M&M",          "symbol": "M&M.NS",         "category": "large_cap", "sector": "Automotive"},
    {"name": "MARUTI",       "symbol": "MARUTI.NS",      "category": "large_cap", "sector": "Automotive"},
    {"name": "BAJAJ-AUTO",   "symbol": "BAJAJ-AUTO.NS",  "category": "large_cap", "sector": "Automotive"},
    {"name": "EICHERMOT",    "symbol": "EICHERMOT.NS",   "category": "large_cap", "sector": "Automotive"},

    # ── Pharma ──
    {"name": "SUNPHARMA",    "symbol": "SUNPHARMA.NS",   "category": "large_cap", "sector": "Pharma"},
    {"name": "DRREDDY",      "symbol": "DRREDDY.NS",     "category": "large_cap", "sector": "Pharma"},
    {"name": "CIPLA",        "symbol": "CIPLA.NS",       "category": "large_cap", "sector": "Pharma"},

    # ── Telecom ──
    {"name": "BHARTIARTL",   "symbol": "BHARTIARTL.NS",  "category": "large_cap", "sector": "Telecom"},

    # ── Insurance ──
    {"name": "HDFCLIFE",     "symbol": "HDFCLIFE.NS",    "category": "large_cap", "sector": "Insurance"},
    {"name": "LICI",         "symbol": "LICI.NS",         "category": "large_cap", "sector": "Insurance"},

    # ── PSU / Energy ──
    {"name": "COALINDIA",    "symbol": "COALINDIA.NS",    "category": "large_cap", "sector": "Mining (PSU)"},
    {"name": "POWERGRID",    "symbol": "POWERGRID.NS",    "category": "large_cap", "sector": "Power Transmission"},
    {"name": "NTPC",         "symbol": "NTPC.NS",         "category": "large_cap", "sector": "Power"},
    {"name": "ONGC",         "symbol": "ONGC.NS",         "category": "large_cap", "sector": "Oil & Gas"},
    {"name": "BEL",          "symbol": "BEL.NS",          "category": "large_cap", "sector": "Defense & Aerospace"},

    # ── Engineering & Construction ──
    {"name": "LT",           "symbol": "LT.NS",           "category": "large_cap", "sector": "Engineering & Construction"},

    # ── Metals ──
    {"name": "HINDALCO",     "symbol": "HINDALCO.NS",     "category": "large_cap", "sector": "Aluminum & Metals"},
    {"name": "JSWSTEEL",     "symbol": "JSWSTEEL.NS",     "category": "large_cap", "sector": "Steel"},

    # ── Healthcare ──
    {"name": "APOLLOHOSP",   "symbol": "APOLLOHOSP.NS",   "category": "large_cap", "sector": "Healthcare"},

    # ── Consumer / Paints ──
    {"name": "ASIANPAINT",   "symbol": "ASIANPAINT.NS",   "category": "large_cap", "sector": "Paints & Chemicals"},
]

# ── Hilega Milega (HM standalone) top symbols ──
# Includes all BTST symbols + indices so HA & HM run on the same universe.
HM_SYMBOLS: list[dict] = [
    {"name": "BAJAJFINSV","symbol": "BAJAJFINSV.NS","category": "large_cap", "sector": "Financial Services"},
    {"name": "BEL",      "symbol": "BEL.NS",       "category": "large_cap", "sector": "Defense & Aerospace"},
    {"name": "KOTAKBANK","symbol": "KOTAKBANK.NS",  "category": "large_cap", "sector": "Banking"},
    {"name": "COALINDIA","symbol": "COALINDIA.NS",  "category": "large_cap", "sector": "Mining (PSU)"},
    {"name": "M&M",      "symbol": "M&M.NS",        "category": "large_cap", "sector": "Automotive"},
    {"name": "DMART",    "symbol": "DMART.NS",      "category": "large_cap", "sector": "Retail"},
    {"name": "DRREDDY",  "symbol": "DRREDDY.NS",    "category": "large_cap", "sector": "Pharma"},
    {"name": "JSWSTEEL", "symbol": "JSWSTEEL.NS",   "category": "large_cap", "sector": "Steel"},
    {"name": "BHARTIARTL","symbol": "BHARTIARTL.NS","category": "large_cap", "sector": "Telecom"},
    {"name": "HDFCLIFE", "symbol": "HDFCLIFE.NS",   "category": "large_cap", "sector": "Insurance"},
    {"name": "SBIN",     "symbol": "SBIN.NS",       "category": "large_cap", "sector": "Banking (PSU)"},
    {"name": "BAJAJ-AUTO","symbol": "BAJAJ-AUTO.NS","category": "large_cap", "sector": "Automotive"},
    {"name": "BANKNIFTY","symbol": "^NSEBANK",      "category": "index",     "sector": "Index"},
    {"name": "NIFTY",    "symbol": "^NSEI",         "category": "index",     "sector": "Index"},
    {"name": "SENSEX",   "symbol": "^BSESN",        "category": "index",     "sector": "Index"},
    {"name": "NTPC",     "symbol": "NTPC.NS",       "category": "large_cap", "sector": "Power"},
    {"name": "ICICIBANK","symbol": "ICICIBANK.NS",  "category": "large_cap", "sector": "Banking"},
]

OPTION_MULTIPLIER = 18

# ── Backtest config ──
SLIPPAGE_PCT = 0.15        # STT + brokerage round-trip (% of premium)
STOP_LOSS_PCT = 0.3        # underlying % move against → exit
TARGET_PCT = 0.8           # underlying % move in favor → exit
VIX_THRESHOLD = 25         # skip trading when India VIX > this
CAPITAL_BASE = 100_000     # ₹ notional capital
POSITION_SIZES: dict[int, float] = {
    3: 0.10,   # strong_buy/sell    → 10% of capital (full size)
    2: 0.05,   # buy/sell           → 5% (half size)
    1: 0.025,  # weak_buy/sell      → 2.5% (quarter size)
    -1: 0.025, # weak_sell          → 2.5%
    -2: 0.05,  # sell               → 5%
    -3: 0.10,  # strong_sell        → 10%
}
TIER_WEIGHTS = {3: 1.0, 2: 0.5, 1: 0.25}  # for reporting


def fetch_vix(period: str = "3mo") -> pd.DataFrame:
    """Fetch India VIX daily data. Returns DataFrame with columns ['Close'], index = date."""
    try:
        vix = yf.download("^INDIAVIX", period=period, progress=False, auto_adjust=True)
        if vix is None or vix.empty:
            return pd.DataFrame()
        if isinstance(vix.columns, pd.MultiIndex):
            vix.columns = [c[0] for c in vix.columns]
        vix.columns = [c.capitalize() for c in vix.columns]
        vix.index = pd.to_datetime(vix.index.date)
        return vix[["Close"]].copy()
    except Exception:
        return pd.DataFrame()


def fetch_data(symbol: str, interval: str = "1h", period: str = "3mo") -> pd.DataFrame:
    return _fetch_data(symbol, interval, period)


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


def _scan_signal(ema_short: pd.Series, ema_long: pd.Series, ha_signal: dict,
                 volume: pd.Series | None = None) -> dict:
    if len(ema_short) < 2 or len(ema_long) < 2:
        return {"action": "SKIP", "reason": "Insufficient data", "priority": "LOW"}
    curr_s = ema_short.iloc[-1]
    curr_l = ema_long.iloc[-1]
    prev_s = ema_short.iloc[-2]
    prev_l = ema_long.iloc[-2]
    ha_st = ha_signal.get("strength", 0)

    vc = {"confirmed": False, "ratio": 0.0}
    if volume is not None:
        vc = check_volume(volume)

    crossed_up = prev_s <= prev_l and curr_s > curr_l
    is_above = curr_s > curr_l
    near_cross_up = not is_above and (curr_l - curr_s) / (curr_l + 1e-9) < 0.02
    crossed_down = prev_s >= prev_l and curr_s < curr_l
    is_below = curr_s < curr_l
    near_cross_down = is_below and (curr_l - curr_s) / (curr_l + 1e-9) < 0.02

    result: dict = {"volume_confirmed": vc["confirmed"], "volume_ratio": vc["ratio"]}

    # BUY checks
    if crossed_up and ha_st >= 2:
        reason = "Crossed + HA strong buy"
        priority = "HIGH"
        if volume is not None and not vc["confirmed"]:
            priority = "MEDIUM"
            reason += " (low vol)"
        result.update({"action": "BUY", "reason": reason, "priority": priority}); return result
    if crossed_up:
        result.update({"action": "WATCH", "reason": "Crossed but HA weak", "priority": "MEDIUM"}); return result
    if near_cross_up and ha_st >= 2:
        result.update({"action": "BUY", "reason": "Near cross + HA strong buy", "priority": "HIGH"}); return result
    if ha_st >= 2 and is_above:
        result.update({"action": "HOLD", "reason": "Above EMA + HA bullish", "priority": "MEDIUM"}); return result

    # SELL checks
    if crossed_down and ha_st <= -2:
        reason = "Bearish cross + HA strong sell"
        priority = "HIGH"
        if volume is not None and not vc["confirmed"]:
            priority = "MEDIUM"
            reason += " (low vol)"
        result.update({"action": "SELL", "reason": reason, "priority": priority}); return result
    if crossed_down:
        result.update({"action": "SELL", "reason": "Bearish cross", "priority": "HIGH"}); return result
    if near_cross_down and ha_st <= -2:
        result.update({"action": "SELL", "reason": "Near bearish cross + HA strong sell", "priority": "HIGH"}); return result
    if ha_st <= -2 and is_below:
        result.update({"action": "SELL", "reason": "Below EMA + HA bearish", "priority": "MEDIUM"}); return result
    if ha_st <= -2:
        result.update({"action": "SELL", "reason": "HA strong sell", "priority": "HIGH"}); return result
    if ha_st >= 2:
        result.update({"action": "BUY", "reason": "HA strong buy", "priority": "HIGH"}); return result

    result.update({"action": "SKIP", "reason": "No signal", "priority": "LOW"})
    return result


def _last_candle_signal(df: pd.DataFrame, ha: pd.DataFrame, iloc_pos: int) -> dict | None:
    """Compute signal for a specific candle position."""
    if iloc_pos < 2:
        return None
    ema_short = df["EMA_10"]
    ema_long = df["EMA_20"]
    if pd.isna(ema_short.iloc[iloc_pos]) or pd.isna(ema_long.iloc[iloc_pos]):
        return None
    ha_sig = _ha_signal_at_index(ha, iloc_pos)
    volume = df["Volume"] if "Volume" in df.columns else None
    scan = _scan_signal(ema_short.iloc[:iloc_pos + 1], ema_long.iloc[:iloc_pos + 1], ha_sig, volume)
    return scan


TRAIL_ACTIVATE_PCT = 0.5  # % favorable move to activate trailing
TRAIL_STOP_PCT = 0.3      # trail distance below peak


def _exit_by_target_stop(
    entry_action: str, entry_price: float,
    next_open: float, next_high: float, next_low: float, next_close: float,
    target_pct: float, stop_pct: float,
    trailing: bool = False,
) -> tuple[str, float, float]:
    """Determine exit.
    Handles gap fills: if next_open gapped past the stop, use next_open as fill price.
    If trailing=True: activates breakeven at 0.5%, then trails 0.3% below peak.
    Returns (exit_reason, exit_price, underlying_pnl_pct).
    """
    if trailing:
        if entry_action == "BUY":
            activate = entry_price * (1 + TRAIL_ACTIVATE_PCT / 100)
            target_price = entry_price * (1 + target_pct / 100)
            stop_price = entry_price * (1 - stop_pct / 100)

            # Gap down past stop — fill at open
            if next_open <= stop_price:
                pnl = (next_open - entry_price) / entry_price * 100
                return "gap_stop", next_open, pnl

            if next_high >= target_price:
                return "target", target_price, target_pct
            if next_high >= activate:
                stop_price = entry_price
                trail_stop = next_high * (1 - TRAIL_STOP_PCT / 100)
                stop_price = max(stop_price, trail_stop)
            if next_low <= stop_price:
                pnl = (stop_price - entry_price) / entry_price * 100
                return "stop", stop_price, pnl
            pnl = (next_close - entry_price) / entry_price * 100
            return "close", next_close, pnl
        else:  # SELL (put)
            activate = entry_price * (1 - TRAIL_ACTIVATE_PCT / 100)
            target_price = entry_price * (1 - target_pct / 100)
            stop_price = entry_price * (1 + stop_pct / 100)

            # Gap up past stop — fill at open
            if next_open >= stop_price:
                pnl = (entry_price - next_open) / entry_price * 100
                return "gap_stop", next_open, pnl

            if next_low <= target_price:
                return "target", target_price, target_pct
            if next_low <= activate:
                stop_price = entry_price
                trail_stop = next_low * (1 + TRAIL_STOP_PCT / 100)
                stop_price = min(stop_price, trail_stop)
            if next_high >= stop_price:
                pnl = (entry_price - stop_price) / entry_price * 100
                return "stop", stop_price, pnl
            pnl = (entry_price - next_close) / entry_price * 100
            return "close", next_close, pnl

    # Original fixed stop/target
    if entry_action == "BUY":
        target_price = entry_price * (1 + target_pct / 100)
        stop_price = entry_price * (1 - stop_pct / 100)

        if next_open <= stop_price:
            pnl = (next_open - entry_price) / entry_price * 100
            return "gap_stop", next_open, pnl

        if next_high >= target_price:
            return "target", target_price, target_pct
        if next_low <= stop_price:
            return "stop", stop_price, -stop_pct
        pnl = (next_close - entry_price) / entry_price * 100
        return "close", next_close, pnl
    else:
        target_price = entry_price * (1 - target_pct / 100)
        stop_price = entry_price * (1 + stop_pct / 100)

        if next_open >= stop_price:
            pnl = (entry_price - next_open) / entry_price * 100
            return "gap_stop", next_open, pnl

        if next_low <= target_price:
            return "target", target_price, target_pct
        if next_high >= stop_price:
            return "stop", stop_price, -stop_pct
        pnl = (entry_price - next_close) / entry_price * 100
        return "close", next_close, pnl


def backtest_btst(
    symbol: str,
    category: str,
    period: str = "3mo",
    interval: str = "1h",
    exit_timing: str = "trailing",
    capital: float = CAPITAL_BASE,
    sector: str = "",
) -> list[dict]:
    """
    BTST backtest with VIX filter, trailing stop, tiered position sizing, slippage.

    Parameters
    ----------
    exit_timing : "close", "open", "trailing" (default: trailing with 0.5% activation)
    sector : sector label for grouping
    """
    df = fetch_data(symbol, interval, period)
    if df.empty:
        return []

    vix_df = fetch_vix(period)
    vix_lookup: dict[str, float] = {}
    if not vix_df.empty:
        for dt, row in vix_df.iterrows():
            vix_lookup[str(dt.date())] = float(row["Close"])

    df["EMA_10"] = compute_ema(df["Close"], 10)
    df["EMA_20"] = compute_ema(df["Close"], 20)
    ha = compute_heikin_ashi(df)

    df["date"] = df.index.date
    day_groups = list(df.groupby("date"))

    day_info: list[dict] = []
    for date, day_df in day_groups:
        day_df = day_df.sort_index()
        last_global_idx = day_df.index[-1]
        iloc_pos = df.index.get_loc(last_global_idx)

        sig = _last_candle_signal(df, ha, iloc_pos)
        ha_sig = _ha_signal_at_index(ha, iloc_pos) if iloc_pos >= 2 else {"signal": "unknown", "strength": 0}
        vol_conf = sig.get("volume_confirmed", False) if sig else False
        vol_ratio = sig.get("volume_ratio", 0.0) if sig else 0.0
        entry = {
            "date": str(date),
            "open": float(day_df["Open"].iloc[0]),
            "high": float(day_df["High"].max()),
            "low": float(day_df["Low"].min()),
            "close": float(day_df["Close"].iloc[-1]),
            "action": sig["action"] if sig else "SKIP",
            "reason": sig["reason"] if sig else "No signal",
            "ha_signal": ha_sig["signal"],
            "ha_strength": ha_sig["strength"],
            "volume_confirmed": vol_conf,
            "volume_ratio": round(vol_ratio, 2),
            "ema_10": round(float(df["EMA_10"].iloc[iloc_pos]), 2) if pd.notna(df["EMA_10"].iloc[iloc_pos]) else 0,
            "ema_20": round(float(df["EMA_20"].iloc[iloc_pos]), 2) if pd.notna(df["EMA_20"].iloc[iloc_pos]) else 0,
        }
        entry["vix"] = vix_lookup.get(entry["date"], None)
        day_info.append(entry)

    trades = []
    for i in range(len(day_info) - 1):
        entry = day_info[i]
        if entry["action"] not in ("BUY", "SELL"):
            continue

        vix_val = entry.get("vix")
        if vix_val is not None and vix_val > VIX_THRESHOLD:
            continue

        next_day = day_info[i + 1]
        entry_price = entry["close"]

        is_trailing = exit_timing == "trailing"
        if exit_timing == "open":
            exit_price = next_day["open"]
            exit_reason = "open"
            underlying_pnl = (exit_price - entry_price) / entry_price * 100
            if entry["action"] == "SELL":
                underlying_pnl = -underlying_pnl
        else:
            exit_reason, exit_price, underlying_pnl = _exit_by_target_stop(
                entry["action"], entry_price,
                next_day["open"], next_day["high"], next_day["low"], next_day["close"],
                TARGET_PCT, STOP_LOSS_PCT, trailing=is_trailing,
            )

        win = underlying_pnl > 0
        option_pnl_pct = underlying_pnl * OPTION_MULTIPLIER
        option_pnl_pct = max(min(option_pnl_pct, 45), -45)
        option_pnl_pct -= SLIPPAGE_PCT

        # Tiered position sizing
        ha_strength = entry.get("ha_strength", 0)
        base_size = POSITION_SIZES.get(ha_strength, 0.025)
        premium_rs = round(capital * base_size, 0)
        option_pnl_rs = round(premium_rs * option_pnl_pct / 100, 0)
        pnl_rs = round(premium_rs * underlying_pnl / 100, 0)

        trade = {
            "symbol": symbol,
            "category": category,
            "sector": sector,
            "entry_date": entry["date"],
            "exit_date": next_day["date"],
            "action": entry["action"],
            "reason": entry["reason"],
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "exit_reason": exit_reason,
            "pnl_pct": round(underlying_pnl, 2),
            "win": win,
            "ha_strength": ha_strength,
            "position_size_pct": round(base_size * 100, 1),
            "premium_rs": int(premium_rs),
            "pnl_rs": int(pnl_rs),
            "option_pnl_pct": round(option_pnl_pct, 2),
            "option_pnl_rs": int(option_pnl_rs),
            "vix_at_entry": vix_val,
            "exit_timing": exit_timing,
            "ha_signal": entry["ha_signal"],
            "volume_confirmed": entry["volume_confirmed"],
            "volume_ratio": entry["volume_ratio"],
            "ema_10": entry["ema_10"],
            "ema_20": entry["ema_20"],
        }
        trades.append(trade)

    return trades


# ── HM Backtest ──


def backtest_btst_hm(
    symbol: str,
    category: str,
    period: str = "3mo",
    interval: str = "1h",
    exit_timing: str = "trailing",
    capital: float = CAPITAL_BASE,
    sector: str = "",
) -> list[dict]:
    """BTST backtest using HM (Hilega Milega) signals instead of EMA+HA."""
    df = fetch_data(symbol, interval, period)
    if df.empty:
        return []

    vix_df = fetch_vix(period)
    vix_lookup: dict[str, float] = {}
    if not vix_df.empty:
        for dt, row in vix_df.iterrows():
            vix_lookup[str(dt.date())] = float(row["Close"])

    df = compute_hm_indicators(df)

    df["date"] = df.index.date
    day_groups = list(df.groupby("date"))

    day_info: list[dict] = []
    for date, day_df in day_groups:
        day_df = day_df.sort_index()
        last_idx = len(df) - 1
        iloc_pos = df.index.get_loc(day_df.index[-1])

        hm_sig = detect_hm_signal(df.iloc[:iloc_pos + 1])
        action = hm_sig.get("signal", "WATCH")
        reason = hm_sig.get("reason", "")
        # Map HM signals to BTST actions
        btst_action = "BUY" if action == "BUY" else "SELL" if action == "SELL" else "SKIP"
        hm_priority = hm_sig.get("priority", "LOW")

        entry = {
            "date": str(date),
            "open": float(day_df["Open"].iloc[0]),
            "high": float(day_df["High"].max()),
            "low": float(day_df["Low"].min()),
            "close": float(day_df["Close"].iloc[-1]),
            "action": btst_action,
            "reason": reason,
            "hm_signal": action,
            "hm_priority": hm_priority,
            "volume_confirmed": False,
            "volume_ratio": 0.0,
        }
        entry["vix"] = vix_lookup.get(entry["date"], None)
        day_info.append(entry)

    trades = []
    for i in range(len(day_info) - 1):
        entry = day_info[i]
        if entry["action"] not in ("BUY", "SELL"):
            continue

        vix_val = entry.get("vix")
        if vix_val is not None and vix_val > VIX_THRESHOLD:
            continue

        next_day = day_info[i + 1]
        entry_price = entry["close"]

        is_trailing = exit_timing == "trailing"
        if exit_timing == "open":
            exit_price = next_day["open"]
            exit_reason = "open"
            underlying_pnl = (exit_price - entry_price) / entry_price * 100
            if entry["action"] == "SELL":
                underlying_pnl = -underlying_pnl
        else:
            exit_reason, exit_price, underlying_pnl = _exit_by_target_stop(
                entry["action"], entry_price,
                next_day["open"], next_day["high"], next_day["low"], next_day["close"],
                TARGET_PCT, STOP_LOSS_PCT, trailing=is_trailing,
            )

        win = underlying_pnl > 0
        option_pnl_pct = underlying_pnl * OPTION_MULTIPLIER
        option_pnl_pct = max(min(option_pnl_pct, 45), -45)
        option_pnl_pct -= SLIPPAGE_PCT

        base_size = 0.05  # fixed 5% for HM
        premium_rs = round(capital * base_size, 0)
        option_pnl_rs = round(premium_rs * option_pnl_pct / 100, 0)
        pnl_rs = round(premium_rs * underlying_pnl / 100, 0)

        trade = {
            "symbol": symbol,
            "category": category,
            "sector": sector,
            "entry_date": entry["date"],
            "exit_date": next_day["date"],
            "action": entry["action"],
            "reason": entry["reason"],
            "entry_price": round(entry_price, 2),
            "exit_price": round(exit_price, 2),
            "exit_reason": exit_reason,
            "pnl_pct": round(underlying_pnl, 2),
            "win": win,
            "ha_strength": 2,
            "position_size_pct": round(base_size * 100, 1),
            "premium_rs": int(premium_rs),
            "pnl_rs": int(pnl_rs),
            "option_pnl_pct": round(option_pnl_pct, 2),
            "option_pnl_rs": int(option_pnl_rs),
            "vix_at_entry": vix_val,
            "exit_timing": exit_timing,
            "hm_signal": entry["hm_signal"],
            "volume_confirmed": False,
            "volume_ratio": 0.0,
            "ema_10": 0, "ema_20": 0,
        }
        trades.append(trade)

    return trades


def run_btst_backtest_hm(
    symbols: list[dict] | None = None,
    period: str = "3mo",
    interval: str = "1h",
    exit_timing: str = "trailing",
    capital: float = CAPITAL_BASE,
) -> dict:
    """Run HM BTST backtest on given symbols (uses BTST_SYMBOLS if None)."""
    symbols = symbols or BTST_SYMBOLS
    all_trades: list[dict] = []
    for sym in symbols:
        print(f"  {sym['name']} ({sym['symbol']})...")
        sector = sym.get("sector", sym.get("category", ""))
        trades = backtest_btst_hm(sym["symbol"], sym["category"], period, interval, exit_timing, capital, sector)
        for t in trades:
            t["display_name"] = sym["name"]
        all_trades.extend(trades)

    by_name: dict[str, list[dict]] = {}
    for t in all_trades:
        by_name.setdefault(t["display_name"], []).append(t)

    by_sector: dict[str, list[dict]] = {}
    for t in all_trades:
        sec = t.get("sector", "Other")
        by_sector.setdefault(sec, []).append(t)

    per_symbol = {n: compute_summary(ts, capital) for n, ts in sorted(by_name.items())}
    overall = compute_summary(all_trades, capital)
    sector_summary = {s: compute_summary(ts, capital) for s, ts in sorted(by_sector.items())}

    from agentest.utils.indicators.journal import log_trades
    log_trades(all_trades, strategy=f"hm_btst_{exit_timing}")

    return {"overall": overall, "per_symbol": per_symbol, "sector_summary": sector_summary,
            "trades": all_trades, "symbols_run": [s["name"] for s in symbols],
            "config": {"period": period, "interval": interval, "exit_timing": exit_timing,
                       "capital": int(capital), "vix_threshold": VIX_THRESHOLD,
                       "stop_loss_pct": STOP_LOSS_PCT, "target_pct": TARGET_PCT,
                       "slippage_pct": SLIPPAGE_PCT}}


def compute_summary(trades: list[dict], capital: float = CAPITAL_BASE) -> dict:
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

    # Rupee P&L (position-sized)
    total_pnl_rs = sum(t.get("pnl_rs", 0) for t in trades)
    total_option_pnl_rs = sum(t.get("option_pnl_rs", 0) for t in trades)
    total_premium_rs = sum(t.get("premium_rs", 0) for t in trades)
    roi_pct = (total_pnl_rs / capital * 100) if capital else 0
    option_roi_pct = (total_option_pnl_rs / capital * 100) if capital else 0

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
        "total_pnl_rs": int(total_pnl_rs),
        "total_option_pnl_rs": int(total_option_pnl_rs),
        "total_premium_deployed_rs": int(total_premium_rs),
        "roi_pct": round(roi_pct, 2),
        "option_roi_pct": round(option_roi_pct, 2),
    }


def run_btst_backtest(
    symbols: list[dict] | None = None,
    period: str = "3mo",
    interval: str = "1h",
    exit_timing: str = "trailing",
    capital: float = CAPITAL_BASE,
) -> dict:
    """Run BTST backtest on given symbols (uses BTST_SYMBOLS if None)."""
    symbols = symbols or BTST_SYMBOLS
    all_trades: list[dict] = []
    for sym in symbols:
        print(f"  {sym['name']} ({sym['symbol']})...")
        sector = sym.get("sector", sym.get("category", ""))
        trades = backtest_btst(sym["symbol"], sym["category"], period, interval, exit_timing, capital, sector)
        for t in trades:
            t["display_name"] = sym["name"]
        all_trades.extend(trades)

    by_name: dict[str, list[dict]] = {}
    for t in all_trades:
        by_name.setdefault(t["display_name"], []).append(t)

    # Sector grouping
    by_sector: dict[str, list[dict]] = {}
    for t in all_trades:
        sec = t.get("sector", "Other")
        by_sector.setdefault(sec, []).append(t)

    per_symbol = {n: compute_summary(ts, capital) for n, ts in sorted(by_name.items())}
    overall = compute_summary(all_trades, capital)
    sector_summary = {s: compute_summary(ts, capital) for s, ts in sorted(by_sector.items())}

    log_trades(all_trades, strategy=f"btst_{exit_timing}")

    return {"overall": overall, "per_symbol": per_symbol, "sector_summary": sector_summary,
            "trades": all_trades, "symbols_run": [s["name"] for s in symbols],
            "config": {"period": period, "interval": interval, "exit_timing": exit_timing,
                       "capital": int(capital), "vix_threshold": VIX_THRESHOLD,
                       "stop_loss_pct": STOP_LOSS_PCT, "target_pct": TARGET_PCT,
                       "slippage_pct": SLIPPAGE_PCT, "tier_weights": TIER_WEIGHTS}}


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

    # VIX check
    vix_df = fetch_vix("1mo")
    vix_val = None
    if not vix_df.empty:
        vix_val = float(vix_df["Close"].iloc[-1])
    vix_warning = vix_val > VIX_THRESHOLD if vix_val is not None else False

    # Position sizing
    ha_sig = _ha_signal_at_index(ha, last_idx)
    ha_strength = ha_sig["strength"]
    pos_pct = POSITION_SIZES.get(ha_strength, POSITION_SIZES.get(2 if abs(ha_strength) >= 2 else 1, 0.05))
    premium_rs = int(CAPITAL_BASE * pos_pct)

    return {
        "name": name,
        "symbol": symbol,
        "category": category,
        "strategy": "EMA+HA",
        "signal": sig["action"],
        "reason": sig["reason"],
        "priority": sig.get("priority", "LOW"),
        "close": round(float(df["Close"].iloc[-1]), 2),
        "ema_10": round(float(df["EMA_10"].iloc[-1]), 2),
        "ema_20": round(float(df["EMA_20"].iloc[-1]), 2),
        "ha_signal": ha_sig["signal"],
        "ha_strength": ha_strength,
        "volume_confirmed": sig.get("volume_confirmed", False),
        "volume_ratio": sig.get("volume_ratio", 0.0),
        "vix": round(vix_val, 1) if vix_val is not None else None,
        "vix_warning": vix_warning,
        "position_size_pct": round(pos_pct * 100, 1),
        "recommended_premium_rs": premium_rs,
        "timestamp": str(df.index[-1]),
        "interval": interval,
    }


# ── Hilega Milega (HM) standalone ──


def get_today_signal_hm(symbol: str, name: str, category: str, interval: str = "15m") -> dict | None:
    period = "5d" if interval == "15m" else "10d"
    df = fetch_data(symbol, interval, period)
    if df.empty or len(df) < 25:
        return None
    df = compute_hm_indicators(df)
    sig = detect_hm_signal(df)
    last = df.iloc[-1]

    vix_df = fetch_vix("1mo")
    vix_val = float(vix_df["Close"].iloc[-1]) if not vix_df.empty else None
    vix_warning = vix_val > VIX_THRESHOLD if vix_val is not None else False

    return {
        "name": name,
        "symbol": symbol,
        "category": category,
        "signal": sig["signal"],
        "reason": sig["reason"],
        "priority": sig["priority"],
        "strategy": "HM",
        "close": round(float(last["Close"]), 2) if pd.notna(last["Close"]) else None,
        "rsi9": round(float(last["RSI9"]), 2) if pd.notna(last.get("RSI9")) else None,
        "speed": round(float(last["Speed"]), 2) if pd.notna(last.get("Speed")) else None,
        "strength": round(float(last["Strength"]), 2) if pd.notna(last.get("Strength")) else None,
        "vix": round(vix_val, 1) if vix_val is not None else None,
        "vix_warning": vix_warning,
        "position_size_pct": 5.0,
        "recommended_premium_rs": int(CAPITAL_BASE * 0.05),
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
    strategy_label = {"trailing": "Trailing", "close": "Close", "open": "Open"}.get(exit_label, exit_label)
    fname = f"BTST_Backtest_{exit_label}_{ts.strftime('%Y%m%d_%H%M%S')}.xlsx"
    out = folder / fname

    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    cap_display = f"₹{cfg.get('capital', 100000):,}"
    ws.cell(row=1, column=1, value=f"BTST Backtest — {strategy_label} strategy").font = Font(bold=True, size=14)
    tier_info = ""
    tw = cfg.get("tier_weights", {})
    if tw:
        tier_info = f" | Tiers: str3={tw.get(3,1.0)*100:.0f}% str2={tw.get(2,0.5)*100:.0f}% str1={tw.get(1,0.25)*100:.0f}%"
    ws.cell(row=2, column=1, value=f"Capital: {cap_display} | SL: {cfg.get('stop_loss_pct',0.3)}% / Tgt: {cfg.get('target_pct',0.8)}% | VIX > {cfg.get('vix_threshold',25)} skip | Slippage: {cfg.get('slippage_pct',0.15)}%{tier_info}").font = Font(size=10, italic=True)
    ws.cell(row=3, column=1, value=f"Generated: {ts:%Y-%m-%d %H:%M:%S}").font = Font(size=10, italic=True)

    o = results["overall"]
    row = 5
    # Strategy description
    if exit_label == "trailing":
        ws.cell(row=row, column=1, value="Trailing: activate at 0.5% gain → breakeven, then trail 0.3% below peak").font = Font(italic=True, size=10, color="555555")
        row += 1
    for c, h in enumerate(["Metric", "Value"], 1):
        wc(ws, row, c, h, font=hfont, fill=hf)
    row += 1

    vol_cnf_trades = sum(1 for t in results["trades"] if t.get("volume_confirmed"))
    vol_cnf_pct = round(vol_cnf_trades / o["total_trades"] * 100, 1) if o["total_trades"] else 0

    for k, v in [
        ("Total Trades", o["total_trades"]),
        ("Win Rate (%)", f"{o['win_rate']}%"),
        ("Wins", o["wins"]), ("Losses", o["losses"]),
        ("Total P&L (%)", f"{o['total_pnl_pct']}%"),
        ("Avg P&L per Trade (%)", f"{o['avg_pnl_pct']}%"),
        ("Compound Return (%)", f"{o['compound_return_pct']}%"),
        ("Total Option P&L (%)", f"{o['total_option_pnl_pct']}%"),
        ("Volume Confirmed", f"{vol_cnf_trades}/{o['total_trades']} ({vol_cnf_pct}%)"),
        ("", ""),
        ("--- Rupee P&L (capital-based) ---", ""),
        ("Total P&L (₹)", f"₹{o['total_pnl_rs']:,}"),
        ("Total Option P&L (₹)", f"₹{o['total_option_pnl_rs']:,}"),
        ("Premium Deployed (₹)", f"₹{o['total_premium_deployed_rs']:,}"),
        ("ROI (%)", f"{o['roi_pct']}%"),
        ("Option ROI (%)", f"{o['option_roi_pct']}%"),
    ]:
        wc(ws, row, 1, k); wc(ws, row, 2, v); row += 1

    ws2 = wb.create_sheet("Per Symbol")
    sh = ["Symbol", "Trades", "WR%", "Wins", "Loss", "Compound%", "Opt P&L%", "Opt ₹", "ROI%",
          "VolCnf%"]
    for c, h in enumerate(sh, 1):
        wc(ws2, 1, c, h, font=hfont, fill=hf)
    for i, (sym, s) in enumerate(sorted(results["per_symbol"].items()), 2):
        sym_trades = [t for t in results["trades"] if t.get("display_name", t["symbol"]) == sym]
        vol_cnf = sum(1 for t in sym_trades if t.get("volume_confirmed"))
        vol_cnf_pct = round(vol_cnf / len(sym_trades) * 100, 1) if sym_trades else 0
        vals = [sym, s["total_trades"], f"{s['win_rate']}%", s["wins"], s["losses"],
                f"{s['compound_return_pct']}%", f"{s['total_option_pnl_pct']}%",
                f"₹{s.get('total_option_pnl_rs', 0):,}", f"{s.get('option_roi_pct', 0)}%",
                f"{vol_cnf_pct}%"]
        for c, val in enumerate(vals, 1):
            is_pos = (isinstance(val, str) and val.startswith("+")) or (isinstance(val, (int, float)) and val > 0)
            wc(ws2, i, c, val, fill=gf if is_pos else None)

    # ── By Sector Sheet ──
    if "sector_summary" in results and results["sector_summary"]:
        ws_sec = wb.create_sheet("By Sector")
        sec_headers = ["Sector", "Symbols", "Trades", "WR%", "Wins", "Loss", "Compound%", "Opt ₹", "ROI%"]
        for c, h in enumerate(sec_headers, 1):
            wc(ws_sec, 1, c, h, font=hfont, fill=hf)
        sec_data = []
        for sec, s in sorted(results["sector_summary"].items()):
            syms_in_sec = [t.get("display_name", "") for t in results["trades"] if t.get("sector") == sec]
            unique = len(set(syms_in_sec))
            sec_data.append((sec, unique, s["total_trades"], s["win_rate"], s["wins"], s["losses"],
                             s["compound_return_pct"], s.get("total_option_pnl_rs", 0), s.get("option_roi_pct", 0)))
        # Sort by WR descending
        sec_data.sort(key=lambda x: x[3], reverse=True)
        for i, (sec, n_sym, n, wr, wins, losses, cmp, opt_rs, roi) in enumerate(sec_data, 2):
            vals = [sec, n_sym, n, f"{wr}%", wins, losses, f"{cmp}%", f"₹{opt_rs:,}", f"{roi}%"]
            for c, val in enumerate(vals, 1):
                wc(ws_sec, i, c, val, fill=gf if wr >= 60 else None)

    ws3 = wb.create_sheet("All Trades")
    th = ["Symbol", "Entry", "Exit", "Action", "Exit By", "Reason", "Entry$", "Exit$", "P&L%",
          "Win", "Size%", "Prem₹", "Opt%", "Opt₹", "VIX", "VolCnf", "VolRat"]
    for c, h in enumerate(th, 1):
        wc(ws3, 1, c, h, font=hfont, fill=hf)
    for i, t in enumerate(results["trades"], 2):
        fill = gf if t.get("win") else rf
        for c, val in enumerate([
            t.get("display_name", t["symbol"]), t["entry_date"], t["exit_date"],
            t["action"], t.get("exit_reason", "close"), t["reason"],
            t["entry_price"], t["exit_price"],
            f"{t['pnl_pct']}%", "W" if t.get("win") else "L",
            t.get("position_size_pct", ""), t.get("premium_rs", ""),
            f"{t['option_pnl_pct']}%", t.get("option_pnl_rs", ""),
            t.get("vix_at_entry", ""),
            "Y" if t.get("volume_confirmed") else "N",
            t.get("volume_ratio", ""),
        ], 1):
            wc(ws3, i, c, val, fill=fill)

    wb.save(out)
    return out


def _write_signal_sheet(ws, signals, title):
    """Write signal rows into a worksheet. title shown as subtitle."""
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    hf = PatternFill(start_color="2C3E50", end_color="2C3E50", fill_type="solid")
    hfont = Font(bold=True, color="FFFFFF", size=11)
    tb = Border(left=Side(style="thin"), right=Side(style="thin"),
                top=Side(style="thin"), bottom=Side(style="thin"))
    gf = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    rf = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")

    def wc(row, col, val, font=None, fill=None):
        c = ws.cell(row=row, column=col, value=val)
        if font: c.font = font
        if fill: c.fill = fill
        c.border = tb
        c.alignment = Alignment(horizontal="center", vertical="center")

    ws.cell(row=1, column=1, value=f"BTST Today's Signals — {title}").font = Font(bold=True, size=14)
    ws.cell(row=2, column=1, value="15m interval — trailing stop (activate 0.5%, trail 0.3%)").font = Font(size=10, italic=True)

    headers = ["Symbol", "Strategy", "Signal", "Options Action", "Close", "Reason",
               "HA/HM Signal", "HA Str", "VIX", "VolCnf", "Premium ₹", "Category"]
    for c, h in enumerate(headers, 1):
        wc(4, c, h, font=hfont, fill=hf)

    for i, r in enumerate(signals, 5):
        action = r.get("signal", "NO DATA")
        vix_warn = r.get("vix_warning", False)
        strat = r.get("strategy", "HA")
        if action == "NO DATA":
            fill = None
            opt = "NO DATA"
        elif action == "BUY":
            fill = gf if not vix_warn else None
            opt = "BUY Call ATM"
        elif action == "SELL":
            fill = rf if not vix_warn else None
            opt = "BUY Put ATM"
        elif action == "HOLD":
            fill = None
            opt = "Hold"
        else:
            fill = None
            opt = "Wait"

        ha_detail = r.get("ha_signal", "")
        if not ha_detail and strat == "HM":
            ha_detail = f"RSI{r.get('rsi9','')}" if r.get("rsi9") else ""

        vix_display = f"{r.get('vix', '')}" + (" ⚠ HIGH" if vix_warn else "")
        vol_display = "Y" if r.get("volume_confirmed") else "N"
        vals = [
            r.get("name", ""), strat, action, opt,
            r.get("close", ""), r.get("reason", ""),
            ha_detail, r.get("ha_strength", ""),
            vix_display, vol_display,
            r.get("recommended_premium_rs", ""), r.get("category", ""),
        ]
        for c, val in enumerate(vals, 1):
            wc(i, c, val, fill=fill)

    note_row = len(signals) + 7
    ws.cell(row=note_row, column=1, value=f"Capital: ₹{CAPITAL_BASE:,} | Position sizing: 4-10% per trade based on signal strength (₹4,000-₹10,000)").font = Font(italic=True, size=10)
    ws.cell(row=note_row + 1, column=1, value="Options note: ATM option ~18x multiplier. BUY→Call, SELL→Put. VIX > 25 → skip.").font = Font(italic=True, size=10)

    for col in range(1, len(headers) + 1):
        ws.column_dimensions[chr(64 + col)].width = 18


def generate_today_signal_report(signals: list[dict], folder: Path | None = None) -> Path:
    """Generate an Excel report for today's BTST signals — two sheets: Indices + All Signals."""
    from openpyxl import Workbook

    ts = datetime.now()
    folder = folder or REPORTS_DIR / ts.strftime("%Y%m%d_%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    fname = f"BTST_TodaySignals_{ts.strftime('%Y%m%d_%H%M%S')}.xlsx"
    out = folder / fname

    idx_signals = [r for r in signals if r.get("name") in INDEX_NAMES]
    stock_signals = [r for r in signals if r.get("name") not in INDEX_NAMES]

    wb = Workbook()

    # Sheet 1: Indices
    ws_idx = wb.active
    ws_idx.title = "Indices"
    _write_signal_sheet(ws_idx, idx_signals, "Indices")

    # Sheet 2: All Signals
    ws_all = wb.create_sheet("All Signals")
    _write_signal_sheet(ws_all, stock_signals, "All Stocks (HA + HM)")

    wb.save(out)

    global TODAY_REPORT
    TODAY_REPORT = out
    return out
