import json
from pathlib import Path
from typing import Any
import httpx
import yaml


class SpecLoader:
    def __init__(
        self,
        specs_dir: str | Path = "tests/specs",
        app_name: str | None = None,
        test_type: str | None = None,
    ) -> None:
        self.specs_dir = Path(specs_dir).resolve()
        self.app_name = app_name
        self.test_type = test_type
        self._main_spec: dict[str, Any] | None = None

    def _inject_base_url(self, spec: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
        if "base_url" not in spec and "base_url" in raw:
            spec["base_url"] = raw["base_url"]
        return spec

    def load(self, name: str) -> dict[str, Any]:
        # 1. App + type: tests/specs/<app>/<type>.yaml → endpoints.<name> or top-level
        if self.app_name and self.test_type:
            path = self.specs_dir / self.app_name / f"{self.test_type}.yaml"
            if not path.exists():
                path = self.specs_dir / self.app_name / f"{self.test_type}.yml"
            if path.exists():
                raw = yaml.safe_load(path.read_text()) or {}
                endpoints = raw.get("endpoints", {})
                if name in endpoints:
                    return self._inject_base_url(endpoints[name], raw)
                if name in raw:
                    return self._inject_base_url(raw[name], raw)
                raise FileNotFoundError(f"Spec '{name}' not found in {path}")

        # 2. App-specific standalone: tests/specs/<app>/<name>.yaml
        if self.app_name:
            path = self.specs_dir / self.app_name / f"{name}.yaml"
            if not path.exists():
                path = self.specs_dir / self.app_name / f"{name}.yml"
            if path.exists():
                raw = yaml.safe_load(path.read_text()) or {}
                return self._inject_base_url(raw, raw)

        # 3. Root-level standalone
        path = self.specs_dir / f"{name}.yaml"
        if not path.exists():
            path = self.specs_dir / f"{name}.yml"
        if path.exists():
            with open(path) as f:
                raw = yaml.safe_load(f) or {}
                return self._inject_base_url(raw, raw)

        # 4. Root-level api_config.yaml → endpoints.<name>
        self._ensure_main_spec()
        if self._main_spec and name in self._main_spec:
            return self._main_spec[name]

        raise FileNotFoundError(f"Spec not found: {name} in {self.specs_dir}")

    def _ensure_main_spec(self) -> None:
        if self._main_spec is not None:
            return
        main_path = self.specs_dir / "api_config.yaml"
        if not main_path.exists():
            main_path = self.specs_dir / "api_config.yml"
        if main_path.exists():
            with open(main_path) as f:
                raw = yaml.safe_load(f) or {}
            self._main_spec = raw.get("endpoints", {})

    def _find_file(self, base: Path, name: str) -> Path | None:
        if Path(name).suffix:
            p = base / name
            return p if p.exists() else None
        for ext in [".json", ".yaml", ".yml"]:
            p = base / f"{name}{ext}"
            if p.exists():
                return p
        return None

    def _read_file(self, p: Path) -> dict[str, Any]:
        ext = p.suffix.lower()
        with open(p) as f:
            if ext == ".json":
                return json.load(f)
            return yaml.safe_load(f)

    def resolve_body(self, spec: dict[str, Any], variant: str = "default") -> dict[str, Any]:
        body_dir = spec.get("body_dir")
        if body_dir:
            bases = [Path(body_dir).expanduser()]
            if not bases[0].is_absolute():
                bases.insert(0, Path("tests") / body_dir)
            for base in bases:
                found = self._find_file(base, variant)
                if found:
                    return self._read_file(found)
                fallback = self._find_file(base, "default")
                if fallback:
                    return self._read_file(fallback)
            raise FileNotFoundError(f"No body file for variant '{variant}' in {body_dir}")

        body = spec.get("body")
        if isinstance(body, str):
            return self._load_body_file(body)
        if isinstance(body, dict):
            body_path = body.get(variant) or body.get("default")
            if body_path:
                return self._load_body_file(body_path)
            raise KeyError(f"Variant '{variant}' not found in spec body map")
        return {}

    def _load_body_file(self, path: str | Path) -> dict[str, Any]:
        p = Path(path)
        if p.suffix:
            if p.exists():
                return self._read_file(p)
            for fallback in [Path("tests") / path, Path("tests/data") / path]:
                if fallback.exists():
                    return self._read_file(fallback)
        else:
            for base in [Path(), Path("tests"), Path("tests/data")]:
                candidate = self._find_file(base, path)
                if candidate:
                    return self._read_file(candidate)
        raise FileNotFoundError(f"Body file not found: {path}")


class ApiClient:
    def __init__(self) -> None:
        self.base_url: str = ""
        self.url: str = ""
        self.headers: dict[str, str] = {}
        self.body: Any = None
        self.response: httpx.Response | None = None

    def set_base_url(self, url: str) -> None:
        self.base_url = url.rstrip("/")
        self.url = self.base_url

    def append_path(self, path: str) -> None:
        path = path.strip()
        if path.startswith("/"):
            self.url = self.base_url + path
        else:
            self.url = self.base_url + "/" + path

    def append_query(self, params: dict[str, str] | str) -> None:
        separator = "&" if "?" in self.url else "?"
        if isinstance(params, dict):
            query_string = "&".join(f"{k}={v}" for k, v in params.items())
        else:
            query_string = params.lstrip("?")
        self.url = f"{self.url}{separator}{query_string}"

    def set_body_from_file(self, file_path: str | Path) -> None:
        loader = SpecLoader()
        self.body = loader._load_body_file(str(file_path))

    def set_body(self, body: Any) -> None:
        self.body = body

    def set_body_from_spec(self, spec_name: str, variant: str = "default", **loader_kw: Any) -> None:
        loader = SpecLoader(**loader_kw)
        spec = loader.load(spec_name)
        if "base_url" in spec:
            self.set_base_url(spec["base_url"])
        self.body = loader.resolve_body(spec, variant)
        if "method" in spec and "path" in spec:
            self.append_path(spec["path"])

    def hit(self, method: str) -> httpx.Response:
        client = httpx.Client(headers=self.headers, timeout=30)
        method = method.upper()
        if method == "GET":
            self.response = client.get(self.url)
        elif method == "POST":
            self.response = client.post(self.url, json=self.body)
        elif method == "PUT":
            self.response = client.put(self.url, json=self.body)
        elif method == "PATCH":
            self.response = client.patch(self.url, json=self.body)
        elif method == "DELETE":
            self.response = client.delete(self.url)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        return self.response

    def validate_status(self, expected: int) -> None:
        assert self.response is not None, "No response to validate"
        actual = self.response.status_code
        assert actual == expected, f"Expected status {expected}, got {actual}"
