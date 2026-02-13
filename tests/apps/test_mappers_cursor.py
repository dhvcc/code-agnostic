from code_agnostic.apps.common.models import MCPAuthDTO, MCPServerDTO, MCPServerType
from code_agnostic.apps.cursor.mapper import CursorMCPMapper


def test_cursor_mapper_to_common_parses_oauth_and_stdio() -> None:
    mapper = CursorMCPMapper()
    mapped = mapper.to_common(
        {
            "local": {"command": "npx", "args": ["-y", "x"]},
            "oauth": {
                "url": "https://example.com/oauth",
                "auth": {
                    "CLIENT_ID": "id",
                    "CLIENT_SECRET": "secret",
                    "scopes": ["read"],
                },
            },
        }
    )

    assert mapped["local"] == MCPServerDTO(
        name="local", type=MCPServerType.STDIO, command="npx", args=["-y", "x"]
    )
    assert mapped["oauth"] == MCPServerDTO(
        name="oauth",
        type=MCPServerType.OAUTH,
        url="https://example.com/oauth",
        auth=MCPAuthDTO(client_id="id", client_secret="secret", scopes=["read"]),
    )


def test_cursor_mapper_from_common_writes_expected_keys() -> None:
    mapper = CursorMCPMapper()
    mapped = mapper.from_common(
        {
            "http": MCPServerDTO(
                name="http", type=MCPServerType.HTTP, url="https://example.com"
            ),
            "local": MCPServerDTO(
                name="local", type=MCPServerType.STDIO, command="uvx", args=["demo"]
            ),
        }
    )

    assert mapped["http"] == {"url": "https://example.com"}
    assert mapped["local"] == {"command": "uvx", "args": ["demo"]}


def test_cursor_mapper_from_common_empty_servers() -> None:
    mapper = CursorMCPMapper()
    mapped = mapper.from_common({})

    assert mapped == {}


def test_cursor_mapper_from_common_oauth_server() -> None:
    mapper = CursorMCPMapper()
    mapped = mapper.from_common(
        {
            "oauth": MCPServerDTO(
                name="oauth",
                type=MCPServerType.OAUTH,
                url="https://example.com/oauth",
                auth=MCPAuthDTO(
                    client_id="id", client_secret="secret", scopes=["read"]
                ),
            ),
        }
    )

    server = mapped["oauth"]
    assert server["url"] == "https://example.com/oauth"
    assert server["auth"]["CLIENT_ID"] == "id"
    assert server["auth"]["CLIENT_SECRET"] == "secret"
    assert server["auth"]["scopes"] == ["read"]


def test_cursor_mapper_from_common_with_headers_and_env() -> None:
    mapper = CursorMCPMapper()
    mapped = mapper.from_common(
        {
            "demo": MCPServerDTO(
                name="demo",
                type=MCPServerType.HTTP,
                url="https://example.com/mcp",
                headers={"X-Custom": "val"},
                env={"TOKEN": "secret"},
            ),
        }
    )

    server = mapped["demo"]
    assert server["headers"] == {"X-Custom": "val"}
    assert server["env"] == {"TOKEN": "secret"}


def test_cursor_mapper_roundtrip() -> None:
    mapper = CursorMCPMapper()
    original = {
        "local": MCPServerDTO(
            name="local", type=MCPServerType.STDIO, command="npx", args=["-y", "x"]
        ),
        "remote": MCPServerDTO(
            name="remote", type=MCPServerType.HTTP, url="https://example.com"
        ),
    }

    serialized = mapper.from_common(original)
    restored = mapper.to_common(serialized)

    assert restored["local"].command == "npx"
    assert restored["local"].args == ["-y", "x"]
    assert restored["remote"].url == "https://example.com"


def test_cursor_mapper_to_common_non_dict_skipped() -> None:
    mapper = CursorMCPMapper()
    mapped = mapper.to_common({"bad": "not-a-dict", "good": {"command": "npx"}})

    assert "bad" not in mapped
    assert "good" in mapped


def test_cursor_mapper_to_common_lowercase_auth_keys() -> None:
    mapper = CursorMCPMapper()
    mapped = mapper.to_common(
        {
            "oauth": {
                "url": "https://example.com/oauth",
                "auth": {
                    "client_id": "id",
                    "client_secret": "secret",
                },
            }
        }
    )

    assert mapped["oauth"].type == MCPServerType.OAUTH
    assert mapped["oauth"].auth is not None
    assert mapped["oauth"].auth.client_id == "id"


def test_cursor_mapper_to_common_env_and_headers() -> None:
    mapper = CursorMCPMapper()
    mapped = mapper.to_common(
        {
            "local": {
                "command": "npx",
                "env": {"TOKEN": "val"},
                "headers": {"X-Custom": "x"},
            }
        }
    )

    assert mapped["local"].env == {"TOKEN": "val"}
    assert mapped["local"].headers == {"X-Custom": "x"}
