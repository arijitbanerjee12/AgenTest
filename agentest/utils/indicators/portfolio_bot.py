"""Portfolio Bot — watches Slack for "I bought..." messages, updates portfolio.csv.

Requires:
  - SLACK_BOT_TOKEN env var (xoxb-...) with channels:history scope
  - SLACK_CHANNEL_ID env var
  - OR pass --token / --channel on CLI

Usage:
  uv run python -m agentest.utils.indicators.portfolio_bot
  uv run python -m agentest.utils.indicators.portfolio_bot --dry-run
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
import urllib.request
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

HOLDINGS_FILE = Path("tests/data/holdings/portfolio.csv")

# ── Known instrument → ticker mapping ──
KNOWN_NAMES: dict[str, str] = {
    "groww defence": "GROWWDEFNC.NS",
    "groww india defence": "GROWWDEFNC.NS",
    "defence etf": "GROWWDEFNC.NS",
    "nippon india etf defence": "GROWWDEFNC.NS",
    "icici nifty": "NIFTYIETF.NS",
    "icici prudential nifty": "NIFTYIETF.NS",
    "nifty etf": "NIFTYIETF.NS",
    "icici pharma": "HEALTHIETF.NS",
    "icici prudential pharma": "HEALTHIETF.NS",
    "pharma etf": "HEALTHIETF.NS",
    "nippon midcap": "MID150BEES.NS",
    "nippon india midcap": "MID150BEES.NS",
    "midcap 150": "MID150BEES.NS",
    "hdfc small cap": "HDFCSML250.NS",
    "hdfc small cap 250": "HDFCSML250.NS",
    "groww ev": "GROWWEV.NS",
    "ev etf": "GROWWEV.NS",
    "lic": "LICI.NS",
    "lic india": "LICI.NS",
    "dmart": "DMART.NS",
    "avenue supermarts": "DMART.NS",
    "alpha low volatility": "ALPHAETF.NS",
    "alpha etf": "ALPHAETF.NS",
    "power grid": "POWERGRID.NS",
    "powergrid": "POWERGRID.NS",
    "psu bank bees": "PSUBNKBEES.NS",
    "nippon psu bank": "PSUBNKBEES.NS",
    "groww small cap": "SMALL250.NS",
    "small cap 250": "SMALL250.NS",
    "groww metals": "GROWWMETAL.NS",
    "metals etf": "GROWWMETAL.NS",
    "it bees": "ITBEES.NS",
    "nippon it": "ITBEES.NS",
    "hindustan unilever": "HINDUNILVR.NS",
    "hul": "HINDUNILVR.NS",
    "icici bank": "ICICIBANK.NS",
    "bajaj finance": "BAJFINANCE.NS",
    "itc": "ITC.NS",
    "absl bank etf": "ABSLBANETF.NS",
    "aditya birla banking": "ABSLBANETF.NS",
    "bank bees": "BANKBEES.NS",
    "nippon bank bees": "BANKBEES.NS",
    "biret": "BIRET.NS",
    "brookfield": "BIRET.NS",
    "brookfield india": "BIRET.NS",
    "gold bees": "GOLDBEES.NS",
    "goldbees": "GOLDBEES.NS",
    "nippon gold": "GOLDBEES.NS",
    "mon100": "MON100.NS",
    "motilal nasdaq": "MON100.NS",
    "nasdaq 100": "MON100.NS",
    "mosmall250": "MOSMALL250.NS",
    "motilal oswal small cap": "MOSMALL250.NS",
    "silver bees": "SILVERBEES.NS",
    "silverbees": "SILVERBEES.NS",
    "nippon silver": "SILVERBEES.NS",
    "reliance": "RELIANCE.NS",
    "rcom": "RELIANCE.NS",
    "tcs": "TCS.NS",
    "infosys": "INFY.NS",
    "hdfc bank": "HDFCBANK.NS",
    "sbin": "SBIN.NS",
    "state bank": "SBIN.NS",
    "bharti airtel": "BHARTIARTL.NS",
    "airtel": "BHARTIARTL.NS",
    "icici": "ICICIBANK.NS",
    "kotak bank": "KOTAKBANK.NS",
    "kotak mahindra": "KOTAKBANK.NS",
    "bajaj finserv": "BAJAJFINSV.NS",
    "bajaj auto": "BAJAJ-AUTO.NS",
    "ntpc": "NTPC.NS",
    "coal india": "COALINDIA.NS",
    "dr reddy": "DRREDDY.NS",
    "drreddy": "DRREDDY.NS",
    "jsw steel": "JSWSTEEL.NS",
    "hdfc life": "HDFCLIFE.NS",
    "hdfc life insurance": "HDFCLIFE.NS",
    "m&m": "M&M.NS",
    "mahindra": "M&M.NS",
    "bel": "BEL.NS",
    "bharat electronics": "BEL.NS",
    "bajaj auto": "BAJAJ-AUTO.NS",
    "sensex": "SENSEX",
}

# ── Pattern matches ──
# "I bought GROWWDEFNC 100 shares at 91"
# "bought 50 ITBEES at ₹32"
# "bought LICI 20 @ 450"
# "i bought reliance 10 shares @ 2500"
BUY_PATTERN = re.compile(
    r"(?:i\s+)?bought\s+"
    r"(?:(?P<qty1>\d+)\s+)?"
    r"(?P<name>[a-zA-Z0-9\s&.-]+?)\s+"
    r"(?:(?P<qty2>\d+)\s+(?:shares|units|qty|qt|share|unit)s?\s+)?"
    r"(?:(?:at|@)\s*[₹Rs.]*\s*(?P<price>[\d,.]+))?",
    re.IGNORECASE,
)


def _load_portfolio() -> list[dict]:
    if not HOLDINGS_FILE.exists():
        return []
    with open(HOLDINGS_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save_portfolio(rows: list[dict]):
    HOLDINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HOLDINGS_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["instrument", "ticker", "category", "units", "invested"])
        w.writeheader()
        w.writerows(rows)


def _resolve_ticker(name: str) -> tuple[str, str]:
    """Resolve free-text name to (ticker, instrument_name)."""
    key = name.strip().lower()

    # Try direct ticker match (user typed .NS or sans .NS)
    for suffix in ("", ".NS", ".BO"):
        t = key.upper() + suffix
        if t.endswith(".NS") or t.endswith(".BO"):
            return t, key.upper()

    # Try known names
    if key in KNOWN_NAMES:
        ticker = KNOWN_NAMES[key]
        return ticker, key.title()

    # Fuzzy: partial match
    for alias, ticker in KNOWN_NAMES.items():
        if key in alias or alias in key:
            return ticker, key.title()

    return key.upper() + ".NS", key.title()


def _resolve_category(ticker: str) -> str:
    t = ticker.upper()
    if t.endswith(".NS"):
        return "large_cap"  # default; user can override
    return "etf"


def parse_buy_message(text: str) -> list[dict]:
    """Parse a Slack message for multiple 'bought' mentions.
    Returns list of dicts with instrument, ticker, units, price, category.
    """
    results = []
    for m in BUY_PATTERN.finditer(text):
        name = m.group("name").strip()
        qty = int(m.group("qty1") or m.group("qty2") or 1)
        price_str = m.group("price")
        price = float(price_str.replace(",", "")) if price_str else None

        ticker, instr = _resolve_ticker(name)
        results.append({
            "instrument": instr,
            "ticker": ticker,
            "units": qty,
            "price": price,
            "category": _resolve_category(ticker),
        })
    return results


def apply_purchase(purchase: dict, portfolio: list[dict]) -> str:
    """Merge one purchase into the portfolio. Returns a status message."""
    ticker = purchase["ticker"]
    units = purchase["units"]
    price = purchase["price"]
    instr = purchase["instrument"]
    cat = purchase["category"]

    for row in portfolio:
        if row["ticker"].upper() == ticker.upper():
            # Holding exists → add to units, recompute avg cost
            old_units = float(row["units"])
            old_invested = float(row["invested"])
            new_invested = (price * units) if price else 0
            total_units = old_units + units
            total_invested = old_invested + new_invested
            row["units"] = str(total_units)
            row["invested"] = f"{total_invested:.2f}"
            return f"Updated {instr} ({ticker}): {old_units} → {total_units} units, avg cost ₹{total_invested/total_units:.2f}"

    # New holding
    invested = (price * units) if price else 0
    portfolio.append({
        "instrument": instr,
        "ticker": ticker,
        "category": cat,
        "units": str(units),
        "invested": f"{invested:.2f}",
    })
    return f"Added {instr} ({ticker}): {units} units" + (f" @ ₹{price}" if price else "")


# ═════════════════════════════════════════════════════════════════════
#  Slack API helpers (requires user token)
# ═════════════════════════════════════════════════════════════════════

SLACK_API = "https://slack.com/api"


def _slack_get(token: str, method: str, params: dict | None = None) -> dict:
    if params is None:
        params = {}
    params["token"] = token
    qs = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
    req = urllib.request.Request(f"{SLACK_API}/{method}?{qs}")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def fetch_recent_messages(token: str, channel: str, limit: int = 20) -> list[dict]:
    """Fetch recent messages from a Slack channel."""
    data = _slack_get(token, "conversations.history", {"channel": channel, "limit": limit})
    if not data.get("ok"):
        print(f"  [Slack API] Error: {data.get('error', 'unknown')}")
        return []
    return data.get("messages", [])


def get_channel_id(token: str, channel_name: str) -> str | None:
    """Resolve #channel-name to channel ID."""
    cursor = None
    while True:
        params: dict = {"limit": 200, "types": "public_channel"}
        if cursor:
            params["cursor"] = cursor
        data = _slack_get(token, "conversations.list", params)
        if not data.get("ok"):
            return None
        for ch in data.get("channels", []):
            if ch["name"] == channel_name.lstrip("#"):
                return ch["id"]
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return None


# ═════════════════════════════════════════════════════════════════════
#  Main CLI
# ═════════════════════════════════════════════════════════════════════

def main():
    parser = ArgumentParser(description="Portfolio Bot — read Slack messages and update portfolio.csv")
    parser.add_argument("--token", help="Slack Bot Token (xoxb-...)")
    parser.add_argument("--channel", help="Channel ID or #channel-name")
    parser.add_argument("--dry-run", action="store_true", help="Parse and show but don't write")
    parser.add_argument("--limit", type=int, default=20, help="Messages to fetch")
    parser.add_argument("--watch", action="store_true", help="Poll every 60s")
    args = parser.parse_args()

    token = args.token or os.environ.get("SLACK_BOT_TOKEN")
    channel = args.channel or os.environ.get("SLACK_CHANNEL_ID")

    if not token or not channel:
        print("Error: need --token and --channel (or SLACK_BOT_TOKEN / SLACK_CHANNEL_ID env vars)")
        sys.exit(1)

    # Resolve channel name → ID
    if channel.startswith("#"):
        resolved = get_channel_id(token, channel)
        if not resolved:
            print(f"  Could not resolve {channel}")
            sys.exit(1)
        channel = resolved
        print(f"  Resolved channel → {channel}")

    def check_once():
        messages = fetch_recent_messages(token, channel, limit=args.limit)
        portfolio = _load_portfolio()
        modified = False

        for msg in reversed(messages):
            text = msg.get("text", "")
            purchases = parse_buy_message(text)
            if not purchases:
                continue
            ts = datetime.fromtimestamp(float(msg["ts"])).strftime("%H:%M")
            print(f"  [{ts}] {msg.get('user', '?')}: {text}")
            for p in purchases:
                print(f"    → {p['instrument']} ({p['ticker']}): {p['units']} units", end="")
                if p["price"]:
                    print(f" @ ₹{p['price']}", end="")
                if not args.dry_run:
                    result = apply_purchase(p, portfolio)
                    modified = True
                    print(f"  {result}", end="")
                print()

        if modified and not args.dry_run:
            _save_portfolio(portfolio)
            print(f"\n  Portfolio saved ({HOLDINGS_FILE})")

    check_once()

    if args.watch:
        print("\n  Watching for new messages (Ctrl+C to stop)...")
        last_ts = ""
        try:
            while True:
                time.sleep(60)
                check_once()
        except KeyboardInterrupt:
            print("\n  Stopped.")


if __name__ == "__main__":
    main()
