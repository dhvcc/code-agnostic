from code_agnostic.apps.common.models import MCPServerType
from code_agnostic.apps.common.utils import common_mcp_to_dto


def test_stdio_server() -> None:
    result = common_mcp_to_dto({"local": {"command": "npx", "args": ["-y", "demo"]}})

    assert "local" in result
    server = result["local"]
    assert server.type == MCPServerType.STDIO
    assert server.command == "npx"
    assert server.args == ["-y", "demo"]


def test_http_server() -> None:
    result = common_mcp_to_dto({"remote": {"url": "https://example.com/mcp"}})

    server = result["remote"]
    assert server.type == MCPServerType.HTTP
    assert server.url == "https://example.com/mcp"
    assert server.auth is None


def test_oauth_server() -> None:
    result = common_mcp_to_dto(
        {
            "oauth": {
                "url": "https://example.com/oauth",
                "auth": {
                    "client_id": "cid",
                    "client_secret": "csecret",
                    "scopes": ["read", "write"],
                },
            }
        }
    )

    server = result["oauth"]
    assert server.type == MCPServerType.OAUTH
    assert server.auth is not None
    assert server.auth.client_id == "cid"
    assert server.auth.client_secret == "csecret"
    assert server.auth.scopes == ["read", "write"]


def test_command_takes_priority_over_url() -> None:
    result = common_mcp_to_dto(
        {"both": {"command": "npx", "url": "https://example.com/mcp"}}
    )

    server = result["both"]
    assert server.type == MCPServerType.STDIO
    assert server.command == "npx"


def test_env_key_takes_priority_over_environment() -> None:
    result = common_mcp_to_dto(
        {
            "demo": {
                "command": "npx",
                "env": {"A": "1"},
                "environment": {"B": "2"},
            }
        }
    )

    server = result["demo"]
    assert server.env == {"A": "1"}


def test_environment_fallback_when_env_not_dict() -> None:
    result = common_mcp_to_dto(
        {
            "demo": {
                "command": "npx",
                "env": "not-a-dict",
                "environment": {"B": "2"},
            }
        }
    )

    server = result["demo"]
    assert server.env == {"B": "2"}


def test_non_dict_entry_silently_skipped() -> None:
    result = common_mcp_to_dto({"bad": "not-a-dict", "good": {"command": "npx"}})

    assert "bad" not in result
    assert "good" in result


def test_empty_mcp_servers_dict() -> None:
    result = common_mcp_to_dto({})

    assert result == {}


def test_server_with_headers() -> None:
    result = common_mcp_to_dto(
        {
            "demo": {
                "url": "https://example.com/mcp",
                "headers": {"Authorization": "Bearer token", "X-Custom": "val"},
            }
        }
    )

    server = result["demo"]
    assert server.headers == {"Authorization": "Bearer token", "X-Custom": "val"}


def test_auth_missing_client_id_results_in_no_auth() -> None:
    result = common_mcp_to_dto(
        {
            "demo": {
                "url": "https://example.com/mcp",
                "auth": {"client_secret": "secret"},
            }
        }
    )

    server = result["demo"]
    assert server.auth is None
    assert server.type == MCPServerType.HTTP


def test_auth_missing_client_secret_results_in_no_auth() -> None:
    result = common_mcp_to_dto(
        {
            "demo": {
                "url": "https://example.com/mcp",
                "auth": {"client_id": "id"},
            }
        }
    )

    server = result["demo"]
    assert server.auth is None
    assert server.type == MCPServerType.HTTP


def test_auth_scopes_non_list_becomes_empty() -> None:
    result = common_mcp_to_dto(
        {
            "demo": {
                "url": "https://example.com/mcp",
                "auth": {
                    "client_id": "id",
                    "client_secret": "secret",
                    "scopes": "not-a-list",
                },
            }
        }
    )

    server = result["demo"]
    assert server.auth is not None
    assert server.auth.scopes == []


def test_args_non_list_becomes_empty() -> None:
    result = common_mcp_to_dto({"demo": {"command": "npx", "args": "not-a-list"}})

    server = result["demo"]
    assert server.args == []


def test_entry_without_command_or_url_skipped() -> None:
    result = common_mcp_to_dto({"demo": {"env": {"A": "1"}}})

    assert result == {}
