import builtins
import json
import re
from typing import Any
import allure
from pytest_bdd import given, when, then, parsers
from agentest.utils.api.api_client import ApiClient, SpecLoader
from agentest.utils.common.json_path import get_value, set_value
from agentest.utils.llm.prompt_loader import build_llm_prompt
from agentest.utils.config.settings import load_config
from agentest.utils.llm import LLMRegistry


@given(parsers.parse('I am testing application "{app_name}" for "{test_type}"'))
def set_app_context(context, app_name: str, test_type: str):
    with allure.step(f'Set application context: "{app_name}" / "{test_type}"'):
        context.app_name = app_name
        context.test_type = test_type
        allure.attach(
            json.dumps({"app_name": app_name, "test_type": test_type}, indent=2),
            "Application Context",
            allure.attachment_type.JSON,
        )


def _ensure_api(context) -> None:
    raw = object.__getattribute__(context, "_store")
    if "_api" not in raw:
        raw["_api"] = ApiClient()


@given(parsers.parse('I set the base url to "{url}"'))
def set_base_url(context, url: str):
    with allure.step(f'Set base URL to "{url}"'):
        _ensure_api(context)
        context._api.set_base_url(url)
        allure.attach(url, "Base URL", allure.attachment_type.TEXT)


@given(parsers.parse('I set the base url from spec "{spec_name}"'))
def set_base_url_from_spec(context, spec_name: str):
    with allure.step(f'Set base URL from spec "{spec_name}"'):
        loader = SpecLoader(
            app_name=getattr(context, "app_name", None),
            test_type=getattr(context, "test_type", None),
        )
        spec = loader.load(spec_name)
        url = spec.get("base_url", "http://localhost:8000")
        _ensure_api(context)
        context._api.set_base_url(url)
        allure.attach(url, "Base URL (from spec)", allure.attachment_type.TEXT)


@given(parsers.parse('I append "{path}" to the base url'))
def append_to_url(context, path: str):
    with allure.step(f'Append path "{path}"'):
        _ensure_api(context)
        context._api.append_path(path)
        allure.attach(context._api.url, "Full URL", allure.attachment_type.TEXT)


@given(parsers.parse('I add query param "{key}" to "{value}"'))
def add_query_param(context, key: str, value: str):
    with allure.step(f'Add query param "{key}" = "{value}"'):
        _ensure_api(context)
        context._api.append_query({key: value})
        allure.attach(
            json.dumps({key: value}, indent=2),
            "Query Parameter",
            allure.attachment_type.JSON,
        )


@given("I set the headers")
def set_headers_table(context, datatable):
    with allure.step("Set request headers"):
        _ensure_api(context)
        headers = {}
        for row in datatable:
            if len(row) >= 2:
                context._api.headers[row[0]] = row[1]
                headers[row[0]] = row[1]
        allure.attach(
            json.dumps(headers, indent=2),
            "Headers",
            allure.attachment_type.JSON,
        )


@given(parsers.parse('I set header "{name}" to "{value}"'))
def set_single_header(context, name: str, value: str):
    with allure.step(f'Set header "{name}" = "{value}"'):
        _ensure_api(context)
        context._api.headers[name] = value
        allure.attach(
            json.dumps({name: value}, indent=2),
            "Header",
            allure.attachment_type.JSON,
        )


@given(parsers.parse('I set the api body from spec "{spec_name}"'))
def set_body_from_spec(context, spec_name: str):
    with allure.step(f'Set body from spec "{spec_name}"'):
        _ensure_api(context)
        context._api.set_body_from_spec(
            spec_name,
            app_name=getattr(context, "app_name", None),
            test_type=getattr(context, "test_type", None),
        )
        _attach_body(context._api.body)


@given(parsers.parse('I set the api body from spec "{spec_name}" variant "{variant}"'))
def set_body_from_spec_variant(context, spec_name: str, variant: str):
    with allure.step(f'Set body from spec "{spec_name}" variant "{variant}"'):
        _ensure_api(context)
        context._api.set_body_from_spec(
            spec_name,
            variant,
            app_name=getattr(context, "app_name", None),
            test_type=getattr(context, "test_type", None),
        )
        _attach_body(context._api.body)


@given(parsers.parse('I set the api body from file "{file_path}"'))
def set_body_from_file(context, file_path: str):
    with allure.step(f'Set body from file "{file_path}"'):
        _ensure_api(context)
        context._api.set_body_from_file(file_path)
        _attach_body(context._api.body)


@given("I set the api body")
def set_body_inline(context, datatable):
    with allure.step("Set body inline from table"):
        body = {}
        for row in datatable:
            if len(row) >= 2:
                path = row[0].strip()
                parsed = _parse_body_value(row[1].strip())
                body = set_value(body, path, parsed)
        _ensure_api(context)
        context._api.set_body(body)
        _attach_body(body)


@given(parsers.parse('I update the api body at "{path}" to "{value}"'))
def update_body_at_path(context, path: str, value: str):
    with allure.step(f'Update body at "{path}" = "{value}"'):
        _ensure_api(context)
        parsed = _parse_body_value(value)
        context._api.body = set_value(context._api.body or {}, path, parsed)
        allure.attach(
            json.dumps({"path": path, "value": parsed}, indent=2, default=str),
            "Body Update",
            allure.attachment_type.JSON,
        )


@given("I update the api body")
def update_body_table(context, datatable):
    with allure.step("Update body from table"):
        _ensure_api(context)
        updates = []
        for row in datatable:
            if len(row) >= 2:
                path = row[0].strip()
                parsed = _parse_body_value(row[1].strip())
                context._api.body = set_value(context._api.body or {}, path, parsed)
                updates.append({"path": path, "value": parsed})
        allure.attach(
            json.dumps(updates, indent=2, default=str),
            "Body Updates",
            allure.attachment_type.JSON,
        )


@when(parsers.parse('I hit the {method} api'))
def hit_api(context, method: str):
    with allure.step(f'HIT {method.upper()} {context._api.url}'):
        _ensure_api(context)
        _attach_request(context)
        context._api.hit(method)
        _attach_response(context._api.response)


@then(parsers.parse("the status code should be {code:d}"))
def validate_status(context, code: int):
    with allure.step(f'Verify status code is {code}'):
        _ensure_api(context)
        actual = context._api.response.status_code if context._api.response else None
        _save_status_code(context, actual)
        allure.attach(
            json.dumps(
                {
                    "expected": code,
                    "actual": actual,
                    "passed": actual == code,
                },
                indent=2,
            ),
            "Status Validation",
            allure.attachment_type.JSON,
        )
        context._api.validate_status(code)


def _save_status_code(context, code: int | None) -> None:
    store = object.__getattribute__(context, "_store")
    store.setdefault("api_response", {})["status_code"] = code


def _save_response(context, path: str) -> None:
    _ensure_api(context)
    resp = context._api.response
    assert resp is not None, "No response to save"
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    value = {
        "status_code": resp.status_code,
        "headers": dict(resp.headers),
        "body": body,
    }
    object.__getattribute__(context, "_store")[path] = value
    allure.attach(
        json.dumps({"path": path, "value": value}, indent=2, default=str),
        "Saved Response",
        allure.attachment_type.JSON,
    )


@then(parsers.parse('I save the response in context'))
def save_response_default(context):
    with allure.step('Save response in context at "api_response"'):
        _save_response(context, "api_response")


@then(parsers.parse('I save the response in context at "{path}"'))
def save_response_at_path(context, path: str):
    with allure.step(f'Save response in context at "{path}"'):
        _save_response(context, path.replace("[", ".").replace("]", ""))


@then("I validate the response")
def validate_response_table(context, datatable):
    with allure.step("Validate response with expression table"):
        _ensure_api(context)
        store = object.__getattribute__(context, "_store")
        if "api_response" not in store or "body" not in store.get("api_response", {}):
            _save_response(context, "api_response")
            store = object.__getattribute__(context, "_store")
        results = []
        safe_globals = _build_validation_globals()
        for row in datatable:
            if len(row) < 2 or row[0].strip().lower() == "input":
                continue
            raw_inputs = [p.strip() for p in row[0].split(",")]
            expression = row[1].strip()

            resolved = []
            input_details = []
            for inp in raw_inputs:
                full_path = f"api_response.{inp}"
                try:
                    val = get_value(store, full_path)
                except (KeyError, IndexError, TypeError):
                    val = None
                resolved.append(val)
                input_details.append(f"{inp} -> {json.dumps(val, default=str)[:100]}")

            locals_dict = {}
            for i, val in enumerate(resolved):
                locals_dict[chr(97 + i)] = val

            passed = False
            error = None
            try:
                result = eval(expression, safe_globals, locals_dict)
                passed = bool(result)
            except Exception as e:
                error = str(e)

            row_result = {
                "inputs": input_details,
                "expression": expression,
                "variables": {chr(97 + i): resolved[i] for i in range(len(resolved))},
                "passed": passed,
                "error": error,
            }
            results.append(row_result)

            if not passed:
                msg = f"Validation failed: {expression} | inputs: {input_details}"
                if error:
                    msg += f" | error: {error}"
                raise AssertionError(msg)

        allure.attach(
            json.dumps(results, indent=2, default=str),
            "Response Validations",
            allure.attachment_type.JSON,
        )


# --- Validation keyword functions ---

_validation_llm: Any = None

def _get_validation_llm():
    global _validation_llm
    if _validation_llm is None:
        cfg = load_config()
        name = cfg.llm.default_provider
        prov_cfg = getattr(cfg.llm, name)
        _validation_llm = LLMRegistry.get(name, prov_cfg.model_dump())
    return _validation_llm


def _build_validation_globals() -> dict[str, Any]:
    globs: dict[str, Any] = {}
    allowed = {"int", "len", "str", "float", "bool", "list", "dict", "type", "isinstance", "range", "min", "max", "sum", "any", "all", "sorted", "reversed", "enumerate", "zip", "map", "filter", "abs", "round", "True", "False", "None"}
    for k in allowed:
        globs[k] = getattr(builtins, k)
    globs["re"] = re

    def regex(pattern: str, value: Any) -> bool:
        return bool(re.search(pattern, str(value)))
    globs["regex"] = regex

    def llm_binary(instruction: str, *values: Any) -> bool:
        prompt = build_llm_prompt(instruction, *values)
        resp = _get_validation_llm().generate(prompt, temperature=0)
        return resp.content.strip().upper() == "YES"
    globs["llm_binary"] = llm_binary

    def llm_score(instruction: str, *values: Any) -> float:
        prompt = build_llm_prompt(instruction, *values)
        resp = _get_validation_llm().generate(prompt, temperature=0)
        try:
            return float(resp.content.strip())
        except ValueError:
            return 0.0
    globs["llm_score"] = llm_score

    return globs


# --- Helpers ---


def _coerce_value(raw: str) -> Any:
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


def _parse_body_value(raw: str) -> Any:
    coerced = _coerce_value(raw)
    if coerced != raw:
        return coerced
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        pass
    return raw


def _attach_body(body: Any) -> None:
    if body is None:
        return
    try:
        allure.attach(
            json.dumps(body, indent=2, default=str),
            "Request Body",
            allure.attachment_type.JSON,
        )
    except (TypeError, ValueError):
        allure.attach(str(body), "Request Body", allure.attachment_type.TEXT)


def _attach_request(context) -> None:
    parts = {
        "url": context._api.url,
        "method": None,
        "headers": dict(context._api.headers),
    }
    if context._api.body is not None:
        parts["body"] = context._api.body
    allure.attach(
        json.dumps(parts, indent=2, default=str),
        "Request",
        allure.attachment_type.JSON,
    )


def _attach_response(response) -> None:
    if response is None:
        return
    try:
        body_preview = response.json()
    except Exception:
        body_preview = response.text[:5000]
    parts = {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body": body_preview,
    }
    allure.attach(
        json.dumps(parts, indent=2, default=str),
        "Response",
        allure.attachment_type.JSON,
    )
