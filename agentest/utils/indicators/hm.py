"""HM (Hilega Milega) — RSI9, WMA, and standalone HM signal detection."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rsi9(series: pd.Series) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_g = gain.rolling(9).mean()
    avg_l = loss.rolling(9).mean().replace(0, np.nan)
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))


def wma(series: pd.Series, length: int) -> pd.Series:
    weights = np.arange(1, length + 1)
    def _wma_apply(arr):
        if len(arr) < length:
            return np.nan
        return np.dot(arr, weights) / weights.sum()
    return series.rolling(length).apply(_wma_apply, raw=True)


def compute_hm_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["RSI9"] = rsi9(df["Close"])
    df["Speed"] = df["RSI9"].ewm(span=3, adjust=False).mean()
    df["Strength"] = wma(df["RSI9"], 21)
    return df


def detect_hm_signal(df: pd.DataFrame) -> dict:
    if df.empty or len(df) < 25:
        return {"signal": "WATCH", "reason": "Insufficient data", "priority": "LOW"}
    last = df.iloc[-1]
    prev = df.iloc[-2]
    rsi9_v, speed, strength = last["RSI9"], last["Speed"], last["Strength"]
    pr, ps, pst = prev["RSI9"], prev["Speed"], prev["Strength"]
    if pd.isna(rsi9_v) or pd.isna(speed) or pd.isna(strength):
        return {"signal": "WATCH", "reason": "NaN indicators", "priority": "LOW"}
    strength_below_both = strength < speed and strength < rsi9_v
    strength_above_both = strength > speed and strength > rsi9_v
    prev_below = pst < ps and pst < pr
    prev_above = pst > ps and pst > pr
    if strength_below_both and not prev_below:
        return {"signal": "BUY", "reason": "HM BUY: Strength crossed below Speed+RSI9", "priority": "HIGH"}
    if strength_above_both and not prev_above:
        return {"signal": "SELL", "reason": "HM SELL: Strength crossed above Speed+RSI9", "priority": "HIGH"}
    if strength_below_both:
        return {"signal": "HOLD", "reason": "HM HOLD: Strength still below Speed+RSI9 (bullish)", "priority": "MEDIUM"}
    if strength_above_both:
        return {"signal": "SELL", "reason": "HM SELL: Strength above Speed+RSI9 (bearish)", "priority": "MEDIUM"}
    return {"signal": "WATCH", "reason": "HM WATCH: Mixed — between Speed and RSI9", "priority": "LOW"}
