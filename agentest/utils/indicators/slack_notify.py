"""Slack notification — two webhooks: BTST signals + Long-term reports."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

import urllib.request

from agentest.utils.indicators.btst import INDEX_NAMES

# ── Webhooks (set env vars SLACK_BTST_WEBHOOK / SLACK_LONG_TERM_WEBHOOK) ──
BTST_WEBHOOK = os.getenv("SLACK_BTST_WEBHOOK", "")
LONG_TERM_WEBHOOK = os.getenv("SLACK_LONG_TERM_WEBHOOK", "")
REPORTS_DIR = Path.home() / "Documents" / "Agentest_Reports"


def _send(webhook: str, text: str) -> bool:
    try:
        data = json.dumps({"text": text}).encode("utf-8")
        req = urllib.request.Request(webhook, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req)
        return True
    except Exception as e:
        print(f"  [Slack] Failed: {e}")
        return False


def _price_fmt(val) -> str:
    try:
        v = float(val)
        if v >= 10000:
            return f"₹{v:,.0f}"
        return f"₹{v:,.2f}"
    except (ValueError, TypeError):
        return str(val)


def _sig_icon(sig: str) -> str:
    return {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡", "WATCH": "👀"}.get(sig, "⚪")


# ═════════════════════════════════════════════════════════════════════
#  BTST Signals → BTST_WEBHOOK
# ═════════════════════════════════════════════════════════════════════

def send_btst_daily(
    btst_signals: list[dict] | None = None,
    long_term_counts: dict[str, int] | None = None,
    btst_summary: dict | None = None,
    hm_summary: dict | None = None,
    scan_date: str | None = None,
):
    date_str = scan_date or datetime.now().strftime("%d %b %Y")
    parts = [f"📊 *Agentest Daily — {date_str}*"]

    if long_term_counts:
        total = sum(long_term_counts.values())
        b = long_term_counts.get("BUY", 0)
        s = long_term_counts.get("SELL", 0)
        h = long_term_counts.get("HOLD", 0)
        w = long_term_counts.get("WATCH", 0)
        parts.append(f"\n*Long-Term:* {total} stocks  ·  🟢 BUY {b}  🔴 SELL {s}  🟡 HOLD {h}  👀 WATCH {w}")

    if btst_signals:
        # Build performance ranking from backtest summary (for sort order)
        perf_rank: dict[str, float] = {}
        if btst_summary:
            per_sym = btst_summary.get("per_symbol", {})
            for sym_name, stats in per_sym.items():
                perf_rank[sym_name] = stats.get("win_rate", 0)

        def _render_combined_table(signals: list[dict], title: str) -> str:
            """Render one table: rows = symbols, columns = HA sig+reason+invest | HM sig+reason+invest."""
            def _sig_with_inv(r):
                sig = r.get("signal", "")
                rs = r.get("recommended_premium_rs")
                if sig in ("SKIP", "NO DATA") or not rs:
                    return f"{_sig_icon(sig)} {sig}"
                return f"{_sig_icon(sig)} {sig} ₹{rs:,}"
            ha = {r["name"]: r for r in signals if r.get("strategy") != "HM" and r.get("signal") in ("BUY","SELL","HOLD","WATCH")}
            hm = {r["name"]: r for r in signals if r.get("strategy") == "HM" and r.get("signal") in ("BUY","SELL","HOLD","WATCH")}
            all_names = list(set(ha) | set(hm))
            # Sort by BTST backtest win rate descending, then alphabetically
            all_names.sort(key=lambda n: (-perf_rank.get(n, 0), n))
            if not all_names:
                return ""
            lines = [f"\n*{title}*", "```"]
            hdr = f"{'Symbol':<14} {'HA':<18} {'HA Reason':<35} {'HM':<18} {'HM Reason'}"
            lines.append(hdr)
            lines.append("-" * 130)
            for name in all_names:
                hr = ha.get(name)
                hmr = hm.get(name)
                ha_sig_str = _sig_with_inv(hr) if hr else "—"
                ha_reason = hr["reason"][:33] if hr else "—"
                hm_sig_str = _sig_with_inv(hmr) if hmr else "—"
                hm_reason = hmr["reason"][:45] if hmr else "—"
                lines.append(f"{name:<14} {ha_sig_str:<18} {ha_reason:<35} {hm_sig_str:<18} {hm_reason}")
            lines.append("```")
            return "\n".join(lines)

        # Split: indices vs stocks
        idx_signals = [r for r in btst_signals if r.get("name") in INDEX_NAMES]
        stock_signals = [r for r in btst_signals if r.get("name") not in INDEX_NAMES]

        if idx_signals:
            parts.append(_render_combined_table(idx_signals, "🏛️ Indices"))

        if stock_signals:
            parts.append(_render_combined_table(stock_signals, "📈 All Stocks"))

        parts.append("_Capital ₹1L · HA: ₹2,500–₹10,000/trade · HM: ₹5,000/trade_")

    if btst_summary:
        o = btst_summary.get("overall", {})
        if o.get("total_trades", 0) > 0:
            wr = o.get("win_rate", 0)
            opt_rs = o.get("total_option_pnl_rs", 0)
            roi = o.get("option_roi_pct", 0)
            parts.append(f"\n*📈 Backtest (HA):* {o['total_trades']} trades  ·  {wr}% WR  ·  ₹{opt_rs:,} opt  ·  {roi}% ROI")
            ps = btst_summary.get("per_symbol", {})
            top5 = sorted(ps.items(), key=lambda x: x[1]["win_rate"], reverse=True)[:5]
            if top5:
                top_items = [f"{s} {d['win_rate']}%" for s, d in top5]
                parts.append(f"   *Top5:* {'  ·  '.join(top_items)}")

    if hm_summary:
        o = hm_summary.get("overall", {})
        if o.get("total_trades", 0) > 0:
            wr = o.get("win_rate", 0)
            opt_rs = o.get("total_option_pnl_rs", 0)
            roi = o.get("option_roi_pct", 0)
            parts.append(f"\n*🔵 Backtest (HM):* {o['total_trades']} trades  ·  {wr}% WR  ·  ₹{opt_rs:,} opt  ·  {roi}% ROI")
            ps = hm_summary.get("per_symbol", {})
            top5 = sorted(ps.items(), key=lambda x: x[1]["win_rate"], reverse=True)[:5]
            if top5:
                top_items = [f"{s} {d['win_rate']}%" for s, d in top5]
                parts.append(f"   *Top:* {'  ·  '.join(top_items)}")

    today_folder = datetime.now().strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / today_folder
    if report_path.exists():
        parts.append(f"\n📁 `{report_path}`")

    _send(BTST_WEBHOOK, "\n".join(parts))


# ═════════════════════════════════════════════════════════════════════
#  Long-term Scan Report → LONG_TERM_WEBHOOK
# ═════════════════════════════════════════════════════════════════════

_CATEGORY_LABELS = {
    "etf": "📦 ETFs",
    "large_cap": "📈 Stocks (Large Cap)",
    "mid_small_cap": "📊 Stocks (Mid/Small Cap)",
}
_CAT_ORDER = ["etf", "large_cap", "mid_small_cap"]


def _group_signals(signals: list[dict]) -> list[tuple[str, list[dict]]]:
    """Group signals by category, ordered ETFs → Large Cap → Mid/Small Cap."""
    groups: dict[str, list[dict]] = {}
    for s in signals:
        cat = s.get("category", "other")
        groups.setdefault(cat, []).append(s)
    result = []
    for cat in _CAT_ORDER:
        if cat in groups:
            result.append((_CATEGORY_LABELS.get(cat, cat.title()), groups[cat]))
    return result


def _render_signal_table(signals: list[dict]) -> str:
    lines = ["```"]
    lines.append(f"{'Symbol':<18} {'Price':>10} {'Reason'}")
    lines.append("-" * 55)
    for r in signals:
        sym = r.get("symbol", "").replace(".NS", "")
        close = _price_fmt(r.get("close", ""))
        reason = r.get("reason", "")
        lines.append(f"{sym:<18} {close:>10} {reason}")
    lines.append("```")
    return "\n".join(lines)


def send_longterm_report(
    buy_signals: list[dict] | None = None,
    sell_signals: list[dict] | None = None,
    holdings_alerts: list[dict] | None = None,
    counts: dict[str, int] | None = None,
    scan_date: str | None = None,
):
    """Post a clean long-term scan report to the #long-term Slack channel."""
    date_str = scan_date or datetime.now().strftime("%d %b %Y")
    parts = [f"📈 *Long-Term Scan — {date_str}*"]

    if counts:
        total = sum(counts.values())
        b = counts.get("BUY", 0)
        s = counts.get("SELL", 0)
        h = counts.get("HOLD", 0)
        w = counts.get("WATCH", 0)
        parts.append(f"\n*Summary:* {total} stocks  ·  🟢 BUY {b}  🔴 SELL {s}  🟡 HOLD {h}  👀 WATCH {w}")

    # BUY signals — grouped by category
    if buy_signals:
        parts.append(f"\n*🟢 BUY Signals ({len(buy_signals)} total)*")
        for label, group in _group_signals(buy_signals):
            parts.append(f"\n  {label}")
            parts.append(_render_signal_table(group))

    # SELL signals — grouped by category
    if sell_signals:
        parts.append(f"\n*🔴 SELL Signals ({len(sell_signals)} total)*")
        for label, group in _group_signals(sell_signals):
            parts.append(f"\n  {label}")
            parts.append(_render_signal_table(group))

    # Holdings alert
    if holdings_alerts:
        parts.append(f"\n🔴 *Holdings Alert — SELL on your portfolio*")
        for h in holdings_alerts:
            parts.append(f"   • {h.get('instrument', '')} ({h.get('ticker', '')})")

    today_folder = datetime.now().strftime("%Y-%m-%d")
    report_path = REPORTS_DIR / today_folder
    if report_path.exists():
        parts.append(f"\n📁 `{report_path}`")

    _send(LONG_TERM_WEBHOOK, "\n".join(parts))
