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
