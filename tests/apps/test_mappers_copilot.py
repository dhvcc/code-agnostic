from code_agnostic.apps.common.models import MCPServerDTO, MCPServerType
from code_agnostic.apps.copilot.mapper import CopilotMCPMapper


def test_copilot_mapper_from_common_stdio_and_http() -> None:
    mapper = CopilotMCPMapper()

    payload = mapper.from_common(
        {
            "local": MCPServerDTO(
                name="local",
                type=MCPServerType.STDIO,
                command="uvx",
                args=["tool"],
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
        "tools": ["*"],
        "type": "local",
        "command": "uvx",
        "args": ["tool"],
        "env": {"TOKEN": "${TOKEN}"},
        "timeout": 3000,
    }
    assert payload["remote"] == {
        "tools": ["*"],
        "type": "http",
        "url": "https://example.com/mcp",
        "headers": {"Authorization": "Bearer ${API_KEY}"},
        "timeout": 5000,
    }


def test_copilot_mapper_to_common_imports_supported_fields() -> None:
    mapper = CopilotMCPMapper()

    payload = mapper.to_common(
        {
            "local": {
                "type": "local",
                "command": "uvx",
                "args": ["tool"],
                "env": {"TOKEN": "${TOKEN}"},
                "timeout": 3000,
                "tools": ["*"],
            },
            "remote": {
                "type": "http",
                "url": "https://example.com/mcp",
                "headers": {"Authorization": "Bearer ${API_KEY}"},
                "timeout": 5000,
                "tools": ["*"],
            },
        }
    )

    assert payload["local"] == MCPServerDTO(
        name="local",
        type=MCPServerType.STDIO,
        command="uvx",
        args=["tool"],
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
