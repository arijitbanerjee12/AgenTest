import pandas as pd


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def detect_crossover(short_ema: pd.Series, long_ema: pd.Series) -> list[dict]:
    if len(short_ema) < 2 or len(long_ema) < 2:
        return []
    signals = []
    prev_short = short_ema.iloc[-2]
    prev_long = long_ema.iloc[-2]
    curr_short = short_ema.iloc[-1]
    curr_long = long_ema.iloc[-1]

    if prev_short <= prev_long and curr_short > curr_long:
        signals.append({"type": "bullish", "date": short_ema.index[-1]})
    elif prev_short >= prev_long and curr_short < curr_long:
        signals.append({"type": "bearish", "date": short_ema.index[-1]})
    else:
        direction = "above" if curr_short > curr_long else "below"
        signals.append({"type": "no_crossover", "short_above": curr_short > curr_long, "direction": direction, "date": short_ema.index[-1]})

    return signals


def compute_crossovers(df: pd.DataFrame, ema_config: list[dict]) -> list[dict]:
    result = []
    for cfg in ema_config:
        period = cfg["period"]
        field = cfg.get("field", "Close")
        col_name = f"EMA_{period}"
        if field not in df.columns:
            continue
        df[col_name] = compute_ema(df[field], period)
        result.append({"period": period, "field": field, "col": col_name})
    return result
