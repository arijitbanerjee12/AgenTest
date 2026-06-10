# AgenTest — Focus Scan Framework

AI-native agentic testing for **technical + fundamental stock scanning** (ETFs + Large Caps) using **pytest + pytest-bdd**, **yfinance + pandas**, **matplotlib**, and **Allure**.

---

## 1. Project Structure

```
agentest/                           ← Framework core
├── cli.py                          ← CLI (run, init)
├── core/                           ← Context, engine
├── steps/indicators/indicator_steps.py ← BDD step definitions
├── utils/
│   ├── config/settings.py          ← Pydantic Settings + YAML loading
│   ├── indicators/                 ← EMA, HA, scanner, chart, data, backtest, fundamental_analysis, enriched_report
│   ├── common/json_path.py         ← Dot/bracket path getter/setter
│   └── llm/                        ← LLM providers (optional, not used in focus workflow)
└── skills/workflows/               ← Agent workflow instructions

tests/                              ← Test suite
├── conftest.py                     ← Fixtures, hooks, auto-alluredir
├── test_runner.py                  ← @scenario parametrized tests (focus_scan only)
├── features/indicators/
│   └── focus_scan.feature          ← BDD feature file (ETFs + large caps)
├── data/stocks/
│   ├── etfs.csv                    ← 75 ETF symbols
│   └── focus_large_cap.csv         ← Top 30 Nifty 50 symbols
└── temp/                           ← Reports, scans, charts

agentest_app/groq_api_mock/         ← Mock Groq API (FastAPI, port 8001)
```

---

## 2. Getting Started

```powershell
uv sync --group dev                                    # Install
uv run python scripts/run_daily.py                     # Full daily scan (long-term + BTST + options)
.\focus_scan.ps1 -Workers 6                            # Same via PowerShell
uv run pytest tests/test_runner.py -m "focus_scan" -n 6 -v  # Technical scan only (105 tests)
uv run pytest tests/test_runner.py -m "btst_scan" -v        # BTST backtest only (2 tests)
```

**Test count:** 105 focus + 2 BTST = **107 tests**

---

## 3. Data Files

| File | Location | Format |
|---|---|---|
| ETF symbols | `tests/data/stocks/etfs.csv` | Header: `symbol` — 75 symbols |
| Large cap symbols | `tests/data/stocks/focus_large_cap.csv` | Header: `symbol,category` — 30 symbols |

`load_symbols_from_csv(path)` reads the first column automatically.

---

## 4. Import Rules

```python
# ✅ Correct paths
from agentest.utils.indicators.ema import compute_ema
from agentest.utils.indicators.heikin_ashi import scan_combined
from agentest.utils.indicators.data import fetch_data, load_symbols_from_csv
from agentest.utils.indicators.chart import generate_report
from agentest.utils.indicators.scanner import run_daily_scan
from agentest.utils.indicators.backtest import backtest_symbol
from agentest.utils.indicators.fundamental_analysis import analyze_signal, analyze_batch
from agentest.utils.indicators.enriched_report import generate_enriched_report
from agentest.utils.config.settings import Settings, load_config
from agentest.steps.indicators.indicator_steps import ...
from agentest.core.context import Context
```

**Step plugin registration** in `conftest.py`:
```python
pytest_plugins = [
    "agentest.steps.context.context_steps",
    "agentest.steps.indicators.indicator_steps",
]
```

---

## 5. Pipeline (`scripts/run_daily.py` / `focus_scan.ps1`)

| Step | Action | Output |
|---|---|---|
| 1 | `pytest -m "focus_scan"` — EMA 10/20 + Heikin-Ashi per stock | `tests/temp/scan_results/*.json` |
| 2 | AI fundamental analysis + enriched Excel report | `~/Documents/Agentest_Reports/.../FocusScan_*.xlsx` |
| 3 | **BTST backtest** — hourly signals on top 7 symbols (Nifty, BankNifty, Sensex + ICICI, HDFC, SBIN, Bharti) with 2 exit strategies | `~/Documents/Agentest_Reports/.../BTST_Backtest_*.xlsx` |
| 4 | Today's BTST signals (15m data) + options recommendation | Console output |
| 5 | Combined summary + Allure HTML report | Console + `tests/temp/reports/` |

**Focus Scan Report** (3 sheets):
- **All Signals** — 105 stocks with tech + fundamental columns
- **AI Analysis** — BUY/SELL with sector-based AI verdicts
- **Summary** — action counts + AI verdict distribution

**BTST Report** (3 sheets):
- **Summary** — overall win rate, P&L, compound return, option P&L
- **Per Symbol** — per-stock breakdown (ICICIBANK, BANKNIFTY, HDFCBANK, SBIN, NIFTY, SENSEX, BHARTIARTL)
- **All Trades** — individual trade log with entry/exit, P&L%, options view

---

## 6. BDD Conventions

### Feature File (`tests/features/indicators/focus_scan.feature`)
```gherkin
@focus_scan
Scenario: Focus ETF scan
  Given I configure EMA indicators
  When I analyze stock for "3y"
  Then I check signal in category "etf"
```

### Test Runner Pattern
```python
@pytest.mark.focus_scan @pytest.mark.etf
@pytest.mark.parametrize("symbol", load_symbols_from_csv("..."))
@scenario("features/indicators/focus_scan.feature", "Focus ETF scan")
def test_focus_etf_scan(symbol): pass
```

### Markers
`focus_scan`, `etf`, `large_cap_focus`, `summary`, `indicator_test`, `btst_scan`

---

## 7. Fundamental Analysis (AI Knowledge Base)

`agentest/utils/indicators/fundamental_analysis.py` — no external API calls.

**Knowledge base includes:**
- **50+ sectors** mapped with PE ranges, growth outlook, trend notes
- **30 large cap stocks** with specific business notes
- **ETF knowledge** for gold, debt, index, sector, factor, thematic ETFs

**Key functions:**

| Function | Purpose |
|---|---|
| `analyze_signal(symbol, action, reason, category)` | Returns dict with sentiment, score, support, verdict |
| `analyze_batch(signals)` | Batch analysis (no LLM, runs in 1-2s) |

**Verdict logic:** Combines sector growth outlook + technical signal direction + sentiment scoring. Special overrides for gold (hold on sell, gold bull market) and debt ETFs (technical signals less relevant).

---

## 8. Backtesting

`agentest/utils/indicators/backtest.py` — walk-forward strategy backtester.

| Function | Purpose |
|---|---|
| `backtest_symbol(symbol, csv_path, ...)` | Full backtest for one symbol |
| `run_backtest_for_category(category, ...)` | Multi-threaded category backtest |

**Key metrics:** Win rate, profit factor, compound return, total trades, total PnL, avg holding days, concurrent positions.

---

## 9. Allure Reporting

Auto-configured in `conftest.py` — results go to `tests/temp/reports/allure_YYYYMMDD/`.

```powershell
allure generate --single-file tests/temp/reports/allure_YYYYMMDD -o tests/temp/reports/allure_YYYYMMDD_report
```

Per-stock charts: EMA lines, HA candles, Buy/Sell markers (150 DPI). Dashboard: pie + bar chart, HTML table, JSON dump.

---

## 10. Code Style

- No comments unless asked
- Type hints (PEP 484), prefer `from __future__ import annotations`
- Line length: **100**
- matplotlib: `matplotlib.use("Agg")` inside function, never module-level
- BDD steps: pytest-bdd decorators (`@given`, `@when`, `@then`)
- Parametrization: `@pytest.mark.parametrize` on test function, never `pytest_generate_tests`
- Imports: absolute from `agentest.*` only
