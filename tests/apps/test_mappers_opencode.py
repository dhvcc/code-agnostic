from code_agnostic.apps.common.models import MCPAuthDTO, MCPServerDTO, MCPServerType
from code_agnostic.apps.opencode.mapper import OpenCodeMCPMapper


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


def test_opencode_mapper_from_common_empty_servers() -> None:
    mapper = OpenCodeMCPMapper()
    mapped = mapper.from_common({})

    assert mapped == {}


def test_opencode_mapper_from_common_with_env() -> None:
    mapper = OpenCodeMCPMapper()
    mapped = mapper.from_common(
        {
            "local": MCPServerDTO(
                name="local",
                type=MCPServerType.STDIO,
                command="npx",
                env={"TOKEN": "secret"},
            ),
        }
    )

    assert mapped["local"]["environment"] == {"TOKEN": "secret"}


def test_opencode_mapper_from_common_with_headers() -> None:
    mapper = OpenCodeMCPMapper()
    mapped = mapper.from_common(
        {
            "remote": MCPServerDTO(
                name="remote",
                type=MCPServerType.HTTP,
                url="https://example.com/mcp",
                headers={"Authorization": "Bearer token"},
            ),
        }
    )

    assert mapped["remote"]["headers"] == {"Authorization": "Bearer token"}


def test_opencode_mapper_to_common_single_element_command() -> None:
    mapper = OpenCodeMCPMapper()
    mapped = mapper.to_common({"tool": {"type": "local", "command": ["python"]}})

    assert mapped["tool"].command == "python"
    assert mapped["tool"].args == []


def test_opencode_mapper_to_common_empty_command_skipped() -> None:
    mapper = OpenCodeMCPMapper()
    mapped = mapper.to_common({"tool": {"type": "local", "command": []}})

    assert "tool" not in mapped


def test_opencode_mapper_to_common_non_dict_server_skipped() -> None:
    mapper = OpenCodeMCPMapper()
    mapped = mapper.to_common(
        {"bad": "not-a-dict", "good": {"type": "remote", "url": "https://x"}}
    )

    assert "bad" not in mapped
    assert "good" in mapped


def test_opencode_mapper_to_common_server_missing_type_with_command() -> None:
    mapper = OpenCodeMCPMapper()
    mapped = mapper.to_common({"tool": {"command": ["npx", "-y", "demo"]}})

    assert "tool" in mapped
    assert mapped["tool"].type == MCPServerType.STDIO


def test_opencode_mapper_to_common_with_environment() -> None:
    mapper = OpenCodeMCPMapper()
    mapped = mapper.to_common(
        {
            "tool": {
                "type": "local",
                "command": ["npx"],
                "environment": {"TOKEN": "val"},
            }
        }
    )

    assert mapped["tool"].env == {"TOKEN": "val"}


def test_opencode_mapper_to_common_with_headers() -> None:
    mapper = OpenCodeMCPMapper()
    mapped = mapper.to_common(
        {
            "remote": {
                "type": "remote",
                "url": "https://x",
                "headers": {"X-Custom": "value"},
            }
        }
    )

    assert mapped["remote"].headers == {"X-Custom": "value"}
