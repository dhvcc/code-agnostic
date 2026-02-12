from pathlib import Path

from code_agnostic.constants import AGENTS_FILENAME
from code_agnostic.mappers.base import IConfigMapper
from code_agnostic.mappers.opencode import OpenCodeMapper


class NativeMapper(IConfigMapper):
    pass


def test_map_mcp_servers_to_opencode_normalizes_remote_and_local() -> None:
    mapped = OpenCodeMapper().map_mcp_servers(
        {
            "remote_server": {
                "url": "https://example.com/mcp",
                "enabled": True,
                "headers": {"Authorization": "Bearer token"},
            },
            "local_server": {
                "command": "npx",
                "args": ["-y", "demo-mcp"],
                "environment": {"FOO": "bar"},
            },
            "invalid_server": {
                "foo": "bar",
            },
        }
    )

    assert mapped["remote_server"] == {
        "type": "remote",
        "url": "https://example.com/mcp",
        "enabled": True,
        "headers": {"Authorization": "Bearer token"},
    }
    assert mapped["local_server"] == {
        "type": "local",
        "command": ["npx", "-y", "demo-mcp"],
        "environment": {"FOO": "bar"},
    }
    assert "invalid_server" not in mapped


def test_base_mapper_defaults_to_native_passthrough(tmp_path: Path) -> None:
    mapper = NativeMapper()
    source = tmp_path / AGENTS_FILENAME
    source.write_text("rules", encoding="utf-8")

    assert mapper.map_mcp_servers({"a": {"url": "https://example.com"}}) == {"a": {"url": "https://example.com"}}
    assert mapper.map_skill_source(source) == source
    assert mapper.map_agent_source(source) == source
    assert mapper.map_workspace_rules_source(source) == source
