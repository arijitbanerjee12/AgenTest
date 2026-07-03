"""Standalone BTST check — HM + HA + Crossover, prints + Slack. No DB/excel."""
import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

BTST_WEBHOOK = os.getenv("SLACK_BTST_WEBHOOK", "")
VIX_THRESHOLD = 25

BTST_SYMBOLS = [
    {"name": "BAJAJFINSV","symbol": "BAJAJFINSV.NS","sector": "Financial Services"},
    {"name": "BEL",      "symbol": "BEL.NS",       "sector": "Defense & Aerospace"},
    {"name": "KOTAKBANK","symbol": "KOTAKBANK.NS",  "sector": "Banking"},
    {"name": "COALINDIA","symbol": "COALINDIA.NS",  "sector": "Mining (PSU)"},
    {"name": "M&M",      "symbol": "M&M.NS",        "sector": "Automotive"},
    {"name": "DMART",    "symbol": "DMART.NS",      "sector": "Retail"},
    {"name": "DRREDDY",  "symbol": "DRREDDY.NS",    "sector": "Pharma"},
    {"name": "JSWSTEEL", "symbol": "JSWSTEEL.NS",   "sector": "Steel"},
    {"name": "BHARTIARTL","symbol": "BHARTIARTL.NS","sector": "Telecom"},
    {"name": "HDFCLIFE", "symbol": "HDFCLIFE.NS",   "sector": "Insurance"},
    {"name": "SBIN",     "symbol": "SBIN.NS",       "sector": "Banking (PSU)"},
    {"name": "BAJAJ-AUTO","symbol": "BAJAJ-AUTO.NS","sector": "Automotive"},
    {"name": "NTPC",     "symbol": "NTPC.NS",       "sector": "Power"},
    {"name": "ICICIBANK","symbol": "ICICIBANK.NS",  "sector": "Banking"},
]

HM_SYMBOLS = [
    {"name": "DMART",      "symbol": "DMART.NS",      "sector": "Retail"},
    {"name": "BHARTIARTL", "symbol": "BHARTIARTL.NS",  "sector": "Telecom"},
    {"name": "ICICIBANK",  "symbol": "ICICIBANK.NS",   "sector": "Banking"},
    {"name": "INFY",       "symbol": "INFY.NS",        "sector": "IT"},
    {"name": "BAJAJ-AUTO", "symbol": "BAJAJ-AUTO.NS",  "sector": "Automotive"},
    {"name": "MARUTI",     "symbol": "MARUTI.NS",      "sector": "Automotive"},
    {"name": "HCLTECH",    "symbol": "HCLTECH.NS",     "sector": "IT"},
    {"name": "BAJFINANCE", "symbol": "BAJFINANCE.NS",  "sector": "NBFC"},
    {"name": "WIPRO",      "symbol": "WIPRO.NS",       "sector": "IT"},
    {"name": "M&M",        "symbol": "M&M.NS",         "sector": "Automotive"},
]

# ── Helpers ──


def fetch_data(symbol, interval="1h", period="3mo"):
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.capitalize() for c in df.columns]
    return df


def fetch_vix(period="1mo"):
    try:
        vix = yf.download("^INDIAVIX", period=period, progress=False, auto_adjust=True)
        if vix.empty:
            return None
        if isinstance(vix.columns, pd.MultiIndex):
            vix.columns = [c[0] for c in vix.columns]
        return float(vix["Close"].iloc[-1])
    except Exception:
        return None


def compute_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def compute_heikin_ashi(df):
    ha = df.copy()
    ha["HA_Close"] = (ha["Open"] + ha["High"] + ha["Low"] + ha["Close"]) / 4
    ha_open = [ha["Open"].iloc[0]]
    for i in range(1, len(ha)):
        ha_open.append((ha_open[-1] + ha["HA_Close"].iloc[i - 1]) / 2)
    ha["HA_Open"] = ha_open
    ha["HA_High"] = ha[["High", "HA_Open", "HA_Close"]].max(axis=1)
    ha["HA_Low"] = ha[["Low", "HA_Open", "HA_Close"]].min(axis=1)
    return ha


def ha_signal(ha, idx=-1):
    if len(ha) < 3 or abs(idx) > len(ha) - 1:
        return {"signal": "unknown", "strength": 0}
    last = ha.iloc[idx]
    prev = ha.iloc[idx - 1]
    prev2 = ha.iloc[idx - 2]
    is_green = last["HA_Close"] > last["HA_Open"]
    is_red = last["HA_Close"] < last["HA_Open"]
    hi, lo = last["HA_High"], last["HA_Low"]
    denom = hi - lo + 1e-9
    no_upper = abs(hi - max(last["HA_Open"], last["HA_Close"])) < 0.01 * denom
    no_lower = abs(min(last["HA_Open"], last["HA_Close"]) - lo) < 0.01 * denom
    pg = prev["HA_Close"] > prev["HA_Open"]
    p2g = prev2["HA_Close"] > prev2["HA_Open"]
    if is_green and no_upper and is_green and pg and p2g:
        return {"signal": "strong_buy", "strength": 3}
    if is_green and pg:
        return {"signal": "buy", "strength": 2}
    if is_green:
        return {"signal": "weak_buy", "strength": 1}
    if is_red and no_lower and not pg and not p2g:
        return {"signal": "strong_sell", "strength": -3}
    if is_red and not pg:
        return {"signal": "sell", "strength": -2}
    if is_red:
        return {"signal": "weak_sell", "strength": -1}
    return {"signal": "neutral", "strength": 0}


def scan_signal(ema_short, ema_long, ha_sig):
    if len(ema_short) < 2:
        return {"action": "SKIP", "reason": "Insufficient data"}
    cs, cl = ema_short.iloc[-1], ema_long.iloc[-1]
    ps, pl = ema_short.iloc[-2], ema_long.iloc[-2]
    ha_st = ha_sig.get("strength", 0)

    crossed_up = ps <= pl and cs > cl
    is_above = cs > cl
    near_cross_up = not is_above and (cl - cs) / (cl + 1e-9) < 0.02
    crossed_down = ps >= pl and cs < cl
    is_below = cs < cl
    near_cross_down = is_below and (cl - cs) / (cl + 1e-9) < 0.02

    if crossed_up and ha_st >= 2:
        return {"action": "BUY", "reason": "Crossed + HA strong buy", "priority": "HIGH"}
    if crossed_up:
        return {"action": "WATCH", "reason": "Crossed but HA weak", "priority": "MEDIUM"}
    if near_cross_up and ha_st >= 2:
        return {"action": "BUY", "reason": "Near cross + HA strong buy", "priority": "HIGH"}
    if ha_st >= 2 and is_above:
        return {"action": "HOLD", "reason": "Above EMA + HA bullish", "priority": "MEDIUM"}
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
    if ha_st >= 2:
        return {"action": "BUY", "reason": "HA strong buy", "priority": "HIGH"}
    return {"action": "SKIP", "reason": "No signal", "priority": "LOW"}


def last_candle_signal(df, ha, iloc_pos):
    if iloc_pos < 2:
        return None
    ema10 = df["EMA_10"]
    ema20 = df["EMA_20"]
    if pd.isna(ema10.iloc[iloc_pos]) or pd.isna(ema20.iloc[iloc_pos]):
        return None
    hasig = ha_signal(ha, iloc_pos)
    return scan_signal(ema10.iloc[:iloc_pos + 1], ema20.iloc[:iloc_pos + 1], hasig)


# ── HM helpers ──


def _rsi9(series):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_g = gain.rolling(9).mean()
    avg_l = loss.rolling(9).mean().replace(0, np.nan)
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))


def _wma(series, length):
    weights = np.arange(1, length + 1)
    def _apply(arr):
        if len(arr) < length:
            return np.nan
        return np.dot(arr, weights) / weights.sum()
    return series.rolling(length).apply(_apply, raw=True)


# ── EMA+HA signal ──


def get_ema_ha_signal(symbol, name, sector):
    df = fetch_data(symbol, "15m", "5d")
    if df.empty or len(df) < 25:
        return None
    df["EMA_10"] = compute_ema(df["Close"], 10)
    df["EMA_20"] = compute_ema(df["Close"], 20)
    ha = compute_heikin_ashi(df)
    sig = last_candle_signal(df, ha, len(df) - 1)
    if sig is None:
        return None
    hasig = ha_signal(ha, len(df) - 1)
    vix = fetch_vix()
    return {
        "name": name, "symbol": symbol, "sector": sector,
        "strategy": "EMA+HA",
        "signal": sig["action"], "reason": sig["reason"],
        "close": round(float(df["Close"].iloc[-1]), 2),
        "ha_signal": hasig["signal"], "ha_strength": hasig["strength"],
        "vix": vix, "vix_warning": vix > VIX_THRESHOLD if vix else False,
    }


# ── HM signal ──


def get_hm_signal(symbol, name, sector):
    df = fetch_data(symbol, "15m", "5d")
    if df.empty or len(df) < 25:
        return None
    df["RSI9"] = _rsi9(df["Close"])
    df["Speed"] = df["RSI9"].ewm(span=3, adjust=False).mean()
    df["Strength"] = _wma(df["RSI9"], 21)
    last = df.iloc[-1]
    prev = df.iloc[-2]
    rsi9v, speed, strength = last["RSI9"], last["Speed"], last["Strength"]
    pr, ps, pst = prev["RSI9"], prev["Speed"], prev["Strength"]
    if pd.isna(rsi9v) or pd.isna(speed) or pd.isna(strength):
        return None

    below = strength < speed and strength < rsi9v
    above = strength > speed and strength > rsi9v
    p_below = pst < ps and pst < pr
    p_above = pst > ps and pst > pr

    if below and not p_below:
        action, reason, prio = "BUY", "Crossed below Speed+RSI9", "HIGH"
    elif above and not p_above:
        action, reason, prio = "SELL", "Crossed above Speed+RSI9", "HIGH"
    elif below:
        action, reason, prio = "HOLD", "Bullish below Speed+RSI9", "MEDIUM"
    elif above:
        action, reason, prio = "SELL", "Bearish above Speed+RSI9", "MEDIUM"
    else:
        action, reason, prio = "WATCH", "Mixed between Speed and RSI9", "LOW"

    vix = fetch_vix()
    return {
        "name": name, "symbol": symbol, "sector": sector,
        "strategy": "HM",
        "signal": action, "reason": reason, "priority": prio,
        "close": round(float(last["Close"]), 2),
        "rsi9": round(float(rsi9v), 2), "speed": round(float(speed), 2),
        "strength_raw": round(float(strength), 2),
        "vix": vix, "vix_warning": vix > VIX_THRESHOLD if vix else False,
    }


# ── Slack ──


def send_slack(msg):
    try:
        import urllib.request
        data = f'{{"text": "{msg}"}}'.encode()
        req = urllib.request.Request(BTST_WEBHOOK, data, {"Content-Type": "application/json"})
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"  [Slack error] {e}")


# ── Main ──


def main():
    print("=" * 70)
    print(f"  BTST SIGNALS — {datetime.now():%Y-%m-%d %H:%M}")
    print("=" * 70)

    results = []
    for s in BTST_SYMBOLS:
        sig = get_ema_ha_signal(s["symbol"], s["name"], s["sector"])
        results.append(sig or {"name": s["name"], "signal": "NO DATA", "strategy": "EMA+HA"})

    hm_results = []
    for s in HM_SYMBOLS:
        sig = get_hm_signal(s["symbol"], s["name"], s["sector"])
        hm_results.append(sig or {"name": s["name"], "signal": "NO DATA", "strategy": "HM"})

    # ── Print ──
    print("\n  EMA+HA CROSSOVER SIGNALS")
    print(f"  {'Name':<14} {'Sig':<8} {'Close':<10} {'HA':<12} {'VIX':<6} Reason")
    print(f"  {'-'*75}")
    for r in results:
        if r.get("signal") == "NO DATA":
            print(f"  {r['name']:<14} NO DATA")
        else:
            v = f"{r['vix']}" + ("!" if r.get("vix_warning") else "")
            print(f"  {r['name']:<14} {r['signal']:<8} {r['close']:<10} {r.get('ha_signal',''):<12} {v:<6} {r['reason']}")

    print("\n  HILEGA MILEGA STANDALONE")
    print(f"  {'Name':<14} {'Sig':<8} {'RSI9':<8} {'Speed':<8} {'Str':<8} {'Close':<10} Reason")
    print(f"  {'-'*75}")
    for r in hm_results:
        if r.get("signal") == "NO DATA":
            print(f"  {r['name']:<14} NO DATA")
        else:
            print(f"  {r['name']:<14} {r['signal']:<8} {r.get('rsi9',''):<8} {r.get('speed',''):<8} {r.get('strength_raw',''):<8} {r.get('close',''):<10} {r['reason']}")

    # Summary
    counts_ha = {}
    for r in results:
        s = r.get("signal", "NO DATA")
        counts_ha[s] = counts_ha.get(s, 0) + 1
    counts_hm = {}
    for r in hm_results:
        s = r.get("signal", "NO DATA")
        counts_hm[s] = counts_hm.get(s, 0) + 1

    print(f"\n  Summary: EMA+HA BUY={counts_ha.get('BUY',0)} SELL={counts_ha.get('SELL',0)} HOLD={counts_ha.get('HOLD',0)} WATCH={counts_ha.get('WATCH',0)} SKIP={counts_ha.get('SKIP',0)}")
    print(f"           HM      BUY={counts_hm.get('BUY',0)} SELL={counts_hm.get('SELL',0)} HOLD={counts_hm.get('HOLD',0)} WATCH={counts_hm.get('WATCH',0)} SKIP={counts_hm.get('SKIP',0)}")

    # Build Slack msg
    slack_lines = [f"*BTST Signals — {datetime.now():%Y-%m-%d %H:%M}*"]
    slack_lines.append("")
    slack_lines.append("*EMA+HA Crossover*")
    for r in results:
        if r.get("signal") == "NO DATA":
            slack_lines.append(f"  {r['name']} — NO DATA")
        else:
            icon = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "WATCH": "🔵", "SKIP": "⚪"}
            slack_lines.append(f"  {icon.get(r['signal'], '⚪')} {r['name']}: *{r['signal']}* — {r['reason']} ({r.get('ha_signal','')})")
    slack_lines.append("")
    slack_lines.append("*Hilega Milega*")
    for r in hm_results:
        if r.get("signal") == "NO DATA":
            slack_lines.append(f"  {r['name']} — NO DATA")
        else:
            icon = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "WATCH": "🔵", "SKIP": "⚪"}
            slack_lines.append(f"  {icon.get(r['signal'], '⚪')} {r['name']}: *{r['signal']}* — RSI9={r.get('rsi9','')} S={r.get('speed','')} W={r.get('strength_raw','')}")

    vix_now = fetch_vix()
    if vix_now:
        slack_lines.append(f"\nVIX: {vix_now:.1f}" + (" ⚠ HIGH" if vix_now > VIX_THRESHOLD else ""))

    send_slack("\n".join(slack_lines))
    print(f"\n  [Slack] Sent to BTST channel.")
    print("=" * 70)


if __name__ == "__main__":
    main()
