import json

from code_agnostic.apps.codex.schema_repository import CodexSchemaRepository
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
    def _fail(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _fail)

    schema = OpenCodeSchemaRepository(ttl_seconds=0).load_schema()
    assert schema.get("type") == "object"
    assert "mcp" in schema.get("properties", {})


def test_codex_schema_repository_prefers_remote(monkeypatch) -> None:
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
    def _fail(*args, **kwargs):
        raise AssertionError("urlopen should not be called for local-only schema")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _fail)
    schema = CursorSchemaRepository(ttl_seconds=0).load_schema()
    assert schema.get("type") == "object"
    assert "mcpServers" in schema.get("properties", {})


def test_remote_returns_invalid_json_falls_back_to_local(monkeypatch) -> None:
    def _bad_json(*args, **kwargs):
        return _Response("{not valid json")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _bad_json)

    schema = OpenCodeSchemaRepository(ttl_seconds=0).load_schema()
    assert schema.get("type") == "object"
    assert "mcp" in schema.get("properties", {})


def test_remote_returns_non_dict_falls_back_to_local(monkeypatch) -> None:
    def _non_dict(*args, **kwargs):
        return _Response(json.dumps(["not", "a", "dict"]))

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _non_dict)

    schema = OpenCodeSchemaRepository(ttl_seconds=0).load_schema()
    assert schema.get("type") == "object"
    assert "mcp" in schema.get("properties", {})


def test_cache_ttl_within_ttl_uses_cache(monkeypatch) -> None:
    call_count = 0
    remote_schema = {"type": "object", "properties": {"cached": {}}}

    def _counting(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _Response(json.dumps(remote_schema))

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _counting)

    repo = CodexSchemaRepository(ttl_seconds=3600)
    schema1 = repo.load_schema()
    schema2 = repo.load_schema()

    assert schema1 == remote_schema
    assert schema2 == remote_schema
    assert call_count == 1


def test_cache_ttl_expired_refetches(monkeypatch) -> None:
    import time as time_module

    import code_agnostic.apps.common.schema as schema_mod

    call_count = 0
    remote_schema = {"type": "object", "properties": {"fresh": {}}}

    def _counting(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return _Response(json.dumps(remote_schema))

    monkeypatch.setattr(schema_mod, "urlopen", _counting)

    current_time = time_module.time()
    fake_times = iter([current_time, current_time + 7200])

    original_time = time_module.time

    def _fake_time():
        return next(fake_times, original_time())

    monkeypatch.setattr(schema_mod.time, "time", _fake_time)

    repo = CodexSchemaRepository(ttl_seconds=3600)
    repo.load_schema()
    repo.load_schema()

    assert call_count == 2
