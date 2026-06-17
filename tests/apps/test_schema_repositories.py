import json

from code_agnostic.apps.codex.schema_repository import CodexSchemaRepository
from code_agnostic.apps.cursor.schema_repository import CursorSchemaRepository
from code_agnostic.apps.opencode.schema_repository import OpenCodeSchemaRepository


def _opencode_config_properties(schema: dict) -> dict:
    ref = schema.get("$ref")
    if ref == "#/$defs/Config":
        config = schema.get("$defs", {}).get("Config", {})
        properties = config.get("properties", {})
        return properties if isinstance(properties, dict) else {}
    properties = schema.get("properties", {})
    return properties if isinstance(properties, dict) else {}


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
    assert "mcp" in _opencode_config_properties(schema)
    experimental = _opencode_config_properties(schema)["experimental"]
    assert "policies" in experimental["properties"]


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


def test_codex_schema_repository_fallback_includes_current_feature_flags(
    monkeypatch,
) -> None:
    def _fail(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _fail)

    schema = CodexSchemaRepository(ttl_seconds=0).load_schema()
    global_features = schema["properties"]["features"]["properties"]
    profile_features = schema["definitions"]["ConfigProfile"]["properties"]["features"][
        "properties"
    ]
    for features in (global_features, profile_features):
        assert "code_mode" in features
        assert "local_thread_store_compression" in features
        assert "resize_all_images" in features
        assert "respect_system_proxy" in features
        assert "terminal_visualization_instructions" in features
        assert "token_budget" in features
        assert "sleep_tool" in features
        assert "responses_websocket_response_processed" not in features

    code_mode = global_features["code_mode"]
    assert code_mode == {"$ref": "#/definitions/FeatureToml_for_CodeModeConfigToml"}


def test_codex_schema_repository_fallback_allows_advertised_reasoning_efforts(
    monkeypatch,
) -> None:
    def _fail(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _fail)

    schema = CodexSchemaRepository(ttl_seconds=0).load_schema()
    reasoning_effort = schema["definitions"]["ReasoningEffort"]
    assert reasoning_effort["type"] == "string"
    assert reasoning_effort["minLength"] == 1
    assert "enum" not in reasoning_effort


def test_codex_schema_repository_fallback_includes_current_app_config(
    monkeypatch,
) -> None:
    def _fail(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _fail)

    schema = CodexSchemaRepository(ttl_seconds=0).load_schema()
    app_config = schema["definitions"]["AppConfig"]["properties"]
    assert "approvals_reviewer" in app_config


def test_codex_schema_repository_fallback_includes_realtime_webrtc_base_url(
    monkeypatch,
) -> None:
    def _fail(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _fail)

    schema = CodexSchemaRepository(ttl_seconds=0).load_schema()
    assert "experimental_realtime_webrtc_call_base_url" in schema["properties"]


def test_cursor_schema_repository_uses_local_only(monkeypatch) -> None:
    def _fail(*args, **kwargs):
        raise AssertionError("urlopen should not be called for local-only schema")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _fail)
    schema = CursorSchemaRepository(ttl_seconds=0).load_schema()
    assert schema.get("type") == "object"
    assert "mcpServers" in schema.get("properties", {})
    assert schema["$defs"]["localServer"]["properties"]["envFile"]["type"] == "string"


def test_remote_returns_invalid_json_falls_back_to_local(monkeypatch) -> None:
    def _bad_json(*args, **kwargs):
        return _Response("{not valid json")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _bad_json)

    schema = OpenCodeSchemaRepository(ttl_seconds=0).load_schema()
    assert "mcp" in _opencode_config_properties(schema)


def test_remote_returns_non_dict_falls_back_to_local(monkeypatch) -> None:
    def _non_dict(*args, **kwargs):
        return _Response(json.dumps(["not", "a", "dict"]))

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _non_dict)

    schema = OpenCodeSchemaRepository(ttl_seconds=0).load_schema()
    assert "mcp" in _opencode_config_properties(schema)


def test_opencode_schema_repository_fallback_matches_current_agent_and_permissions(
    monkeypatch,
) -> None:
    def _fail(*args, **kwargs):
        raise OSError("network down")

    monkeypatch.setattr("code_agnostic.apps.common.schema.urlopen", _fail)

    schema = OpenCodeSchemaRepository(ttl_seconds=0).load_schema()
    properties = _opencode_config_properties(schema)
    agent_properties = properties["agent"]["properties"]
    agent_config_properties = schema["$defs"]["AgentConfig"]["properties"]
    permission_properties = schema["$defs"]["PermissionConfig"]["anyOf"][1][
        "properties"
    ]
    mcp_local_properties = schema["$defs"]["McpLocalConfig"]["properties"]
    assert "scout" not in agent_properties
    assert agent_config_properties["variant"]["type"] == "string"
    assert mcp_local_properties["cwd"]["type"] == "string"
    assert "repo_clone" not in permission_properties
    assert "repo_overview" not in permission_properties


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
