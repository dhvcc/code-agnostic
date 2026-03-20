from code_agnostic.apps.common.models import MCPServerDTO, MCPServerType
from code_agnostic.apps.common.utils import dto_to_common_mcp


def test_dto_to_common_mcp_stdio_and_http() -> None:
    payload = dto_to_common_mcp(
        {
            "stdio": MCPServerDTO(
                name="stdio",
                type=MCPServerType.STDIO,
                command="uvx",
                args=["demo"],
                timeout_ms=900000,
                env={"TOKEN": "${TOKEN}"},
                headers={},
            ),
            "http": MCPServerDTO(
                name="http",
                type=MCPServerType.HTTP,
                url="https://example.com/mcp",
                headers={"Authorization": "Bearer token"},
                env={},
            ),
        }
    )

    assert payload["stdio"]["command"] == "uvx"
    assert payload["stdio"]["args"] == ["demo"]
    assert payload["stdio"]["timeout"] == 900000
    assert payload["http"]["url"] == "https://example.com/mcp"
