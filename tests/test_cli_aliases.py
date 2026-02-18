"""Tests for singular/plural CLI group aliases."""

from pathlib import Path

from code_agnostic.__main__ import cli


def test_app_alias_resolves_to_apps(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["app", "list"])
    assert result.exit_code == 0


def test_app_alias_enable(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["app", "enable", "-a", "cursor"])
    assert result.exit_code == 0
    assert "cursor" in result.output


def test_app_alias_disable(minimal_shared_config: Path, cli_runner, enable_app) -> None:
    enable_app("cursor")
    result = cli_runner.invoke(cli, ["app", "disable", "-a", "cursor"])
    assert result.exit_code == 0


def test_workspace_alias_resolves_to_workspaces(
    minimal_shared_config: Path, cli_runner
) -> None:
    result = cli_runner.invoke(cli, ["workspace", "list"])
    assert result.exit_code == 0


def test_workspace_alias_add(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    result = cli_runner.invoke(
        cli, ["workspace", "add", "--name", "myws", "--path", str(ws)]
    )
    assert result.exit_code == 0
    assert "Workspace added" in result.output


def test_workspace_alias_remove(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cli_runner.invoke(cli, ["workspace", "add", "--name", "myws", "--path", str(ws)])
    result = cli_runner.invoke(cli, ["workspace", "remove", "--name", "myws"])
    assert result.exit_code == 0
    assert "Workspace removed" in result.output
