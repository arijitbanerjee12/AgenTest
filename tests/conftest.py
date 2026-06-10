from datetime import datetime
import pytest
from agentest.core.context import Context

pytest_plugins = [
    "agentest.steps.context.context_steps",
    "agentest.steps.api.api_steps",
    "agentest.steps.indicators.indicator_steps",
]


# ── Global context (session-scoped, persists across all tests) ─────────────

@pytest.fixture(scope="session")
def global_context():
    return Context()


# ── Standard fixtures ────────────────────────────────────────────────────

@pytest.fixture
def symbol():
    return None


@pytest.fixture
def context():
    return Context()


# ── Hooks ────────────────────────────────────────────────────────────────

def pytest_configure(config):
    if not config.option.allure_report_dir:
        date_str = datetime.now().strftime("%Y%m%d")
        config.option.allure_report_dir = f"tests/temp/reports/allure_{date_str}"


def pytest_collection_modifyitems(config, items):
    """Move @summary tests to the end so they run after per-stock tests."""
    summary, rest = [], []
    for item in items:
        if item.get_closest_marker("summary"):
            summary.append(item)
        else:
            rest.append(item)
    items[:] = rest + summary


def pytest_sessionfinish(session):
    report_dir = session.config.option.allure_report_dir
    if report_dir:
        report_out = f"{report_dir}_report"
        tr = session.config.pluginmanager.get_plugin("terminalreporter")
        if tr:
            tr.ensure_newline()
            tr.write_line(f"  \u2514\u2500 Allure results: {report_dir}")
            tr.write_line(f"  \u2514\u2500 Generate report: allure generate --single-file {report_dir} -o {report_out}")
