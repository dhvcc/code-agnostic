"""Tests for named flag syntax on all commands."""

from pathlib import Path

from code_agnostic.__main__ import cli


def test_plan_with_app_flag(
    minimal_shared_config: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")
    result = cli_runner.invoke(cli, ["plan", "-a", "cursor"])
    assert result.exit_code == 0
    assert "cursor" in result.output


def test_plan_with_long_app_flag(
    minimal_shared_config: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")
    result = cli_runner.invoke(cli, ["plan", "--app", "cursor"])
    assert result.exit_code == 0
    assert "cursor" in result.output


def test_plan_defaults_to_all(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["plan"])
    assert result.exit_code == 0


def test_apply_with_app_flag(
    minimal_shared_config: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")
    result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])
    assert result.exit_code == 0


def test_apply_with_long_app_flag(
    minimal_shared_config: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")
    result = cli_runner.invoke(cli, ["apply", "--app", "cursor"])
    assert result.exit_code == 0


def test_status_with_app_flag(
    minimal_shared_config: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")
    result = cli_runner.invoke(cli, ["status", "-a", "cursor"])
    assert result.exit_code == 0
    assert "cursor" in result.output


def test_status_with_verbose_flag(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["status", "-v"])
    assert result.exit_code == 0


def test_apps_enable_with_app_flag(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["apps", "enable", "-a", "cursor"])
    assert result.exit_code == 0
    assert "cursor" in result.output
    assert "enabled" in result.output


def test_apps_enable_with_long_app_flag(
    minimal_shared_config: Path, cli_runner
) -> None:
    result = cli_runner.invoke(cli, ["apps", "enable", "--app", "cursor"])
    assert result.exit_code == 0


def test_apps_disable_with_app_flag(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["apps", "enable", "-a", "cursor"])
    assert result.exit_code == 0
    result = cli_runner.invoke(cli, ["apps", "disable", "-a", "cursor"])
    assert result.exit_code == 0


def test_workspaces_add_with_named_flags(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "myws", "--path", str(ws)]
    )
    assert result.exit_code == 0
    assert "Workspace added" in result.output


def test_workspaces_remove_with_named_flag(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cli_runner.invoke(cli, ["workspaces", "add", "--name", "myws", "--path", str(ws)])
    result = cli_runner.invoke(cli, ["workspaces", "remove", "--name", "myws"])
    assert result.exit_code == 0
    assert "Workspace removed" in result.output


def test_workspaces_git_exclude_with_workspace_flag(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "repo" / ".git" / "info").mkdir(parents=True)
    cli_runner.invoke(cli, ["workspaces", "add", "--name", "myws", "--path", str(ws)])
    enable_app("cursor")
    result = cli_runner.invoke(cli, ["workspaces", "git-exclude", "-w", "myws"])
    assert result.exit_code == 0
    assert "Updated git excludes" in result.output


def test_workspaces_git_exclude_with_long_workspace_flag(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "repo" / ".git" / "info").mkdir(parents=True)
    cli_runner.invoke(cli, ["workspaces", "add", "--name", "myws", "--path", str(ws)])
    enable_app("cursor")
    result = cli_runner.invoke(
        cli, ["workspaces", "git-exclude", "--workspace", "myws"]
    )
    assert result.exit_code == 0


def test_import_plan_with_app_flag(cli_runner, tmp_path: Path) -> None:
    codex_root = tmp_path / ".codex"
    codex_root.mkdir(parents=True)
    (codex_root / "config.toml").write_text(
        '[mcp_servers.demo]\ncommand = "uvx"\n', encoding="utf-8"
    )
    result = cli_runner.invoke(cli, ["import", "plan", "-a", "codex"])
    assert result.exit_code == 0


def test_import_apply_with_app_flag(cli_runner, tmp_path: Path) -> None:
    codex_root = tmp_path / ".codex"
    codex_root.mkdir(parents=True)
    (codex_root / "config.toml").write_text(
        '[mcp_servers.demo]\ncommand = "uvx"\n', encoding="utf-8"
    )
    result = cli_runner.invoke(cli, ["import", "apply", "-a", "codex"])
    assert result.exit_code == 0
