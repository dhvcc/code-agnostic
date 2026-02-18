import json
from pathlib import Path

from jsonschema import Draft202012Validator

from code_agnostic.__main__ import cli


def _cursor_schema() -> dict:
    schema_path = (
        Path(__file__).resolve().parent.parent
        / "code_agnostic"
        / "apps"
        / "cursor"
        / "schema.json"
    )
    return json.loads(schema_path.read_text(encoding="utf-8"))


def test_apply_does_not_touch_cursor_home_when_cursor_sync_disabled(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
) -> None:
    result = cli_runner.invoke(cli, ["apply"])

    assert result.exit_code == 0
    assert not (tmp_path / ".cursor").exists()


def test_cursor_schema_accepts_documented_mcp_examples() -> None:
    schema = _cursor_schema()
    validator = Draft202012Validator(schema)

    local_payload = {
        "mcpServers": {
            "server-name": {
                "command": "npx",
                "args": ["-y", "mcp-server"],
                "env": {"API_KEY": "value"},
            }
        }
    }
    remote_payload = {
        "mcpServers": {
            "server-name": {
                "url": "http://localhost:3000/mcp",
                "headers": {"API_KEY": "value"},
            }
        }
    }
    oauth_payload = {
        "mcpServers": {
            "oauth-server": {
                "url": "https://api.example.com/mcp",
                "auth": {
                    "CLIENT_ID": "your-oauth-client-id",
                    "CLIENT_SECRET": "your-oauth-client-secret",
                },
            }
        }
    }

    assert list(validator.iter_errors(local_payload)) == []
    assert list(validator.iter_errors(remote_payload)) == []
    assert list(validator.iter_errors(oauth_payload)) == []


def test_cursor_schema_rejects_server_without_command_or_url() -> None:
    schema = _cursor_schema()
    validator = Draft202012Validator(schema)

    invalid_payload = {
        "mcpServers": {
            "broken": {
                "env": {"API_KEY": "value"},
            }
        }
    }

    errors = list(validator.iter_errors(invalid_payload))
    assert errors


def test_apply_cursor_generates_schema_valid_config(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "local": {"command": "npx", "args": ["-y", "local-server"]},
                    "remote": {"url": "https://example.com/mcp"},
                }
            }
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])

    assert result.exit_code == 0
    payload = json.loads(
        (tmp_path / ".cursor" / "mcp.json").read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(_cursor_schema())
    assert list(validator.iter_errors(payload)) == []
