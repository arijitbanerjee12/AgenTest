import pytest
from agentest.core.context import Context

pytest_plugins = [
    "agentest.steps.context_steps",
    "agentest.steps.api_steps",
]


@pytest.fixture
def context():
    return Context()
