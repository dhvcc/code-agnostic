from code_agnostic.apps.sync.apps.codex.mapper import CodexMCPMapper
from code_agnostic.apps.sync.models import MCPServerDTO, MCPServerType


def test_codex_mapper_to_common_parses_env_and_headers() -> None:
    mapper = CodexMCPMapper()
    mapped = mapper.to_common(
        {
            "sentry": {
                "url": "https://example.com/mcp",
                "env_vars": ["API_KEY"],
                "http_headers": {"X-Api-Version": "1"},
                "env_http_headers": {"Authorization": "TOKEN"},
            }
        }
    )

    server = mapped["sentry"]
    assert server.type == MCPServerType.HTTP
    assert server.env == {"API_KEY": "${API_KEY}"}
    assert server.headers["X-Api-Version"] == "1"
    assert server.headers["Authorization"] == "${TOKEN}"


def test_codex_mapper_from_common_splits_env_and_headers() -> None:
    mapper = CodexMCPMapper()
    mapped = mapper.from_common(
        {
            "demo": MCPServerDTO(
                name="demo",
                type=MCPServerType.HTTP,
                url="https://example.com/mcp",
                env={"API_KEY": "${API_KEY}", "PLAIN": "value"},
                headers={
                    "Authorization": "Bearer ${TOKEN}",
                    "X-Test": "${HEADER_ENV}",
                    "X-Static": "x",
                },
            )
        }
    )

    server = mapped["demo"]
    assert server["url"] == "https://example.com/mcp"
    assert server["env_vars"] == ["API_KEY"]
    assert server["env"] == {"PLAIN": "value"}
    assert server["bearer_token_env_var"] == "TOKEN"
    assert server["env_http_headers"] == {"X-Test": "HEADER_ENV"}
    assert server["http_headers"] == {"X-Static": "x"}
