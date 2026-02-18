"""Tests for agents CLI commands."""

from pathlib import Path

from code_agnostic.__main__ import cli


def test_agents_list_empty(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["agents", "list"])
    assert result.exit_code == 0
    assert "No agents" in result.output


def test_agents_list_populated(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    agents_dir = core_root / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "planner.md").write_text("agent content", encoding="utf-8")

    result = cli_runner.invoke(cli, ["agents", "list"])
    assert result.exit_code == 0
    assert "planner" in result.output


def test_agents_remove_existing(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    agents_dir = core_root / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "old-agent.md").write_text("content", encoding="utf-8")

    result = cli_runner.invoke(cli, ["agents", "remove", "--name", "old-agent"])
    assert result.exit_code == 0
    assert "Removed" in result.output
    assert not (agents_dir / "old-agent.md").exists()


def test_agents_remove_nonexistent(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["agents", "remove", "--name", "nope"])
    assert result.exit_code != 0


def test_agents_workspace_scoped(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path, cli_runner
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cli_runner.invoke(cli, ["workspaces", "add", "--name", "myws", "--path", str(ws)])

    ws_agents = core_root / "workspaces" / "myws" / "agents"
    ws_agents.mkdir(parents=True)
    (ws_agents / "ws-agent.md").write_text("ws agent", encoding="utf-8")

    result = cli_runner.invoke(cli, ["agents", "list", "-w", "myws"])
    assert result.exit_code == 0
    assert "ws-agent" in result.output
