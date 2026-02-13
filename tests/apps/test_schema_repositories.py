import json

from code_agnostic.apps.codex.schema_repository import CodexSchemaRepository
from code_agnostic.apps.common.schema import _SCHEMA_CACHE
from code_agnostic.apps.cursor.schema_repository import CursorSchemaRepository
from code_agnostic.apps.opencode.schema_repository import OpenCodeSchemaRepository


class _Response:
    def __init__(self, payload: str) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def read(self) -> bytes:
        return self._payload.encode("utf-8")


def test_opencode_schema_repository_fallbacks_to_local(monkeypatch) -> None:
    _SCHEMA_CACHE.clear()

    def _fail(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _fail)

    schema = OpenCodeSchemaRepository(ttl_seconds=0).load_schema()
    assert schema.get("type") == "object"
    assert "mcp" in schema.get("properties", {})


def test_codex_schema_repository_prefers_remote(monkeypatch) -> None:
    _SCHEMA_CACHE.clear()
    remote_schema = {
        "type": "object",
        "properties": {"mcp_servers": {"type": "object"}},
    }

    def _ok(*args, **kwargs):
        return _Response(json.dumps(remote_schema))

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _ok)

    schema = CodexSchemaRepository(ttl_seconds=0).load_schema()
    assert schema == remote_schema


def test_cursor_schema_repository_uses_local_only(monkeypatch) -> None:
    _SCHEMA_CACHE.clear()

    def _fail(*args, **kwargs):
        raise AssertionError("urlopen should not be called for local-only schema")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _fail)
    schema = CursorSchemaRepository(ttl_seconds=0).load_schema()
    assert schema.get("type") == "object"
    assert "mcpServers" in schema.get("properties", {})
