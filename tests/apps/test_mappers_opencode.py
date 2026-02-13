from code_agnostic.apps.sync.models import MCPAuthDTO, MCPServerDTO, MCPServerType
from code_agnostic.apps.sync.opencode import OpenCodeMCPMapper


def test_opencode_mapper_from_common() -> None:
    mapper = OpenCodeMCPMapper()
    mapped = mapper.from_common(
        {
            "local": MCPServerDTO(
                name="local",
                type=MCPServerType.STDIO,
                command="npx",
                args=["-y", "demo"],
            ),
            "remote": MCPServerDTO(
                name="remote", type=MCPServerType.HTTP, url="https://example.com/mcp"
            ),
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

    assert mapped["local"] == {"type": "local", "command": ["npx", "-y", "demo"]}
    assert mapped["remote"] == {"type": "remote", "url": "https://example.com/mcp"}
    assert mapped["oauth"] == {
        "type": "remote",
        "url": "https://example.com/oauth",
        "oauth": {"clientId": "id", "clientSecret": "secret", "scope": "read"},
    }


def test_opencode_mapper_to_common() -> None:
    mapper = OpenCodeMCPMapper()
    mapped = mapper.to_common(
        {
            "stdio": {"type": "local", "command": ["python", "-m", "server"]},
            "http": {"type": "remote", "url": "https://example.com/http"},
            "oauth": {
                "type": "remote",
                "url": "https://example.com/oauth",
                "oauth": {
                    "clientId": "cid",
                    "clientSecret": "csecret",
                    "scope": "read",
                },
            },
        }
    )

    assert mapped["stdio"] == MCPServerDTO(
        name="stdio",
        type=MCPServerType.STDIO,
        command="python",
        args=["-m", "server"],
    )
    assert mapped["http"].type == MCPServerType.HTTP
    assert mapped["oauth"].type == MCPServerType.OAUTH
    assert mapped["oauth"].auth == MCPAuthDTO(
        client_id="cid", client_secret="csecret", scopes=["read"]
    )
