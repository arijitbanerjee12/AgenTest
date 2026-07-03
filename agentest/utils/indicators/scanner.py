from __future__ import annotations
from pathlib import Path
from typing import Any
import pandas as pd
from agentest.utils.indicators.ema import compute_ema, detect_crossover
from agentest.utils.indicators.heikin_ashi import compute_heikin_ashi, detect_ha_signal, scan_combined


def run_daily_scan(data: dict[str, pd.DataFrame], ema_config: list[dict]) -> dict[str, dict]:
    if len(ema_config) < 2:
        short_col = f"EMA_{ema_config[0]['period']}"
        long_col = f"EMA_{ema_config[1]['period']}" if len(ema_config) > 1 else short_col
    else:
        short_col = f"EMA_{ema_config[0]['period']}"
        long_col = f"EMA_{ema_config[1]['period']}"

    results: dict[str, dict] = {}
    for sym, df in data.items():
        if df.empty or "Close" not in df.columns:
            continue
        for cfg in ema_config:
            col = f"EMA_{cfg['period']}"
            df[col] = compute_ema(df[cfg.get('field', 'Close')], cfg['period'])

        cross_signals = detect_crossover(df[short_col], df[long_col])

        ha = compute_heikin_ashi(df)
        ha_signal = detect_ha_signal(ha)

        volume = df["Volume"] if "Volume" in df.columns else None
        scan = scan_combined(df[short_col], df[long_col], ha_signal, volume, ha)

        results[sym] = {
            "data": df,
            "heikin_ashi": ha,
            "ha_signal": ha_signal,
            "crossover": cross_signals[-1] if cross_signals else {},
            "scan": scan,
            "ema_short": df[short_col].iloc[-1] if short_col in df.columns else None,
            "ema_long": df[long_col].iloc[-1] if long_col in df.columns else None,
            "close": df["Close"].iloc[-1],
        }
    return results


def generate_daily_report(
    results: dict[str, dict],
    category: str,
    output_dir: str | Path = "tests/temp/daily_scans",
) -> dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    category_dir = out_dir / category
    category_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for sym, info in results.items():
        scan = info.get("scan", {})
        ha = info.get("ha_signal", {})
        cross = info.get("crossover", {})
        rows.append({
            "symbol": sym,
            "category": category,
            "close": round(info.get("close", 0), 2),
            "ema_short": round(info.get("ema_short", 0), 2) if info.get("ema_short") else None,
            "ema_long": round(info.get("ema_long", 0), 2) if info.get("ema_long") else None,
            "crossover": cross.get("type", "none"),
            "ha_signal": ha.get("signal", "unknown"),
            "ha_strength": ha.get("strength", 0),
            "action": scan.get("action", "SKIP"),
            "status": scan.get("status", "no_action"),
            "reason": scan.get("reason", ""),
            "priority": scan.get("priority", "LOW"),
            "volume_confirmed": scan.get("volume_confirmed", False),
            "volume_ratio": scan.get("volume_ratio", 0.0),
            "vpa_signal": scan.get("vpa_signal", "none"),
        })

    df = pd.DataFrame(rows)

    # Priority order for CSV
    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    df["_sort"] = df["priority"].map(priority_order)
    df = df.sort_values("_sort").drop(columns=["_sort"])

    # Full report
    full_path = category_dir / f"{category}_daily_scan.csv"
    df.to_csv(full_path, index=False)

    # Actionable only (BUY + SELL + WATCH)
    actionable = df[df["action"].isin(["BUY", "SELL", "WATCH"])]
    action_path = category_dir / f"{category}_actionable.csv"
    actionable.to_csv(action_path, index=False)

    # Summary
    summary = {
        "category": category,
        "total": len(df),
        "buy_signals": int((df["action"] == "BUY").sum()),
        "sell_signals": int((df["action"] == "SELL").sum()),
        "watch_signals": int((df["action"] == "WATCH").sum()),
        "skip": int((df["action"] == "SKIP").sum()),
        "high_priority": int((df["priority"] == "HIGH").sum()),
        "files": {
            "full": str(full_path),
            "actionable": str(action_path),
        },
    }
    return summary
