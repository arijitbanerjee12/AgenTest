from __future__ import annotations

import yfinance as yf
import pandas as pd


GRANULARITY_MAP = {
    "daily": "1d", "weekly": "1wk", "monthly": "1mo",
    "hourly": "1h", "minute": "1m", "15m": "15m", "5m": "5m",
}


def _flatten_multiindex(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.capitalize() for c in df.columns]
    return df


def fetch_data(symbol: str, interval: str = "1d", period: str = "6mo") -> pd.DataFrame:
    interval = GRANULARITY_MAP.get(interval, interval)
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return pd.DataFrame()
    df = _flatten_multiindex(df)
    df.index = pd.to_datetime(df.index)
    return df


def fetch_multiple(symbols: list[str], interval: str = "1d", period: str = "6mo") -> dict[str, pd.DataFrame]:
    return {sym: fetch_data(sym, interval, period) for sym in symbols}


def load_symbols_from_csv(path: str) -> list[str]:
    df = pd.read_csv(path, comment="#")
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
