from pathlib import Path
import pytest
from pytest_bdd import scenario
from agentest.utils.indicators.data import load_symbols_from_csv

CSV_DIR = Path(__file__).resolve().parent / "data" / "stocks"


# ──────────────────── Focus Scan — ETFs + Top 30 Large Caps ────────────────────

@pytest.mark.focus_scan
@pytest.mark.etf
@pytest.mark.parametrize("symbol", load_symbols_from_csv(str(CSV_DIR / "etfs.csv")))
@scenario("features/indicators/focus_scan.feature", "Focus ETF scan")
def test_focus_etf_scan(symbol):
    pass


@pytest.mark.focus_scan
@pytest.mark.large_cap_focus
@pytest.mark.parametrize("symbol", load_symbols_from_csv(str(CSV_DIR / "focus_large_cap.csv")))
@scenario("features/indicators/focus_scan.feature", "Focus Large Cap scan")
def test_focus_large_cap_scan(symbol):
    pass


@pytest.mark.focus_scan
@pytest.mark.summary
@scenario("features/indicators/focus_scan.feature", "Focus Scan Summary Dashboard")
def test_focus_scan_summary():
    pass


# ──────────────────── BTST Backtest — Indices + Top 10 Large Caps ────────────────────

@pytest.mark.btst_scan
@scenario("features/indicators/btst_scan.feature", "Run BTST backtest")
def test_btst_backtest():
    pass


@pytest.mark.btst_scan
@pytest.mark.summary
@scenario("features/indicators/btst_scan.feature", "BTST Summary Dashboard")
def test_btst_summary():
    pass
