from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import allure
import pandas as pd
import pytest
from pytest_bdd import given, when, then, parsers
from agentest.utils.indicators.ema import compute_crossovers, detect_crossover, compute_ema
from agentest.utils.indicators.data import fetch_data, fetch_multiple, load_symbols_from_csv, load_symbols_from_excel
from agentest.utils.indicators.chart import generate_report, generate_summary_table
from agentest.utils.indicators.heikin_ashi import compute_heikin_ashi, detect_ha_signal, scan_combined
from agentest.utils.indicators.scanner import run_daily_scan, generate_daily_report
from agentest.core.context import Context

SCAN_COUNTS = ["BUY", "SELL", "HOLD", "WATCH", "SKIP"]
_SCAN_RESULTS_DIR = Path("tests/temp/scan_results")

COMMODITY_NAMES = {
    "GC=F": "Gold Futures (COMEX)",
    "SI=F": "Silver Futures (COMEX)",
    "CL=F": "Crude Oil WTI Futures (NYMEX)",
    "NG=F": "Natural Gas Futures (NYMEX)",
    "HG=F": "Copper Futures (COMEX)",
    "PL=F": "Platinum Futures (NYMEX)",
    "PA=F": "Palladium Futures (NYMEX)",
    "ZW=F": "Wheat Futures (CBOT)",
    "ZC=F": "Corn Futures (CBOT)",
    "ZS=F": "Soybean Futures (CBOT)",
    "KC=F": "Coffee 'C' Futures (ICE)",
    "CC=F": "Cocoa Futures (ICE)",
    "SB=F": "Sugar No.11 Futures (ICE)",
    "CT=F": "Cotton No.2 Futures (ICE)",
    "OJ=F": "Orange Juice Futures (ICE)",
}


def _sanitize_filename(s: str) -> str:
    return "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in s)


def _save_stock_result(symbol: str, category: str, action: str, reason: str, priority: str, close: float,
                       ema_10: float, ema_20: float, crossover: str, ha_signal: str, ha_strength: float,
                       volume_confirmed: bool = False, volume_ratio: float = 0.0,
                       vpa_signal: str = "none") -> None:
    _SCAN_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    name = COMMODITY_NAMES.get(symbol, symbol)
    data = {
        "symbol": symbol, "name": name, "category": category, "action": action, "reason": reason,
        "priority": priority, "close": round(close, 2), "ema_10": round(ema_10, 2),
        "ema_20": round(ema_20, 2), "crossover": crossover, "ha_signal": ha_signal,
        "ha_strength": ha_strength, "volume_confirmed": volume_confirmed,
        "volume_ratio": round(volume_ratio, 2), "vpa_signal": vpa_signal,
    }
    safe = _sanitize_filename(symbol)
    (_SCAN_RESULTS_DIR / f"{safe}.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_all_results() -> tuple[list[dict], dict[str, int]]:
    stocks: list[dict] = []
    counts: dict[str, int] = {k: 0 for k in SCAN_COUNTS}
    if not _SCAN_RESULTS_DIR.exists():
        return stocks, counts
    for f in sorted(_SCAN_RESULTS_DIR.iterdir()):
        if f.suffix == ".json":
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                stocks.append(d)
                counts[d.get("action", "SKIP")] += 1
            except Exception:
                pass
    return stocks, counts


def _store(context) -> dict:
    return object.__getattribute__(context, "_store")


def _ensure_indicators(context) -> None:
    store = _store(context)
    store.setdefault("indicators", {})
    store["indicators"].setdefault("ema_config", [])
    store["indicators"].setdefault("granularity", "daily")
    store["indicators"].setdefault("period", "6mo")
    store["indicators"].setdefault("symbols", [])
    store["indicators"].setdefault("data", {})
    store["indicators"].setdefault("results", {})
    store["indicators"].setdefault("summary", {})
    store["indicators"].setdefault("results_dir", "tests/temp/indicator_reports")


# ── Configuration Steps ──────────────────────────────────────────────

@given("I configure EMA indicators")
def configure_ema_table(context, datatable):
    with allure.step("Configure EMA indicators"):
        _ensure_indicators(context)
        store = _store(context)
        configs = []
        for row in datatable:
            if len(row) < 1 or row[0].strip().lower() == "period":
                continue
            period = int(row[0].strip())
            field = row[1].strip() if len(row) >= 2 else "Close"
            configs.append({"period": period, "field": field})
        store["indicators"]["ema_config"] = configs
        allure.attach(json.dumps(configs, indent=2), "EMA Config", allure.attachment_type.JSON)


@given(parsers.parse('I select data granularity "{granularity}"'))
def select_granularity(context, granularity: str):
    with allure.step(f'Select granularity "{granularity}"'):
        _ensure_indicators(context)
        _store(context)["indicators"]["granularity"] = granularity
        allure.attach(granularity, "Granularity", allure.attachment_type.TEXT)


@given("I select data granularity")
def select_granularity_table(context, datatable):
    with allure.step("Select data granularity from table"):
        _ensure_indicators(context)
        store = _store(context)
        levels = []
        for row in datatable:
            if len(row) < 1 or row[0].strip().lower() == "level":
                continue
            level = row[0].strip().lower()
            count = int(row[1].strip()) if len(row) >= 2 else 1
            for _ in range(count):
                levels.append(level)
        store["indicators"]["granularity"] = levels[0] if levels else "daily"
        allure.attach(json.dumps(levels, indent=2), "Granularity Levels", allure.attachment_type.JSON)


@given(parsers.parse('I fetch data for the last "{period}"'))
@when(parsers.parse('I fetch historical data for the last "{period}"'))
def set_fetch_period(context, period: str):
    with allure.step(f'Set fetch period to "{period}"'):
        _ensure_indicators(context)
        store = _store(context)
        store["indicators"]["period"] = period
        symbols = store["indicators"].get("symbols", [])
        granularity = store["indicators"].get("granularity", "daily")
        data: dict[str, Any] = {}
        for sym in symbols:
            df = fetch_data(sym, granularity, period)
            if df is not None and not df.empty:
                data[sym] = df
        store["indicators"]["data"] = data
        allure.attach(
            json.dumps({sym: len(df) for sym, df in data.items()}, indent=2),
            "Fetched Data",
            allure.attachment_type.JSON,
        )


# ── Symbol Loading Steps ─────────────────────────────────────────────

@given(parsers.parse('I load stock symbols from "{path}"'))
def load_symbols_file(context, path: str):
    with allure.step(f'Load stock symbols from "{path}"'):
        _ensure_indicators(context)
        store = _store(context)
        p = Path(path)
        if p.suffix.lower() in (".xls", ".xlsx"):
            symbols = load_symbols_from_excel(str(p))
        else:
            symbols = load_symbols_from_csv(str(p))
        store["indicators"]["symbols"] = symbols
        allure.attach(json.dumps(symbols, indent=2), "Loaded Symbols", allure.attachment_type.JSON)


@given("I set stock symbols")
def set_symbols_table(context, datatable):
    with allure.step("Set stock symbols from table"):
        _ensure_indicators(context)
        store = _store(context)
        symbols = []
        for row in datatable:
            if len(row) < 1 or row[0].strip().lower() == "symbol":
                continue
            symbols.append(row[0].strip().upper())
        store["indicators"]["symbols"] = symbols
        allure.attach(json.dumps(symbols, indent=2), "Stock Symbols", allure.attachment_type.JSON)


# ── Data Fetching Steps ──────────────────────────────────────────────

@when("I fetch historical data")
def fetch_historical_data(context):
    with allure.step("Fetch historical data for all symbols"):
        _ensure_indicators(context)
        store = _store(context)
        cfg = store["indicators"]
        symbols = cfg["symbols"]
        granularity = cfg["granularity"]
        period = cfg.get("period", "6mo")
        data: dict[str, Any] = {}
        errors = []
        for sym in symbols:
            df = fetch_data(sym, granularity, period)
            if df is not None and not df.empty:
                data[sym] = df
            else:
                errors.append(sym)
        cfg["data"] = data
        allure.attach(
            json.dumps({sym: len(df) for sym, df in data.items()}, indent=2),
            "Fetched Data (rows per symbol)",
            allure.attachment_type.JSON,
        )
        if errors:
            allure.attach(json.dumps(errors, indent=2), "Fetch Errors", allure.attachment_type.JSON)


# ── Calculation Steps ────────────────────────────────────────────────

@then("I calculate EMA crossovers")
def calculate_ema_crossovers(context):
    with allure.step("Calculate EMA crossovers"):
        _ensure_indicators(context)
        store = _store(context)
        cfg = store["indicators"]
        ema_config = cfg["ema_config"]
        data = cfg["data"]
        results: dict[str, Any] = {}
        for sym, df in data.items():
            compute_crossovers(df, ema_config)
            cols = [f"EMA_{c['period']}" for c in ema_config]
            if len(cols) >= 2:
                signals = detect_crossover(df[cols[0]], df[cols[1]])
            else:
                signals = []
            results[sym] = {"data": df, "signals": signals}
        cfg["results"] = results
        summary_lines = []
        for sym, info in results.items():
            sig = info["signals"][-1] if info["signals"] else {}
            summary_lines.append(f"{sym}: {sig.get('type', 'unknown')}")
        allure.attach("\n".join(summary_lines), "Crossover Summary", allure.attachment_type.TEXT)


# ── Reporting Steps ──────────────────────────────────────────────────

@then("I generate EMA crossover report with charts")
def generate_crossover_report(context):
    with allure.step("Generate EMA crossover report with charts"):
        _ensure_indicators(context)
        store = _store(context)
        cfg = store["indicators"]
        results = cfg["results"]
        ema_config = cfg["ema_config"]
        output_dir = cfg.get("results_dir", "tests/temp/indicator_reports")

        summary = generate_report(results, ema_config, output_dir)
        cfg["summary"] = summary

        summary_path = generate_summary_table(summary, output_dir)

        allure.attach(
            json.dumps(
                {
                    "total": summary["total"],
                    "bullish": summary["bullish"],
                    "bearish": summary["bearish"],
                    "no_crossover": summary["no_crossover"],
                },
                indent=2,
            ),
            "Report Summary",
            allure.attachment_type.JSON,
        )

        for sym, chart_path in summary.get("charts", {}).items():
            allure.attach.file(chart_path, f"{sym} Chart", allure.attachment_type.PNG)

        if summary_path and summary_path.exists():
            allure.attach.file(str(summary_path), "Crossover Summary CSV", allure.attachment_type.CSV)


# ── Verification Steps ───────────────────────────────────────────────

@then(parsers.parse('the crossover signal for "{symbol}" should be "{expected}"'))
def verify_crossover_signal(context, symbol: str, expected: str):
    with allure.step(f'Verify {symbol} crossover signal is "{expected}"'):
        _ensure_indicators(context)
        store = _store(context)
        results = store["indicators"].get("results", {})
        info = results.get(symbol.upper())
        assert info is not None, f"No data for symbol {symbol}"
        signals = info.get("signals", [])
        assert signals, f"No crossover signals for {symbol}"
        actual = signals[-1].get("type", "unknown")
        assert actual == expected, f"{symbol}: expected {expected}, got {actual}"
        allure.attach(json.dumps({"symbol": symbol, "expected": expected, "actual": actual}, indent=2), "Signal Verification", allure.attachment_type.JSON)


@then("the following symbols should have bullish crossover")
def verify_bullish_crossovers(context, datatable):
    with allure.step("Verify bullish crossover for symbols"):
        _ensure_indicators(context)
        store = _store(context)
        results = store["indicators"].get("results", {})
        failures = []
        for row in datatable:
            if len(row) < 1 or row[0].strip().lower() == "symbol":
                continue
            sym = row[0].strip().upper()
            info = results.get(sym)
            if info is None:
                failures.append(f"{sym}: no data")
                continue
            signals = info.get("signals", [])
            if not signals:
                failures.append(f"{sym}: no signals")
                continue
            actual = signals[-1].get("type", "unknown")
            if actual != "bullish":
                failures.append(f"{sym}: expected bullish, got {actual}")
        assert not failures, "\n".join(failures)
        allure.attach(json.dumps(failures or "All passed", indent=2), "Bullish Verification", allure.attachment_type.JSON)


# ── Heikin-Ashi Steps ────────────────────────────────────────────────

@when("I calculate Heikin-Ashi candles")
def calculate_heikin_ashi(context):
    with allure.step("Calculate Heikin-Ashi candles"):
        _ensure_indicators(context)
        store = _store(context)
        cfg = store["indicators"]
        data = cfg.get("data", {})
        for sym, df in data.items():
            ha = compute_heikin_ashi(df)
            cfg.setdefault("heikin_ashi", {})[sym] = ha
        allure.attach(
            json.dumps({sym: len(ha) for sym, ha in cfg.get("heikin_ashi", {}).items()}, indent=2),
            "Heikin-Ashi Calculation",
            allure.attachment_type.JSON,
        )


@then("I detect Heikin-Ashi signals")
def detect_ha_signals(context):
    with allure.step("Detect Heikin-Ashi signals"):
        _ensure_indicators(context)
        store = _store(context)
        cfg = store["indicators"]
        ha_data = cfg.get("heikin_ashi", {})
        signals = {}
        for sym, ha in ha_data.items():
            sig = detect_ha_signal(ha)
            signals[sym] = sig
        cfg["ha_signals"] = signals
        summary = "\n".join(f"{sym}: {s['signal']} (strength {s['strength']})" for sym, s in signals.items())
        allure.attach(summary, "Heikin-Ashi Signals Summary", allure.attachment_type.TEXT)


# ── Daily Scan Steps ──────────────────────────────────────────────────

@when("I run the daily scan")
def daily_scan(context):
    with allure.step("Run daily scan (EMA + Heikin-Ashi combined)"):
        _ensure_indicators(context)
        store = _store(context)
        cfg = store["indicators"]
        data = cfg.get("data", {})
        ema_config = cfg.get("ema_config", [])
        results = run_daily_scan(data, ema_config)
        cfg["scan_results"] = results
        summary_lines = []
        has_ha = "heikin_ashi" not in cfg
        for sym, info in results.items():
            s = info["scan"]
            ha = info["ha_signal"]
            cross = info["crossover"]
            summary_lines.append(f"{sym}: {s['action']} ({s['reason']}) | HA={ha['signal']} | Cross={cross.get('type','none')}")
        allure.attach("\n".join(summary_lines), "Daily Scan Results", allure.attachment_type.TEXT)


@then(parsers.parse('I generate daily scan report for category "{category}"'))
def generate_daily_scan_report(context, category: str):
    with allure.step(f'Generate daily scan report for "{category}"'):
        _ensure_indicators(context)
        store = _store(context)
        cfg = store["indicators"]
        results = cfg.get("scan_results", {})
        summary = generate_daily_report(results, category)
        cfg.setdefault("daily_reports", {})[category] = summary

        buys = summary.get("buy_signals", 0)
        sells = summary.get("sell_signals", 0)
        watches = summary.get("watch_signals", 0)
        high = summary.get("high_priority", 0)

        # ── Per-stock signal details + charts ──
        signal_stocks = []
        no_signal_stocks = []
        for sym, info in results.items():
            s = info["scan"]
            ha = info["ha_signal"]
            cross = info["crossover"]
            detail = (
                f"{sym}\n"
                f"  Action     : {s['action']}\n"
                f"  Reason     : {s['reason']}\n"
                f"  Priority   : {s['priority']}\n"
                f"  Close      : {info.get('close', 0):.2f}\n"
                f"  EMA(10)    : {info.get('ema_short', 0):.2f}\n"
                f"  EMA(20)    : {info.get('ema_long', 0):.2f}\n"
                f"  Crossover  : {cross.get('type', 'none')}\n"
                f"  Heikin-Ashi: {ha['signal']} (strength {ha['strength']})"
            )
            if s["action"] in ("BUY", "SELL"):
                signal_stocks.append(detail)
                _attach_stock_chart(info, sym)
            else:
                no_signal_stocks.append(detail)

        # ── Attach grouped summaries ──
        if signal_stocks:
            allure.attach(
                "\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n".join(signal_stocks),
                f"{category} — Signals Detected ({len(signal_stocks)})",
                allure.attachment_type.TEXT,
            )
        if no_signal_stocks:
            allure.attach(
                f"Total: {len(no_signal_stocks)} stocks with no BUY/SELL signal",
                f"{category} — No Signal ({len(no_signal_stocks)})",
                allure.attachment_type.TEXT,
            )

        # ── Attach report summary JSON ──
        allure.attach(
            json.dumps({
                "category": category,
                "total": summary["total"],
                "buy_signals": buys,
                "sell_signals": sells,
                "watch_signals": watches,
                "high_priority": high,
                "files": summary["files"],
            }, indent=2),
            f"{category} Report Summary",
            allure.attachment_type.JSON,
        )

        # ── Assert — scenario PASSES only if at least one BUY/SELL signal ──
        if buys + sells == 0:
            pytest.fail(f"{category}: No BUY or SELL signals found (total {summary['total']} stocks)")


# ── Daily Scan Verification Steps ─────────────────────────────────────

# ── Per-Stock BDD Steps ──────────────────────────────────────────────

@when(parsers.parse('I analyze stock for "{period}"'))
def analyze_single_stock(context, symbol, request, period: str):
    _ = request  # keep for compat
    with allure.step(f'Analyze {symbol} ({period})'):
        _ensure_indicators(context)
        store = _store(context)
        cfg = store["indicators"]
        cfg["symbols"] = [symbol]

        df = fetch_data(symbol, "daily", period)
        assert df is not None and not df.empty, f"No data for {symbol}"

        for p in (10, 20):
            df[f"EMA_{p}"] = compute_ema(df["Close"], p)

        cross_signals = detect_crossover(df["EMA_10"], df["EMA_20"])
        ha = compute_heikin_ashi(df)
        ha_signal = detect_ha_signal(ha)
        volume = df["Volume"] if "Volume" in df.columns else None
        scan = scan_combined(df["EMA_10"], df["EMA_20"], ha_signal, volume, ha)

        cfg["single_result"] = {
            "symbol": symbol,
            "close": float(df["Close"].iloc[-1]),
            "ema_10": float(df["EMA_10"].iloc[-1]),
            "ema_20": float(df["EMA_20"].iloc[-1]),
            "crossover": cross_signals[-1] if cross_signals else {"type": "none"},
            "ha_signal": ha_signal,
            "scan": scan,
            "data": df,
        }
        allure.attach(json.dumps({
            "symbol": symbol, "period": period,
            "close": float(df["Close"].iloc[-1]),
            "rows": len(df),
        }, indent=2), f"{symbol} \u2014 Data Fetched", allure.attachment_type.JSON)


@then(parsers.parse('I check signal in category "{category}"'))
def check_single_stock_signal(context, symbol, request, category: str, global_context: Context):
    _ = request  # keep for compat
    with allure.step(f'Check signal for {symbol} ({category})'):
        _ensure_indicators(context)
        store = _store(context)
        info = store["indicators"].get("single_result", {})
        s = info.get("scan", {})
        ha = info.get("ha_signal", {})
        cross = info.get("crossover", {})
        action = s.get("action", "SKIP")
        reason = s.get("reason", "Unknown")
        has_signal = action in ("BUY", "SELL")

        summary = (
            f"{symbol} | 3y | {action}: {reason}\n"
            f"{chr(0x2501)*46}\n"
            f"Category     : {category}\n"
            f"Close        : {info.get('close', 0):.2f}\n"
            f"EMA(10)      : {info.get('ema_10', 0):.2f}\n"
            f"EMA(20)      : {info.get('ema_20', 0):.2f}\n"
            f"{chr(0x2501)*46}\n"
            f"EMA Crossover : {cross.get('type', 'none')}\n"
            f"Heikin-Ashi   : {ha.get('signal', 'unknown')} (strength {ha.get('strength', 0)})\n"
            f"Combined Scan : {action} \u2014 {reason}\n"
            f"Priority      : {s.get('priority', 'LOW')}"
        )
        allure.attach(summary, f"{symbol} \u2014 Signal Summary", allure.attachment_type.TEXT)
        _attach_stock_chart(info, symbol)
        allure.dynamic.title(f"{symbol} | 3y | {action}: {reason}")

        # Persist result to disk (parallel-safe — one file per stock)
        _save_stock_result(
            symbol=symbol, category=category, action=action, reason=reason,
            priority=s.get("priority", "LOW"), close=info.get("close", 0),
            ema_10=info.get("ema_10", 0), ema_20=info.get("ema_20", 0),
            crossover=cross.get("type", "none"),
            ha_signal=ha.get("signal", "unknown"),
            ha_strength=ha.get("strength", 0),
            volume_confirmed=s.get("volume_confirmed", False),
            volume_ratio=s.get("volume_ratio", 0.0),
            vpa_signal=s.get("vpa_signal", "none"),
        )

        if not has_signal:
            pytest.fail(f"{symbol}: No BUY or SELL signal \u2014 {reason}")


# ── Chart Attachment Helper ──────────────────────────────────────────

def _attach_stock_chart(info: dict, symbol: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import FancyBboxPatch
    from io import BytesIO
    import pandas as pd

    df = info.get("data")
    if df is None or "Close" not in df.columns:
        return

    fig, ax = plt.subplots(figsize=(12, 5.5), facecolor="#f8f9fa")
    ax.set_facecolor("#ffffff")

    # ── Price line ──
    ax.plot(df.index, df["Close"], label="Close", color="#2c3e50",
            linewidth=1.2, alpha=0.8, zorder=3)

    # ── EMA lines ──
    colors = {"EMA_10": "#e74c3c", "EMA_20": "#2980b9"}
    for col in ("EMA_10", "EMA_20"):
        if col in df.columns:
            ax.plot(df.index, df[col], label=col.replace("_", " "),
                    color=colors.get(col, "#666"), linestyle="--",
                    linewidth=1.1, alpha=0.7, zorder=4)

    # ── Buy/Sell markers ──
    s = info.get("scan", {})
    action = s.get("action", "")
    last_idx = df.index[-1]
    last_close = df["Close"].iloc[-1]
    if action == "BUY":
        ax.scatter(last_idx, last_close, color="#27ae60", s=180,
                   marker="^", edgecolors="white", linewidth=1.5, zorder=5,
                   label="BUY Signal")
    elif action == "SELL":
        ax.scatter(last_idx, last_close, color="#e74c3c", s=180,
                   marker="v", edgecolors="white", linewidth=1.5, zorder=5,
                   label="SELL Signal")

    # ── Title and labels ──
    title_color = "#27ae60" if action == "BUY" else "#e74c3c" if action == "SELL" else "#7f8c8d"
    ax.set_title(f"{symbol}  |  {action}  |  {s.get('reason', '')}",
                 fontsize=12, fontweight="bold", color=title_color, pad=12)
    ax.set_ylabel("Price (INR)", fontsize=9, color="#555")
    ax.tick_params(axis="both", labelsize=8, colors="#555")

    # ── X-axis date formatting ──
    if len(df) > 60:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    for label in ax.get_xticklabels():
        label.set_ha("center")

    # ── Annotations ──
    close_val = info.get("close", 0)
    ema10 = info.get("ema_10", 0)
    ema20 = info.get("ema_20", 0)
    ha_sig = info.get("ha_signal", {})
    text = (f"Close: {close_val:.2f}  |  EMA(10): {ema10:.2f}  |  "
            f"EMA(20): {ema20:.2f}\n"
            f"HA: {ha_sig.get('signal', '')} (str {ha_sig.get('strength', 0)})  |  "
            f"Cross: {info.get('crossover', {}).get('type', '')}")
    ax.text(0.5, -0.15, text, transform=ax.transAxes, fontsize=8,
            color="#555", ha="center", va="top",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#ecf0f1",
                      edgecolor="#bdc3c7", alpha=0.8))

    ax.legend(fontsize=8, loc="upper left", framealpha=0.9,
              edgecolor="#ccc", fancybox=True)
    ax.grid(alpha=0.25, linestyle=":", color="#bbb")
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    allure.attach(buf.getvalue(), f"{symbol} Chart", allure.attachment_type.PNG)


# ── Standalone Dashboard Generator ─────────────────────────────────────────

def generate_dashboard(stocks: list, counts: dict) -> None:
    """Generate and attach HTML dashboard, charts, and JSON to Allure."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from io import BytesIO
    import json
    from collections import defaultdict

    total = len(stocks)
    if total == 0:
        allure.attach("No results accumulated.", "Dashboard", allure.attachment_type.TEXT)
        return

    cat_counts: dict = defaultdict(lambda: {"BUY": 0, "SELL": 0, "HOLD": 0, "WATCH": 0, "SKIP": 0})
    for s in stocks:
        cat_counts[s["category"]][s["action"]] += 1

    action_order = ("BUY", "SELL", "HOLD", "WATCH", "SKIP")
    action_colors = {"BUY": "#66BB6A", "SELL": "#EF5350", "HOLD": "#FFA726", "WATCH": "#90A4AE", "SKIP": "#CFD8DC"}
    action_labels = {"BUY": "BUY", "SELL": "SELL", "HOLD": "HOLD", "WATCH": "WATCH", "SKIP": "NO SIGNAL"}

    html_parts = [f"""<!DOCTYPE html><html><head><style>
body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; color: #333; }}
h1 {{ font-size: 22px; margin-bottom: 4px; }}
h2 {{ font-size: 16px; margin: 18px 0 8px; padding-bottom: 4px; border-bottom: 2px solid #eee; }}
table {{ border-collapse: collapse; width: 100%; margin-bottom: 12px; font-size: 13px; }}
th, td {{ padding: 6px 10px; text-align: left; border-bottom: 1px solid #dee2e6; }}
th {{ background: #f8f9fa; font-weight: 600; }}
.summary-counts {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0; }}
.count-card {{ padding: 12px 20px; border-radius: 8px; text-align: center; min-width: 80px; font-weight: 600; }}
.count-card .num {{ font-size: 28px; }}
.count-card .lbl {{ font-size: 12px; opacity: 0.85; }}
.stock-row:hover {{ background: #f0f0f0; }}
.cat-table th {{ font-size: 12px; }}
</style></head><body>
<h1>&#128202; Daily Scan Summary Dashboard</h1>
<p style="color:#666;margin-bottom:12px;">Total stocks scanned: <strong>{total}</strong></p>
<div class="summary-counts">"""]

    for label in action_order:
        c = counts.get(label, 0)
        pct = c / total * 100 if total else 0
        bg = action_colors[label]
        html_parts.append(
            f'<div class="count-card" style="background:{bg};color:#fff;">'
            f'<div class="num">{c}</div>'
            f'<div class="lbl">{action_labels[label]} ({pct:.1f}%)</div></div>'
        )

    html_parts.append("""</div>
<h2>&#128202; Signals by Category</h2>
<table class="cat-table"><tr><th>Category</th><th>Total</th>""")
    for label in action_order:
        html_parts.append(f'<th style="color:{action_colors[label]}">{action_labels[label]}</th>')
    html_parts.append("</tr>")
    for cat in sorted(cat_counts):
        cc = cat_counts[cat]
        cat_total = sum(cc.values())
        html_parts.append(f"<tr><td><strong>{cat}</strong></td><td>{cat_total}</td>")
        for label in action_order:
            html_parts.append(f'<td style="color:{action_colors[label]};font-weight:600">{cc[label]}</td>')
        html_parts.append("</tr>")
    html_parts.append("</table>")

    for section_label in action_order:
        section_stocks = [s for s in stocks if s["action"] == section_label]
        if not section_stocks:
            continue
        html_parts.append(
            f'<h2 style="color:{action_colors[section_label]}">'
            f'{action_labels[section_label]} Signals ({len(section_stocks)})</h2>'
            f'<table><tr><th>Symbol</th><th>Name</th><th>Category</th><th>Reason</th><th>Close</th></tr>'
        )
        for s in section_stocks:
            n = s.get("name", s["symbol"])
            html_parts.append(
                f'<tr class="stock-row">'
                f'<td><strong>{s["symbol"]}</strong></td>'
                f'<td>{n}</td>'
                f'<td>{s["category"]}</td>'
                f'<td>{s["reason"]}</td>'
                f'<td>{s["close"]:.2f}</td></tr>'
            )
        html_parts.append("</table>")

    html_parts.append("</body></html>")
    allure.attach("\n".join(html_parts), "Scan Dashboard Summary", allure.attachment_type.HTML)

    signals = [s for s in stocks if s["action"] in ("BUY", "SELL")]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), facecolor="#f8f9fa")
    colors_pie = {"BUY": "#66BB6A", "SELL": "#EF5350", "HOLD": "#FFA726", "WATCH": "#90A4AE", "SKIP": "#CFD8DC"}
    labels = [k for k in ("BUY", "SELL", "HOLD", "WATCH", "SKIP") if counts.get(k, 0) > 0]
    sizes = [counts[k] for k in labels]
    pie_colors = [colors_pie.get(k, "#ccc") for k in labels]
    wedges, texts, autotexts = ax1.pie(
        sizes, labels=None, autopct="%1.1f%%", startangle=90,
        colors=pie_colors, shadow=False, wedgeprops={"linewidth": 1, "edgecolor": "white"},
        pctdistance=0.78
    )
    for t in autotexts:
        t.set_fontsize(9)
        t.set_fontweight("bold")
    ax1.set_title("Signal Distribution", fontsize=12, fontweight="bold", pad=12)
    ax1.legend(wedges, [f"{l} ({counts[l]})" for l in labels],
               title="Action", loc="center left", bbox_to_anchor=(-0.35, 0.5),
               fontsize=9, title_fontsize=10)

    cat_names = sorted(cat_counts.keys())
    x = range(len(cat_names))
    width = 0.2
    for j, label in enumerate(("BUY", "SELL", "HOLD", "WATCH", "SKIP")):
        values = [cat_counts[c][label] for c in cat_names]
        bars = ax2.bar([i + j * width for i in x], values, width,
                       label=label, color=colors_pie.get(label, "#ccc"),
                       edgecolor="white", linewidth=0.5)
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax2.text(bar.get_x() + bar.get_width() / 2, h,
                         str(int(h)), ha="center", va="bottom", fontsize=7)
    ax2.set_xticks([i + width * 2 for i in x])
    ax2.set_xticklabels(cat_names, fontsize=9, rotation=15)
    ax2.set_ylabel("Count", fontsize=9)
    ax2.set_title("Signals by Category", fontsize=12, fontweight="bold", pad=12)
    ax2.legend(fontsize=8, loc="upper right")
    ax2.grid(axis="y", alpha=0.25, linestyle=":", color="#bbb")
    fig.tight_layout()
    buf = BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
    plt.close(fig)
    allure.attach(buf.getvalue(), "Dashboard Charts", allure.attachment_type.PNG)

    summary_json = {
        "total": total,
        "counts": dict(counts),
        "categories": cat_names,
        "category_counts": {c: dict(cc) for c, cc in sorted(cat_counts.items())},
        "signals": [
            {"symbol": s["symbol"], "action": s["action"], "reason": s["reason"],
             "category": s["category"], "close": round(s["close"], 2)}
            for s in signals
        ],
    }
    allure.attach(json.dumps(summary_json, indent=2), "Dashboard JSON",
                  allure.attachment_type.JSON)
    allure.dynamic.title(f"Daily Scan Summary \u2014 {counts.get('BUY',0)} BUY, "
                         f"{counts.get('SELL',0)} SELL, "
                         f"{counts.get('HOLD',0)} HOLD, "
                         f"{counts.get('WATCH',0)} WATCH, "
                         f"{counts.get('SKIP',0)} SKIP ({total} stocks)")


# ── Cumulative Dashboard BDD Step ─────────────────────────────────────────

@then("I generate cumulative scan dashboard")
def generate_cumulative_dashboard():
    stocks, counts = _load_all_results()
    if stocks:
        generate_dashboard(stocks, counts)
    else:
        allure.attach("No scan results found in scan_results directory.", "Dashboard", allure.attachment_type.TEXT)


# ── BTST BDD Steps ──────────────────────────────────────────────────────────

_BTST_RESULTS_PATH = Path("tests/temp/btst_results")
_BTST_DATA_PATH: Path | None = None


@given("I have BTST symbols configured")
def btst_configure():
    _BTST_RESULTS_PATH.mkdir(parents=True, exist_ok=True)


@when(parsers.parse('I run BTST backtest for "{period}"'))
def btst_run(period: str):
    from agentest.utils.indicators.btst import run_btst_backtest
    global _BTST_DATA_PATH
    results = run_btst_backtest(period)
    o = results["overall"]
    report_path = _BTST_RESULTS_PATH / "btst_results.json"
    report_path.write_text(json.dumps(results, indent=2, default=lambda x: str(x)), encoding="utf-8")
    _BTST_DATA_PATH = report_path

    summary = (
        f"BTST Backtest completed\n"
        f"Total trades: {o['total_trades']}\n"
        f"Win rate: {o['win_rate']}%\n"
        f"Compound return: {o['compound_return_pct']}%\n"
        f"Avg option P&L: {o['avg_option_pnl_pct']}%\n"
        f"Wins: {o['wins']} / Losses: {o['losses']}"
    )
    allure.attach(summary, "BTST Backtest Summary", allure.attachment_type.TEXT)


@then("I generate BTST signals report")
def btst_signals():
    from agentest.utils.indicators.btst import generate_btst_report
    global _BTST_DATA_PATH
    if not _BTST_DATA_PATH or not _BTST_DATA_PATH.exists():
        allure.attach("No BTST data available.", "BTST Report", allure.attachment_type.TEXT)
        return
    data = json.loads(_BTST_DATA_PATH.read_text(encoding="utf-8"))
    path = generate_btst_report(data)
    allure.attach(str(path), "BTST Report Path", allure.attachment_type.TEXT)

    table_lines = ["| Symbol | Trades | Win Rate | Avg P&L% | Compound% |"]
    table_lines.append("|--------|--------|----------|----------|-----------|")
    for sym, s in sorted(data["per_symbol"].items()):
        table_lines.append(f"| {sym} | {s['total_trades']} | {s['win_rate']}% | {s['avg_pnl_pct']}% | {s['compound_return_pct']}% |")
    o = data["overall"]
    table_lines.append(f"| **TOTAL** | {o['total_trades']} | {o['win_rate']}% | {o['avg_pnl_pct']}% | {o['compound_return_pct']}% |")
    allure.attach("\n".join(table_lines), "BTST Per-Symbol Report", allure.attachment_type.TEXT)


@then("I generate BTST dashboard")
def btst_dashboard():
    global _BTST_DATA_PATH
    if not _BTST_DATA_PATH or not _BTST_DATA_PATH.exists():
        allure.attach("No BTST data found.", "BTST Dashboard", allure.attachment_type.TEXT)
        return
    data = json.loads(_BTST_DATA_PATH.read_text(encoding="utf-8"))
    o = data["overall"]
    allure.dynamic.title(f"BTST Dashboard — {o['total_trades']} trades, {o['win_rate']}% win rate")
    allure.attach(json.dumps(o, indent=2), "BTST Overall Summary", allure.attachment_type.JSON)
