"""Tests for mcp CLI commands."""

import json
from pathlib import Path

from code_agnostic.__main__ import cli


def test_mcp_list_empty(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["mcp", "list"])
    assert result.exit_code == 0
    assert "No MCP servers" in result.output


def test_mcp_list_populated(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "github": {"command": "npx", "args": ["mcp-github"]},
                }
            }
        ),
        encoding="utf-8",
    )
    result = cli_runner.invoke(cli, ["mcp", "list"])
    assert result.exit_code == 0
    assert "github" in result.output


def test_mcp_add_stdio(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    result = cli_runner.invoke(
        cli,
        ["mcp", "add", "github", "--command", "npx", "--args", "mcp-github"],
    )
    assert result.exit_code == 0
    assert "Added" in result.output

    payload = json.loads(
        (core_root / "config" / "mcp.base.json").read_text(encoding="utf-8")
    )
    assert "github" in payload["mcpServers"]
    assert payload["mcpServers"]["github"]["command"] == "npx"


def test_mcp_add_http(minimal_shared_config: Path, core_root: Path, cli_runner) -> None:
    result = cli_runner.invoke(
        cli,
        ["mcp", "add", "remote", "--url", "https://example.com/mcp"],
    )
    assert result.exit_code == 0
    assert "Added" in result.output

    payload = json.loads(
        (core_root / "config" / "mcp.base.json").read_text(encoding="utf-8")
    )
    assert payload["mcpServers"]["remote"]["url"] == "https://example.com/mcp"


def test_mcp_add_with_env(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(
        cli,
        [
            "mcp",
            "add",
            "github",
            "--command",
            "npx",
            "--args",
            "mcp-github",
            "--env",
            "GITHUB_TOKEN",
        ],
    )
    assert result.exit_code == 0


def test_mcp_add_with_env_literal(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    result = cli_runner.invoke(
        cli,
        [
            "mcp",
            "add",
            "demo",
            "--command",
            "uvx",
            "--env",
            "KEY=literal-value",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(
        (core_root / "config" / "mcp.base.json").read_text(encoding="utf-8")
    )
    assert payload["mcpServers"]["demo"]["env"]["KEY"] == "literal-value"


def test_mcp_add_conflict_default_fails(
    minimal_shared_config: Path, cli_runner
) -> None:
    cli_runner.invoke(cli, ["mcp", "add", "demo", "--command", "uvx"])
    result = cli_runner.invoke(cli, ["mcp", "add", "demo", "--command", "uvx"])
    assert result.exit_code != 0


def test_mcp_add_conflict_skip(minimal_shared_config: Path, cli_runner) -> None:
    cli_runner.invoke(cli, ["mcp", "add", "demo", "--command", "uvx"])
    result = cli_runner.invoke(
        cli, ["mcp", "add", "demo", "--command", "other", "--on-conflict", "skip"]
    )
    assert result.exit_code == 0
    assert "Skipped" in result.output


def test_mcp_add_conflict_overwrite(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    cli_runner.invoke(cli, ["mcp", "add", "demo", "--command", "uvx", "--args", "old"])
    result = cli_runner.invoke(
        cli,
        [
            "mcp",
            "add",
            "demo",
            "--command",
            "uvx",
            "--args",
            "new",
            "--on-conflict",
            "overwrite",
        ],
    )
    assert result.exit_code == 0
    payload = json.loads(
        (core_root / "config" / "mcp.base.json").read_text(encoding="utf-8")
    )
    assert payload["mcpServers"]["demo"]["args"] == ["new"]


def test_mcp_remove_existing(minimal_shared_config: Path, cli_runner) -> None:
    cli_runner.invoke(cli, ["mcp", "add", "demo", "--command", "uvx"])
    result = cli_runner.invoke(cli, ["mcp", "remove", "demo"])
    assert result.exit_code == 0
    assert "Removed" in result.output


def test_mcp_remove_nonexistent(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["mcp", "remove", "nope"])
    assert result.exit_code != 0


def test_mcp_add_requires_command_or_url(
    minimal_shared_config: Path, cli_runner
) -> None:
    result = cli_runner.invoke(cli, ["mcp", "add", "broken"])
    assert result.exit_code != 0


def test_mcp_workspace_scoped(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cli_runner.invoke(cli, ["workspaces", "add", "--name", "myws", "--path", str(ws)])

    result = cli_runner.invoke(
        cli, ["mcp", "add", "local", "--command", "uvx", "-w", "myws"]
    )
    assert result.exit_code == 0

    list_result = cli_runner.invoke(cli, ["mcp", "list", "-w", "myws"])
    assert list_result.exit_code == 0
    assert "local" in list_result.output

    global_list = cli_runner.invoke(cli, ["mcp", "list"])
    assert "local" not in global_list.output


def test_mcp_list_workspace_not_found(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["mcp", "list", "-w", "nonexistent"])
    assert result.exit_code != 0
