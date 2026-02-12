from llm_sync.mappers.opencode import map_mcp_servers_to_opencode


def test_map_mcp_servers_to_opencode_normalizes_remote_and_local() -> None:
    mapped = map_mcp_servers_to_opencode(
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
