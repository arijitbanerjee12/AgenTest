# API Test Case Creation Workflow

## Overview

This workflow guides the agent in creating API test cases for any application using the AgenTest framework. The agent receives inputs like curl commands, API responses, contracts, or a repo URL, and produces a structured test suite.

---

## 1. Input Processing

### 1.1 From curl commands
Parse the curl to extract:
- **Method**: `-X POST` or the HTTP verb (default GET)
- **URL**: The full URL, split into base + path
- **Headers**: Everything after `-H`
- **Body**: Everything after `-d` or `--data` (JSON)
- **Query params**: URL `?key=value` pairs

### 1.2 From API responses
Capture response JSON to generate:
- **Response schema** → `tests/schemas/<app>/<endpoint>_response.json`
- **Assertion patterns** → contract validation steps in the feature file

### 1.3 From contracts / OpenAPI specs
Parse contract (OpenAPI 3.x, RAML, etc.) to extract:
- Endpoints, methods, request bodies, response schemas
- Required vs optional fields (for validation test cases)
- Status codes

### 1.4 From a repo URL
Clone or inspect the repo to understand:
- The application architecture (routes, controllers, models)
- Existing API endpoints from route definitions
- Data models / schemas from the codebase
- This helps create context-aware test cases

---

## 2. Directory Structure (created per application)

```
tests/
├── features/
│   └── <app_name>/                  ← feature files (Gherkin)
│       └── <endpoint>_test.feature
├── specs/
│   └── <app_name>/
│       ├── api.yaml                 ← endpoint definitions (MANDATORY)
│       ├── schemas.yaml             ← response validation schemas (optional)
│       └── contracts.yaml           ← contract assertions (optional)
├── data/
│   └── <app_name>/
│       └── <endpoint>/              ← body variant JSON/YAML files
│           ├── default.json         ← default body (MANDATORY)
│           ├── minimal.json         ← required fields only
│           ├── full.json            ← all fields
│           ├── invalid.json         ← invalid data for negative tests
│           └── edge_cases.json      ← boundary values
├── schemas/
│   └── <app_name>/
│       └── <endpoint>_response.json ← expected response structure
├── step_defs/                       ← custom step definitions (optional)
│   └── <app_name>_steps.py
└── temp/
    └── reports/                     ← Allure + Cucumber JSON reports
```

---

## 3. Files to Create

### 3.1 Endpoint Spec: `tests/specs/<app_name>/api.yaml` (MANDATORY)

```yaml
endpoints:
  <endpoint_name>:
    method: POST               # GET | POST | PUT | PATCH | DELETE
    path: /api/v1/resource     # relative path appended to base url
    body_dir: tests/data/<app_name>/<endpoint_name>   # (optional) body variants directory
    headers:                   # (optional) default headers
      Content-Type: application/json
    query_params:              # (optional) default query params
      api_key: test
```

> If `body_dir` is not set, the `body` field can be used instead:
> ```yaml
>   body: tests/data/<app_name>/<endpoint_name>/default.json
> ```
> Or with variant map:
> ```yaml
>   body:
>     default: tests/data/<app_name>/<endpoint_name>/default.json
>     invalid: tests/data/<app_name>/<endpoint_name>/invalid.json
> ```

### 3.2 Body Data Files: `tests/data/<app_name>/<endpoint_name>/` (MANDATORY for mutating methods)

Each file is a JSON or YAML body. Supported extensions: `.json` (default), `.yaml`, `.yml`.

**`default.json`** — the standard request body:
```json
{
  "title": "foo",
  "body": "bar",
  "userId": 1
}
```

**`minimal.json`** — required fields only (for validation):
```json
{
  "title": "minimal"
}
```

**`invalid.json`** — intentionally wrong data for negative tests:
```json
{
  "title": "",
  "userId": "not-a-number"
}
```

### 3.3 Feature File: `tests/features/<app_name>/<endpoint>_test.feature` (MANDATORY)

```gherkin
Feature: <App Name> - <Endpoint Name> API Tests

  Background:
    Given I am testing application "<app_name>" for "api"
    And I set the base url to "<base_url>"
    And I set the headers
      | name         | value            |
      | Content-Type | application/json |

  # --- Positive Tests ---

  Scenario: Create a <resource> with default data
    Given I set the api body from spec "<endpoint_name>"
    When I hit the POST api
    Then the status code should be 201
    And the response should contain valid <resource> data

  Scenario: Create a <resource> with custom variant
    Given I set the api body from spec "<endpoint_name>" variant "custom"
    When I hit the POST api
    Then the status code should be 201

  # --- Negative Tests ---

  Scenario: Create a <resource> with invalid data
    Given I set the api body from spec "<endpoint_name>" variant "invalid"
    When I hit the POST api
    Then the status code should be 400

  # --- Body Override Tests ---

  Scenario: Override specific fields before hitting
    Given I set the api body from spec "<endpoint_name>"
    And I update the api body at "title" to "overridden"
    And I update the api body at "userId" to "99"
    When I hit the POST api
    Then the status code should be 201

  Scenario: Override nested fields
    Given I set the api body
      | path       | value          |
      | user.name  | John           |
      | user.age   | 30             |
      | tags       | ["a","b"]      |
    And I update the api body at "user.address.city" to "NYC"
    When I hit the POST api
    Then the status code should be 201

  # --- GET Tests ---

  Scenario: Fetch resource by ID
    Given I append "/api/v1/resource/1" to the base url
    When I hit the GET api
    Then the status code should be 200

  # --- Query Param Tests ---

  Scenario: Filter resources
    Given I append "/api/v1/resource" to the base url
    And I add query param "status" to "active"
    And I add query param "page" to "1"
    When I hit the GET api
    Then the status code should be 200

  # --- Header Override Tests ---

  Scenario: Send with custom header
    Given I set the headers
      | name         | value            |
      | Authorization| Bearer test-token |
    And I set the api body from spec "<endpoint_name>" variant "default"
    When I hit the POST api
    Then the status code should be 201

  # --- Scenario Outline (data-driven) ---

  Scenario Outline: Create <resource> with different variants
    Given I set the api body from spec "<endpoint_name>" variant "<variant>"
    When I hit the POST api
    Then the status code should be <status>

    Examples:
      | variant   | status |
      | default   | 201    |
      | minimal   | 201    |
      | invalid   | 400    |
```

### 3.4 Schema File: `tests/schemas/<app_name>/<endpoint>_response.json` (optional)

Used for response validation via custom steps:
```json
{
  "type": "object",
  "required": ["id", "title", "body", "userId"],
  "properties": {
    "id": {"type": "integer"},
    "title": {"type": "string"},
    "body": {"type": "string"},
    "userId": {"type": "integer"}
  }
}
```

---

## 4. Available Steps Reference

### Context Steps
| Step | Description |
|---|---|
| `Given I am testing application "{app}" for "{type}"` | Sets app context for spec loading |
| `Given I save "{value}" in context at "{path}"` | Saves value in context (dot notation) |
| `Then the context at "{path}" should be "{expected}"` | Asserts context value |

### API Steps
| Step | Description |
|---|---|
| `Given I set the base url to "{url}"` | Initializes API client and sets base URL |
| `Given I append "{path}" to the base url` | Appends path to the base URL |
| `Given I add query param "{key}" to "{value}"` | Adds query parameter to the URL |
| `Given I set the headers` | Sets multiple headers via Gherkin table |
| `Given I set header "{name}" to "{value}"` | Sets a single header |
| `Given I set the api body from spec "{name}"` | Loads body from endpoint spec (default variant) |
| `Given I set the api body from spec "{name}" variant "{variant}"` | Loads body with a specific variant |
| `Given I set the api body from file "{path}"` | Loads body directly from a file |
| `Given I set the api body` | Sets body inline via Gherkin table (flat keys only) |
| `Given I update the api body at "{path}" to "{value}"` | Updates a nested field in the loaded body |
| `Given I update the api body` | Updates multiple fields via table (path/value columns) |
| `When I hit the {method} api` | Sends the HTTP request |
| `Then the status code should be {code}` | Validates response status code |

### Path Syntax for body updates
- Simple: `title`, `userId`
- Nested: `user.name`, `user.address.city`
- List by index (dot): `items.0.name`, `tags.1`
- List by index (bracket): `items[0].name`, `tags[1]`
- Deeply nested: `users.0.addresses.1.city`

### Value coercion in tables
| Feature file value | Coerced type |
|---|---|
| `"true"` / `"false"` | boolean |
| `"null"` | None |
| `"42"` | int |
| `"3.14"` | float |
| `"[1,2,3]"` | list (JSON parsed) |
| `"{\"key\":\"val\"}"` | dict (JSON parsed) |
| everything else | string |

---

## 5. Workflow Steps (Agent Execution Order)

### Step 1: Understand the Input
- If a **curl command** is given → parse to extract method, URL, headers, body
- If an **OpenAPI spec** is given → extract all endpoints, schemas
- If a **repo URL** is given → clone and analyze routes, models, controllers
- If **manual input** is given → map fields to the framework structure

### Step 2: Create Application Directory Structure
```
tests/specs/<app_name>/api.yaml
tests/data/<app_name>/<endpoint>/
tests/features/<app_name>/
```

### Step 3: Create Body Variant Files
For each endpoint that accepts a body:
1. **`default.json`** — the standard body from the curl/contract
2. **`minimal.json`** — only required fields
3. **`invalid.json`** — bad data for 4xx tests
4. **`edge_cases.json`** — large values, special chars (optional)

### Step 4: Create Endpoint Spec (`api.yaml`)
Define every endpoint under `endpoints:` with method, path, body_dir.

### Step 5: Create Feature File
Write Gherkin scenarios covering:
- Happy path (default data → 2xx)
- Variants (custom data → 2xx)
- Negative path (invalid data → 4xx)
- Field overrides (update body at path → 2xx)
- GET queries with params
- Header variations

### Step 6: Create Schema Files (optional)
For response contract validation.

### Step 7: Create Custom Step Definitions (optional)
In `tests/step_defs/` for app-specific assertions (e.g., response field validation).

### Step 8: Verify
```bash
cd <project_root>
uv run pytest tests/test_runner.py -v
```

---

## 6. Mandatory vs Optional Files

| File | Required | Purpose |
|---|---|---|
| `tests/specs/<app>/api.yaml` | **YES** | Endpoint definitions (method, path, body) |
| `tests/data/<app>/<ep>/default.json` | **YES** | Default request body |
| `tests/features/<app>/<ep>_test.feature` | **YES** | Gherkin scenarios |
| `tests/data/<app>/<ep>/minimal.json` | No | Minimal fields test |
| `tests/data/<app>/<ep>/invalid.json` | No | Negative testing |
| `tests/data/<app>/<ep>/custom.json` | No | Custom variant |
| `tests/schemas/<app>/` | No | Response validation |
| `tests/step_defs/` | No | Custom assertions |

> **Note:** `api.yaml` and at least one body data file + one feature file are the minimum to run a test.

---

## 7. Example: Full Flow from a Curl

**Input curl:**
```bash
curl -X POST https://jsonplaceholder.typicode.com/posts \
  -H "Content-Type: application/json" \
  -d '{"title":"foo","body":"bar","userId":1}'
```

**Agent creates:**

1. `tests/specs/myapp/api.yaml` → endpoint `create_post` with `body_dir: tests/data/myapp/create_post`
2. `tests/data/myapp/create_post/default.json` → `{"title":"foo","body":"bar","userId":1}`
3. `tests/data/myapp/create_post/minimal.json` → `{"title":"minimal"}`
4. `tests/data/myapp/create_post/invalid.json` → `{"title":"","userId":"bad"}`
5. `tests/features/myapp/create_post_test.feature` → Background + 5 scenarios (default, minimal, invalid, override, Scenario Outline)

**Feature file generated:**
```gherkin
Feature: MyApp - Create Post API Tests

  Background:
    Given I am testing application "myapp" for "api"
    And I set the base url to "https://jsonplaceholder.typicode.com"
    And I set the headers
      | name         | value            |
      | Content-Type | application/json |

  Scenario Outline: Create post with different variants
    Given I set the api body from spec "create_post" variant "<variant>"
    When I hit the POST api
    Then the status code should be <status>

    Examples:
      | variant | status |
      | default | 201    |
      | minimal | 201    |
      | invalid | 400    |

  Scenario: Override specific fields
    Given I set the api body from spec "create_post"
    And I update the api body at "title" to "custom title"
    When I hit the POST api
    Then the status code should be 201
```
