from __future__ import annotations
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np


def _plot_symbol(symbol: str, df: pd.DataFrame, ema_cols: list[str], signals: list[dict], output_dir: Path) -> Path | None:
    if df is None or df.empty or "Close" not in df.columns:
        return None
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(df.index, df["Close"], label="Close", color="blue", linewidth=1.5, alpha=0.8)

    colors = ["orange", "green", "red", "purple", "brown"]
    for i, col in enumerate(ema_cols):
        if col in df.columns:
            ax.plot(df.index, df[col], label=col, color=colors[i % len(colors)], linewidth=1, linestyle="--")

    for sig in signals:
        sig_type = sig.get("type", "")
        date = sig.get("date")
        if date and date in df.index:
            price = df.loc[date, "Close"] if date in df.index else None
            if price is not None:
                marker = "^" if sig_type == "bullish" else "v" if sig_type == "bearish" else "o"
                color = "green" if sig_type == "bullish" else "red" if sig_type == "bearish" else "gray"
                ax.scatter(date, price, marker=marker, s=200, color=color, zorder=5, label=f"{sig_type} @ {date.strftime('%Y-%m-%d')}" if sig_type != "no_crossover" else "")

    ax.set_title(f"{symbol} - EMA Crossover Analysis", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    out = output_dir / f"{symbol}_ema_crossover.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return out


def generate_report(results: dict, ema_config: list[dict], output_dir: str | Path = "tests/temp/indicator_reports") -> dict[str, Any]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ema_cols = [f"EMA_{cfg['period']}" for cfg in ema_config]

    summary = {
        "total": len(results),
        "bullish": [],
        "bearish": [],
        "no_crossover": [],
        "charts": {},
        "errors": [],
    }

    for symbol, info in results.items():
        df = info.get("data")
        signals = info.get("signals", [])
        chart_path = _plot_symbol(symbol, df, ema_cols, signals, out_dir)
        if chart_path:
            summary["charts"][symbol] = str(chart_path)

        latest = signals[-1] if signals else {}
        sig_type = latest.get("type", "unknown")
        if sig_type == "bullish":
            summary["bullish"].append(symbol)
        elif sig_type == "bearish":
            summary["bearish"].append(symbol)
        else:
            summary["no_crossover"].append(symbol)

    return summary


def generate_summary_table(summary: dict, output_dir: str | Path) -> Path:
    out_dir = Path(output_dir)
    rows = []
    for group_name in ["bullish", "bearish", "no_crossover"]:
        for sym in summary.get(group_name, []):
            rows.append({"symbol": sym, "signal": group_name.replace("_", " ").title()})
    if not rows:
        return None
    df = pd.DataFrame(rows)
    path = out_dir / "crossover_summary.csv"
    df.to_csv(path, index=False)
    return path
