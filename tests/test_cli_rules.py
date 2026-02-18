"""Tests for rules CLI commands."""

from pathlib import Path

from code_agnostic.__main__ import cli


def test_rules_list_empty(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["rules", "list"])
    assert result.exit_code == 0
    assert "No rules" in result.output


def test_rules_list_populated(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    rules_dir = core_root / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "python-style.md").write_text(
        "---\ndescription: Python standards\n---\n\nUse type hints.\n",
        encoding="utf-8",
    )
    result = cli_runner.invoke(cli, ["rules", "list"])
    assert result.exit_code == 0
    assert "python-style" in result.output


def test_rules_remove_existing(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    rules_dir = core_root / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "old-rule.md").write_text("content", encoding="utf-8")
    result = cli_runner.invoke(cli, ["rules", "remove", "--name", "old-rule"])
    assert result.exit_code == 0
    assert "Removed" in result.output


def test_rules_remove_nonexistent(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["rules", "remove", "--name", "nope"])
    assert result.exit_code != 0


def test_rules_workspace_scoped_list(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path, cli_runner
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cli_runner.invoke(cli, ["workspaces", "add", "--name", "myws", "--path", str(ws)])

    ws_rules = core_root / "workspaces" / "myws" / "rules"
    ws_rules.mkdir(parents=True)
    (ws_rules / "ws-rule.md").write_text(
        "---\ndescription: Workspace rule\n---\n\nWS content.\n",
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["rules", "list", "-w", "myws"])
    assert result.exit_code == 0
    assert "ws-rule" in result.output


def test_rules_workspace_not_found(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["rules", "list", "-w", "nonexistent"])
    assert result.exit_code != 0
