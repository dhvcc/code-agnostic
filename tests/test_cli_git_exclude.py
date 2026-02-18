"""Tests for git-exclude CLI commands."""

from pathlib import Path

from code_agnostic.__main__ import cli


def _setup_workspace(cli_runner, tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    cli_runner.invoke(cli, ["workspaces", "add", "--name", "myws", "--path", str(ws)])
    return ws


def test_exclude_add(minimal_shared_config: Path, tmp_path: Path, cli_runner) -> None:
    _setup_workspace(cli_runner, tmp_path)
    result = cli_runner.invoke(
        cli, ["workspaces", "exclude-add", "--pattern", "*.generated", "-w", "myws"]
    )
    assert result.exit_code == 0
    assert "Added" in result.output


def test_exclude_remove(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    _setup_workspace(cli_runner, tmp_path)
    cli_runner.invoke(
        cli, ["workspaces", "exclude-add", "--pattern", "*.generated", "-w", "myws"]
    )
    result = cli_runner.invoke(
        cli, ["workspaces", "exclude-remove", "--pattern", "*.generated", "-w", "myws"]
    )
    assert result.exit_code == 0
    assert "Removed" in result.output


def test_exclude_remove_not_found(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    _setup_workspace(cli_runner, tmp_path)
    result = cli_runner.invoke(
        cli, ["workspaces", "exclude-remove", "--pattern", "nope", "-w", "myws"]
    )
    assert result.exit_code != 0


def test_exclude_list(minimal_shared_config: Path, tmp_path: Path, cli_runner) -> None:
    _setup_workspace(cli_runner, tmp_path)
    cli_runner.invoke(
        cli, ["workspaces", "exclude-add", "--pattern", "*.generated", "-w", "myws"]
    )
    result = cli_runner.invoke(cli, ["workspaces", "exclude-list", "-w", "myws"])
    assert result.exit_code == 0
    assert "*.generated" in result.output


def test_exclude_list_empty(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    _setup_workspace(cli_runner, tmp_path)
    result = cli_runner.invoke(cli, ["workspaces", "exclude-list", "-w", "myws"])
    assert result.exit_code == 0
    assert "defaults" in result.output.lower() or "include_defaults" in result.output
