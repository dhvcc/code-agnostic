from code_agnostic.apps.codex.mapper import CodexMCPMapper
from code_agnostic.apps.common.models import MCPServerDTO, MCPServerType


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


def test_codex_mapper_from_common_empty_servers() -> None:
    mapper = CodexMCPMapper()
    mapped = mapper.from_common({})

    assert mapped == {}


def test_codex_mapper_from_common_stdio_server() -> None:
    mapper = CodexMCPMapper()
    mapped = mapper.from_common(
        {
            "local": MCPServerDTO(
                name="local",
                type=MCPServerType.STDIO,
                command="uvx",
                args=["demo"],
            ),
        }
    )

    server = mapped["local"]
    assert server["command"] == "uvx"
    assert server["args"] == ["demo"]
    assert "url" not in server


def test_codex_mapper_from_common_bearer_token_pattern() -> None:
    mapper = CodexMCPMapper()
    mapped = mapper.from_common(
        {
            "remote": MCPServerDTO(
                name="remote",
                type=MCPServerType.HTTP,
                url="https://example.com/mcp",
                headers={"Authorization": "Bearer ${API_TOKEN}"},
            ),
        }
    )

    assert mapped["remote"]["bearer_token_env_var"] == "API_TOKEN"


def test_codex_mapper_from_common_non_bearer_auth_header() -> None:
    mapper = CodexMCPMapper()
    mapped = mapper.from_common(
        {
            "remote": MCPServerDTO(
                name="remote",
                type=MCPServerType.HTTP,
                url="https://example.com/mcp",
                headers={"Authorization": "Basic abc123"},
            ),
        }
    )

    server = mapped["remote"]
    assert "bearer_token_env_var" not in server
    assert server["http_headers"] == {"Authorization": "Basic abc123"}


def test_codex_mapper_to_common_bearer_token_env_var() -> None:
    mapper = CodexMCPMapper()
    mapped = mapper.to_common(
        {
            "remote": {
                "url": "https://example.com/mcp",
                "bearer_token_env_var": "MY_TOKEN",
            }
        }
    )

    server = mapped["remote"]
    assert server.headers["Authorization"] == "Bearer ${MY_TOKEN}"


def test_codex_mapper_to_common_stdio_server() -> None:
    mapper = CodexMCPMapper()
    mapped = mapper.to_common(
        {
            "local": {
                "command": "npx",
                "args": ["-y", "demo"],
            }
        }
    )

    server = mapped["local"]
    assert server.type == MCPServerType.STDIO
    assert server.command == "npx"
    assert server.args == ["-y", "demo"]


def test_codex_mapper_to_common_non_dict_skipped() -> None:
    mapper = CodexMCPMapper()
    mapped = mapper.to_common({"bad": "not-a-dict", "good": {"url": "https://x"}})

    assert "bad" not in mapped
    assert "good" in mapped


def test_codex_mapper_to_common_env_vars_list() -> None:
    mapper = CodexMCPMapper()
    mapped = mapper.to_common(
        {
            "demo": {
                "url": "https://x",
                "env_vars": ["API_KEY", "SECRET"],
            }
        }
    )

    server = mapped["demo"]
    assert server.env["API_KEY"] == "${API_KEY}"
    assert server.env["SECRET"] == "${SECRET}"


def test_codex_mapper_to_common_env_table() -> None:
    mapper = CodexMCPMapper()
    mapped = mapper.to_common(
        {
            "demo": {
                "url": "https://x",
                "env": {"KEY": "value"},
            }
        }
    )

    server = mapped["demo"]
    assert server.env["KEY"] == "value"
