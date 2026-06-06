from typing import Any
import allure
import json
from pytest_bdd import when, then, parsers


def _coerce_context_value(raw: str) -> Any:
    raw = raw.strip()
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    if raw.lower() == "null":
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


@when(parsers.parse('I save "{value}" in context at "{path}"'))
def save_in_context(context, value: str, path: str):
    with allure.step(f'Save "{value}" in context at "{path}"'):
        parts = path.replace("[", ".").replace("]", "").split(".")
        target = context
        for part in parts[:-1]:
            target = target[int(part)] if part.lstrip("-").isdigit() else target[part]
        key = parts[-1]
        if key.lstrip("-").isdigit():
            target[int(key)] = value
        else:
            target[key] = value
        allure.attach(json.dumps({"path": path, "value": value}, indent=2), "Context Save", allure.attachment_type.JSON)


@then(parsers.parse('the context at "{path}" should be set'))
def verify_context_set(context, path: str):
    with allure.step(f'Verify context at "{path}" is set'):
        parts = path.replace("[", ".").replace("]", "").split(".")
        target = context
        for part in parts:
            target = target[int(part)] if part.lstrip("-").isdigit() else target[part]
        assert target is not None and target != "", f"Expected '{path}' to be set, but got {target!r}"
        allure.attach(json.dumps({"path": path, "value": str(target)}, indent=2), "Context Set Verification", allure.attachment_type.JSON)


@then(parsers.parse('the context at "{path}" should be "{expected}"'))
def verify_context(context, path: str, expected: str):
    with allure.step(f'Verify context at "{path}" equals "{expected}"'):
        parts = path.replace("[", ".").replace("]", "").split(".")
        target = context
        for part in parts:
            target = target[int(part)] if part.lstrip("-").isdigit() else target[part]
        expected_coerced = _coerce_context_value(expected)
        assert target == expected_coerced, f"Expected '{expected_coerced}', got '{target}'"
        allure.attach(json.dumps({"path": path, "expected": expected_coerced, "actual": target, "coerced": str(expected_coerced != expected)}, indent=2), "Context Verification", allure.attachment_type.JSON)

