from __future__ import annotations
import pandas as pd
import numpy as np


def compute_heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    ha = df.copy()
    ha["HA_Close"] = (ha["Open"] + ha["High"] + ha["Low"] + ha["Close"]) / 4

    ha_open = [ha["Open"].iloc[0]]
    for i in range(1, len(ha)):
        prev = ha_open[-1]
        prev_close = ha["HA_Close"].iloc[i - 1]
        ha_open.append((prev + prev_close) / 2)
    ha["HA_Open"] = ha_open

    ha["HA_High"] = ha[["High", "HA_Open", "HA_Close"]].max(axis=1)
    ha["HA_Low"] = ha[["Low", "HA_Open", "HA_Close"]].min(axis=1)
    return ha


def detect_ha_signal(ha: pd.DataFrame) -> dict:
    if ha.empty or len(ha) < 3:
        return {"signal": "unknown", "strength": 0}

    last = ha.iloc[-1]
    prev = ha.iloc[-2]
    prev2 = ha.iloc[-3]

    is_green = last["HA_Close"] > last["HA_Open"]
    is_red = last["HA_Close"] < last["HA_Open"]
    no_upper_wick = abs(last["HA_High"] - max(last["HA_Open"], last["HA_Close"])) < 0.01 * (last["HA_High"] - last["HA_Low"] + 1e-9)
    no_lower_wick = abs(min(last["HA_Open"], last["HA_Close"]) - last["HA_Low"]) < 0.01 * (last["HA_High"] - last["HA_Low"] + 1e-9)

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


def scan_early_crossover(ema_short: pd.Series, ema_long: pd.Series, ha_signal: dict) -> dict:
    if len(ema_short) < 2 or len(ema_long) < 2:
        return {"status": "insufficient_data"}

    curr_short = ema_short.iloc[-1]
    curr_long = ema_long.iloc[-1]
    prev_short = ema_short.iloc[-2]
    prev_long = ema_long.iloc[-2]

    already_crossed_up = prev_short <= prev_long and curr_short > curr_long
    is_above = curr_short > curr_long
    near_cross_up = not is_above and (curr_long - curr_short) / (curr_long + 1e-9) < 0.02

    ha_strength = ha_signal.get("strength", 0)

    # ── BUY signals ──
    if already_crossed_up:
        if ha_strength >= 2:
            return {"status": "confirmed_bullish", "action": "BUY", "reason": "Crossed + HA strong buy", "priority": "HIGH"}
        return {"status": "crossed", "action": "WATCH", "reason": "Crossed but HA weak", "priority": "MEDIUM"}

    if near_cross_up and ha_strength >= 2:
        return {"status": "early_bullish", "action": "BUY", "reason": "Near cross + HA strong buy", "priority": "HIGH"}

    if near_cross_up and ha_strength >= 1:
        return {"status": "early_watch", "action": "WATCH", "reason": "Near cross + HA buy", "priority": "MEDIUM"}

    if ha_strength >= 2 and is_above:
        return {"status": "above_with_momentum", "action": "HOLD", "reason": "Above EMA + HA bullish", "priority": "MEDIUM"}

    return {"status": "no_action", "action": "SKIP", "reason": "No signal", "priority": "LOW"}


def scan_sell_signal(ema_short: pd.Series, ema_long: pd.Series, ha_signal: dict) -> dict:
    if len(ema_short) < 2 or len(ema_long) < 2:
        return {"status": "insufficient_data"}

    curr_short = ema_short.iloc[-1]
    curr_long = ema_long.iloc[-1]
    prev_short = ema_short.iloc[-2]
    prev_long = ema_long.iloc[-2]

    already_crossed_down = prev_short >= prev_long and curr_short < curr_long
    is_below = curr_short < curr_long
    near_cross_down = is_below and (curr_long - curr_short) / (curr_long + 1e-9) < 0.02

    ha_strength = ha_signal.get("strength", 0)

    # ── SELL signals ──
    if already_crossed_down:
        if ha_strength <= -2:
            return {"status": "confirmed_bearish", "action": "SELL", "reason": "Bearish cross + HA strong sell", "priority": "HIGH"}
        return {"status": "bearish_crossed", "action": "SELL", "reason": "Bearish cross occurred", "priority": "HIGH"}

    if near_cross_down and ha_strength <= -2:
        return {"status": "early_bearish", "action": "SELL", "reason": "Near bearish cross + HA strong sell", "priority": "HIGH"}

    if near_cross_down and ha_strength <= -1:
        return {"status": "early_bearish_watch", "action": "WATCH", "reason": "Near bearish cross + HA sell", "priority": "MEDIUM"}

    if ha_strength <= -2 and is_below:
        return {"status": "below_with_downtrend", "action": "SELL", "reason": "Below EMA + HA bearish momentum", "priority": "MEDIUM"}

    if ha_strength <= -2:
        return {"status": "ha_strong_sell", "action": "SELL", "reason": "HA strong sell signal", "priority": "HIGH"}

    if ha_strength <= -1:
        return {"status": "ha_sell", "action": "WATCH", "reason": "HA sell signal", "priority": "MEDIUM"}

    return {"status": "no_action", "action": "SKIP", "reason": "No sell signal", "priority": "LOW"}


def scan_combined(ema_short: pd.Series, ema_long: pd.Series, ha_signal: dict) -> dict:
    buy = scan_early_crossover(ema_short, ema_long, ha_signal)
    sell = scan_sell_signal(ema_short, ema_long, ha_signal)

    if buy.get("priority") in ("HIGH", "MEDIUM") and sell.get("priority") in ("HIGH", "MEDIUM"):
        return {"status": "conflict", "action": "WATCH", "reason": f"Buy({buy['reason']}) vs Sell({sell['reason']})", "priority": "MEDIUM"}

    if buy.get("priority") in ("HIGH", "MEDIUM"):
        return buy
    if sell.get("priority") in ("HIGH", "MEDIUM"):
        return sell

    if buy.get("action") != "SKIP":
        return buy
    if sell.get("action") != "SKIP":
        return sell

    return {"status": "no_action", "action": "SKIP", "reason": "No signal", "priority": "LOW"}
