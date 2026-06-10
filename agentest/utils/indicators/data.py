from __future__ import annotations
from typing import Any
import yfinance as yf
import pandas as pd


GRANULARITY_MAP = {
    "daily": "1d",
    "weekly": "1wk",
    "monthly": "1mo",
    "hourly": "1h",
    "minute": "1m",
}


def fetch_data(symbol: str, granularity: str, period: str = "6mo") -> pd.DataFrame | None:
    interval = GRANULARITY_MAP.get(granularity, "1d")
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return None
        return df
    except Exception:
        return None


def fetch_multiple(symbols: list[str], granularity: str, period: str = "6mo") -> dict[str, pd.DataFrame]:
    results: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = fetch_data(sym, granularity, period)
        if df is not None and not df.empty:
            results[sym] = df
    return results


def load_symbols_from_csv(path: str) -> list[str]:
    df = pd.read_csv(path)
    col = None
    for candidate in ["symbol", "Symbol", "SYMBOL", "ticker", "Ticker", "name", "Name"]:
        if candidate in df.columns:
            col = candidate
            break
    if col is None:
        col = df.columns[0]
    return df[col].dropna().str.strip().str.upper().tolist()


def load_symbols_from_excel(path: str) -> list[str]:
    df = pd.read_excel(path, engine="openpyxl")
    col = None
    for candidate in ["symbol", "Symbol", "SYMBOL", "ticker", "Ticker", "name", "Name"]:
        if candidate in df.columns:
            col = candidate
            break
    if col is None:
        col = df.columns[0]
    return df[col].dropna().str.strip().str.upper().tolist()
