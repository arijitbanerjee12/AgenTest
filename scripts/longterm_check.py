"""Standalone long-term scan — EMA 10/20 + HA, prints + Slack. No DB/excel."""
import os
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

LONG_TERM_WEBHOOK = os.getenv("SLACK_LONG_TERM_WEBHOOK", "")

ETFS = [
    "NIFTYBEES.NS","BANKBEES.NS","GOLDBEES.NS","MOM100.NS","LIQUIDBEES.NS","NETF.NS",
    "JUNIORBEES.NS","SETFNIF50.NS","AXISNIFTY.NS","MIDCAP.NS","SMALLCAP.NS","PSUBNKBEES.NS",
    "SBIETFIT.NS","ITBEES.NS","HEALTHY.NS","FMCGIETF.NS","CONSUMBEES.NS","AUTOBEES.NS",
    "CPSEETF.NS","GROWWEV.NS","GOLDETF.NS","MON100.NS","MAFANG.NS","GROWWDEFNC.NS","NIFTY1.NS",
    "NIFTYIETF.NS","NIFTYETF.NS","NIFTYBETA.NS","IDFNIFTYET.NS","QNIFTY.NS","SILVERBEES.NS",
    "SETFGOLD.NS","HDFCGOLD.NS","PHARMABEES.NS","MID150BEES.NS","MOSMALL250.NS","EDELWEISS.NS",
    "ALPHAETF.NS","FINIETF.NS","MAHKTECH.NS","MASPTOP50.NS","MONQ50.NS","HNGSNGBEES.NS",
    "GROWWMOM50.NS","MOCAPITAL.NS","NEXT50IETF.NS","TOP100CASE.NS","INFRAIETF.NS","MOM30IETF.NS",
    "MONIFTY500.NS","GROWWRLTY.NS","MOMENTUM50.NS","AUTOIETF.NS","MNC.NS","AONETMMQ50.NS",
    "EVINDIA.NS","HEALTHCARE.NS","NV20IETF.NS","PVTBANIETF.NS","MOREALTY.NS","HDFCMOMENT.NS",
    "SMALL250.NS","EVIETF.NS","MIDSMALL.NS","FLEXIADD.NS","ESENSEX.NS","CONS.NS","MOHEALTH.NS",
    "AONETOTAL.NS","ALPL30IETF.NS","GROWWCHEM.NS","LIQUIDCASE.NS","GROWWMETAL.NS","LTGILTBEES.NS",
    "ICICIB22.NS","HEALTHIETF.NS","HDFCSML250.NS","ABSLBANETF.NS","BIRET.NS",
]

LARGE_CAPS = [
    "ADANIENT.NS","ADANIPORTS.NS","APOLLOHOSP.NS","ASIANPAINT.NS","AXISBANK.NS",
    "BAJAJ-AUTO.NS","BAJFINANCE.NS","BAJAJFINSV.NS","BEL.NS","BHARTIARTL.NS",
    "CIPLA.NS","COALINDIA.NS","DRREDDY.NS","EICHERMOT.NS","GRASIM.NS","HCLTECH.NS",
    "HDFCBANK.NS","HDFCLIFE.NS","HINDALCO.NS","HINDUNILVR.NS","ICICIBANK.NS","ITC.NS",
    "INFY.NS","JSWSTEEL.NS","KOTAKBANK.NS","LT.NS","M&M.NS","MARUTI.NS","NTPC.NS",
    "ONGC.NS","LICI.NS","DMART.NS","POWERGRID.NS",
]

# ── Helpers ──


def fetch_data(symbol, interval="1d", period="1y"):
    df = yf.download(symbol, interval=interval, period=period, progress=False, auto_adjust=True)
    if df is None or df.empty:
        return pd.DataFrame()
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.columns = [c.capitalize() for c in df.columns]
    return df


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
    if is_green and no_upper and pg and p2g:
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


def analyze_stock(symbol, category):
    df = fetch_data(symbol, "1d", "1y")
    if df.empty or len(df) < 30:
        return None
    df["EMA_10"] = compute_ema(df["Close"], 10)
    df["EMA_20"] = compute_ema(df["Close"], 20)
    ha = compute_heikin_ashi(df)
    idx = len(df) - 1
    ema10 = df["EMA_10"]
    ema20 = df["EMA_20"]
    if pd.isna(ema10.iloc[idx]) or pd.isna(ema20.iloc[idx]):
        return None
    hasig = ha_signal(ha, idx)
    sig = scan_signal(ema10.iloc[:idx + 1], ema20.iloc[:idx + 1], hasig)
    return {
        "symbol": symbol.replace(".NS", ""),
        "category": category,
        "action": sig["action"],
        "reason": sig["reason"],
        "close": round(float(df["Close"].iloc[-1]), 2),
        "ha_signal": hasig["signal"],
    }


# ── Slack ──


def send_slack(msg):
    try:
        import urllib.request
        data = f'{{"text": "{msg}"}}'.encode()
        req = urllib.request.Request(LONG_TERM_WEBHOOK, data, {"Content-Type": "application/json"})
        urllib.request.urlopen(req)
    except Exception as e:
        print(f"  [Slack error] {e}")


# ── Main ──


def main():
    print("=" * 70)
    print(f"  LONG-TERM SCAN — {datetime.now():%Y-%m-%d %H:%M}")
    print(f"  {len(ETFS)} ETFs + {len(LARGE_CAPS)} Large Caps = {len(ETFS) + len(LARGE_CAPS)} stocks")
    print("=" * 70)

    all_signals = []
    for sym in ETFS:
        sig = analyze_stock(sym, "etf")
        all_signals.append(sig or {"symbol": sym.replace(".NS",""), "category": "etf", "action": "NO DATA"})
    for sym in LARGE_CAPS:
        sig = analyze_stock(sym, "large_cap")
        all_signals.append(sig or {"symbol": sym.replace(".NS",""), "category": "large_cap", "action": "NO DATA"})

    # Print table
    busy = [s for s in all_signals if s.get("action") in ("BUY", "SELL", "HOLD")]
    print(f"\n  SIGNALS ({len(busy)} actionable / {len(all_signals)} scanned)\n")
    print(f"  {'Symbol':<16} {'Type':<12} {'Signal':<8} {'HA':<14} {'Close':<10} Reason")
    print(f"  {'-'*80}")
    for s in all_signals:
        if s.get("action") in ("BUY", "SELL", "HOLD"):
            print(f"  {s['symbol']:<16} {s['category']:<12} {s['action']:<8} {s.get('ha_signal',''):<14} {s.get('close',''):<10} {s['reason']}")

    # Summary counts
    from collections import Counter
    counts = Counter(s.get("action", "SKIP") for s in all_signals)
    print(f"\n  SUMMARY: BUY={counts['BUY']} SELL={counts['SELL']} HOLD={counts['HOLD']} WATCH={counts['WATCH']} SKIP={counts['SKIP']} NO DATA={counts['NO DATA']}")

    buys = [s for s in all_signals if s.get("action") == "BUY"]
    sells = [s for s in all_signals if s.get("action") == "SELL"]
    holds = [s for s in all_signals if s.get("action") == "HOLD"]

    # Slack
    slack_lines = [f"*Long-Term Scan — {datetime.now():%Y-%m-%d %H:%M}*"]
    slack_lines.append(f"*{counts['BUY']} BUY / {counts['SELL']} SELL / {counts['HOLD']} HOLD* ({len(busy)} action / {len(all_signals)} scanned)")
    slack_lines.append("")
    if buys:
        slack_lines.append("*BUY Signals*")
        for s in buys:
            slack_lines.append(f"  🟢 {s['symbol']} ({s['category']}) — {s['reason']}")
    if sells:
        slack_lines.append("\n*SELL Signals*")
        for s in sells:
            slack_lines.append(f"  🔴 {s['symbol']} ({s['category']}) — {s['reason']}")
    if holds:
        slack_lines.append("\n*HOLD Signals*")
        for s in holds:
            slack_lines.append(f"  🟡 {s['symbol']} ({s['category']}) — {s['reason']}")
    if counts['WATCH'] > 0:
        slack_lines.append(f"\nWATCH: {counts['WATCH']} | SKIP: {counts['SKIP']}")

    send_slack("\n".join(slack_lines))
    print(f"  [Slack] Sent to long-term channel.")
    print("=" * 70)


if __name__ == "__main__":
    main()
