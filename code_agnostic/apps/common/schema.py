import json
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from code_agnostic.apps.common.interfaces.repositories import ISchemaRepository

_SCHEMA_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


class JsonSchemaRepository(ISchemaRepository):
    def __init__(
        self,
        *,
        local_schema_path: Path,
        remote_schema_url: str | None,
        ttl_seconds: int = 3600,
    ) -> None:
        self.local_schema_path = local_schema_path
        self.remote_schema_url = remote_schema_url
        self.ttl_seconds = ttl_seconds

    def load_schema(self) -> dict[str, Any]:
        if self.remote_schema_url:
            remote = self._load_remote_with_cache(self.remote_schema_url)
            if remote is not None:
                return remote
        return self._load_local_with_cache(self.local_schema_path)

    def _load_remote_with_cache(self, url: str) -> dict[str, Any] | None:
        cached = _SCHEMA_CACHE.get(url)
        now = time.time()
        if cached and now - cached[0] < self.ttl_seconds:
            return cached[1]
        try:
            request = Request(url, headers={"User-Agent": "code-agnostic"})
            with urlopen(request, timeout=20) as response:
                payload = response.read().decode("utf-8")
            schema = json.loads(payload)
            if isinstance(schema, dict):
                _SCHEMA_CACHE[url] = (now, schema)
                return schema
        except Exception:
            return None
        return None

    def _load_local_with_cache(self, path: Path) -> dict[str, Any]:
        key = str(path.resolve())
        cached = _SCHEMA_CACHE.get(key)
        now = time.time()
        if cached and now - cached[0] < self.ttl_seconds:
            return cached[1]
        schema = json.loads(path.read_text(encoding="utf-8"))
        _SCHEMA_CACHE[key] = (now, schema)
        return schema
