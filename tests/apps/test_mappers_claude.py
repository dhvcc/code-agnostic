from code_agnostic.apps.claude.mapper import ClaudeMCPMapper
from code_agnostic.apps.common.models import MCPServerDTO, MCPServerType


def test_claude_mapper_from_common_stdio_and_http() -> None:
    mapper = ClaudeMCPMapper()

    payload = mapper.from_common(
        {
            "local": MCPServerDTO(
                name="local",
                type=MCPServerType.STDIO,
                command="uvx",
                args=["tool"],
                cwd="/tmp/project",
                env_file=".env",
                env={"TOKEN": "${TOKEN}"},
                timeout_ms=3000,
            ),
            "remote": MCPServerDTO(
                name="remote",
                type=MCPServerType.HTTP,
                url="https://example.com/mcp",
                headers={"Authorization": "Bearer ${API_KEY}"},
                timeout_ms=5000,
            ),
        }
    )

    assert payload["local"] == {
        "type": "stdio",
        "command": "uvx",
        "args": ["tool"],
        "cwd": "/tmp/project",
        "env": {"TOKEN": "${TOKEN}"},
        "timeout": 3000,
    }
    assert payload["remote"] == {
        "type": "http",
        "url": "https://example.com/mcp",
        "headers": {"Authorization": "Bearer ${API_KEY}"},
        "timeout": 5000,
    }


def test_claude_mapper_to_common() -> None:
    mapper = ClaudeMCPMapper()

    payload = mapper.to_common(
        {
            "local": {
                "type": "stdio",
                "command": "uvx",
                "args": ["tool"],
                "cwd": "/tmp/project",
                "env": {"TOKEN": "${TOKEN}"},
                "timeout": 3000,
            },
            "remote": {
                "type": "streamable-http",
                "url": "https://example.com/mcp",
                "headers": {"Authorization": "Bearer ${API_KEY}"},
                "timeout": 5000,
            },
        }
    )

    assert payload["local"] == MCPServerDTO(
        name="local",
        type=MCPServerType.STDIO,
        command="uvx",
        args=["tool"],
        cwd="/tmp/project",
        env={"TOKEN": "${TOKEN}"},
        timeout_ms=3000,
    )
    assert payload["remote"] == MCPServerDTO(
        name="remote",
        type=MCPServerType.HTTP,
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer ${API_KEY}"},
        timeout_ms=5000,
    )
