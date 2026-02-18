"""Tests for skills CLI commands."""

from pathlib import Path

from code_agnostic.__main__ import cli


def test_skills_list_empty(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["skills", "list"])
    assert result.exit_code == 0
    assert "No skills" in result.output


def test_skills_list_populated(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    skill_dir = core_root / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("skill content", encoding="utf-8")

    result = cli_runner.invoke(cli, ["skills", "list"])
    assert result.exit_code == 0
    assert "my-skill" in result.output


def test_skills_remove_existing(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    skill_dir = core_root / "skills" / "old-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("content", encoding="utf-8")

    result = cli_runner.invoke(cli, ["skills", "remove", "--name", "old-skill"])
    assert result.exit_code == 0
    assert "Removed" in result.output
    assert not skill_dir.exists()


def test_skills_remove_nonexistent(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["skills", "remove", "--name", "nope"])
    assert result.exit_code != 0


def test_skills_workspace_scoped(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path, cli_runner
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cli_runner.invoke(cli, ["workspaces", "add", "--name", "myws", "--path", str(ws)])

    ws_skill = core_root / "workspaces" / "myws" / "skills" / "ws-skill"
    ws_skill.mkdir(parents=True)
    (ws_skill / "SKILL.md").write_text("ws skill", encoding="utf-8")

    result = cli_runner.invoke(cli, ["skills", "list", "-w", "myws"])
    assert result.exit_code == 0
    assert "ws-skill" in result.output
