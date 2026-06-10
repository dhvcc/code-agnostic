"""Tests for skills CLI commands."""

from pathlib import Path
import sys

import pytest

from code_agnostic.__main__ import cli
from code_agnostic.core.repository import CoreRepository


def _legacy_skill(path: Path, body: bytes = b"skill content\n") -> Path:
    path.mkdir(parents=True)
    (path / "SKILL.md").write_bytes(body)
    return path


def _bundle_skill(path: Path) -> Path:
    path.mkdir(parents=True)
    (path / "meta.yaml").write_bytes(
        b"spec_version: v1\nkind: skill\nname: bundle-skill\n"
    )
    (path / "prompt.md").write_bytes(b"skill content\n")
    return path


def test_skills_list_empty(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["skills", "list"])
    assert result.exit_code == 0
    assert "No global skills" in result.output
    assert "Copy a skill into ~/.config/code-agnostic/skills/<name>" in result.output
    assert "code-agnostic plan" in result.output
    assert "code-agnostic apply" in result.output


def test_skills_install_global_explicit(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path, cli_runner
) -> None:
    source = _legacy_skill(tmp_path / "my-skill", b"\x00raw bytes\n")

    result = cli_runner.invoke(cli, ["skills", "install", "--global", str(source)])

    assert result.exit_code == 0
    assert "Installed global skill: my-skill" in result.output
    assert (core_root / "skills" / "my-skill" / "SKILL.md").read_bytes() == (
        b"\x00raw bytes\n"
    )


def test_skills_install_project_explicit(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path, cli_runner
) -> None:
    source = _bundle_skill(tmp_path / "bundle-skill")
    project_root = tmp_path / "project"
    project_root.mkdir()
    CoreRepository().add_project("app", project_root)

    result = cli_runner.invoke(
        cli, ["skills", "install", "--project", "app", str(source)]
    )

    assert result.exit_code == 0
    assert "Installed project:app skill: bundle-skill" in result.output
    assert (
        core_root / "projects" / "app" / "skills" / "bundle-skill" / "meta.yaml"
    ).read_bytes() == (source / "meta.yaml").read_bytes()


def test_skills_install_project_requires_existing_project(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    source = _legacy_skill(tmp_path / "my-skill")

    result = cli_runner.invoke(
        cli, ["skills", "install", "--project", "missing", str(source)]
    )

    assert result.exit_code != 0
    assert "Project not found: missing" in result.output


def test_skills_install_workspace_explicit(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path, cli_runner
) -> None:
    source = _legacy_skill(tmp_path / "my-skill")
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    CoreRepository().add_workspace("team", workspace_root)

    result = cli_runner.invoke(
        cli, ["skills", "install", "--workspace", "team", str(source)]
    )

    assert result.exit_code == 0
    assert "Installed workspace:team skill: my-skill" in result.output
    assert (
        core_root / "workspaces" / "team" / "skills" / "my-skill" / "SKILL.md"
    ).exists()


def test_skills_install_infers_project_scope(
    minimal_shared_config: Path,
    tmp_path: Path,
    core_root: Path,
    cli_runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _legacy_skill(tmp_path / "my-skill")
    project_root = tmp_path / "project"
    nested = project_root / "src"
    nested.mkdir(parents=True)
    CoreRepository().add_project("app", project_root)
    monkeypatch.chdir(nested)

    result = cli_runner.invoke(cli, ["skills", "install", str(source)])

    assert result.exit_code == 0
    assert "Installed project:app skill: my-skill" in result.output
    assert (
        core_root / "projects" / "app" / "skills" / "my-skill" / "SKILL.md"
    ).exists()


def test_skills_install_infers_workspace_scope_when_not_in_project(
    minimal_shared_config: Path,
    tmp_path: Path,
    core_root: Path,
    cli_runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _legacy_skill(tmp_path / "my-skill")
    workspace_root = tmp_path / "workspace"
    nested = workspace_root / "repo"
    nested.mkdir(parents=True)
    CoreRepository().add_workspace("team", workspace_root)
    monkeypatch.chdir(nested)

    result = cli_runner.invoke(cli, ["skills", "install", str(source)])

    assert result.exit_code == 0
    assert "Installed workspace:team skill: my-skill" in result.output
    assert (
        core_root / "workspaces" / "team" / "skills" / "my-skill" / "SKILL.md"
    ).exists()


def test_skills_install_without_unique_scope_requires_explicit_scope(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _legacy_skill(tmp_path / "my-skill")
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)

    result = cli_runner.invoke(cli, ["skills", "install", str(source)])

    assert result.exit_code != 0
    assert "No unique project/workspace scope detected" in result.output


def test_skills_install_rejects_invalid_source(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    source = tmp_path / "not-a-skill"
    source.mkdir()
    (source / "README.md").write_text("nope", encoding="utf-8")

    result = cli_runner.invoke(cli, ["skills", "install", str(source)])

    assert result.exit_code != 0
    assert "Invalid skill source" in result.output


def test_skills_install_rejects_path_like_destination_name(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    if sys.platform == "win32":
        pytest.skip("Windows parses drive-like names as paths before CLI validation.")
    source = _legacy_skill(tmp_path / "C:bad")

    result = cli_runner.invoke(cli, ["skills", "install", str(source)])

    assert result.exit_code != 0
    assert "Invalid skill name" in result.output


def test_skills_install_refuses_duplicate_destination(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path, cli_runner
) -> None:
    source = _legacy_skill(tmp_path / "my-skill", b"new\n")
    existing = core_root / "skills" / "my-skill"
    _legacy_skill(existing, b"existing\n")

    result = cli_runner.invoke(cli, ["skills", "install", "--global", str(source)])

    assert result.exit_code != 0
    assert "Skill already exists: global:my-skill" in result.output
    assert (existing / "SKILL.md").read_bytes() == b"existing\n"


def test_skills_install_does_not_write_direct_app_targets(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path, cli_runner
) -> None:
    source = _legacy_skill(tmp_path / "my-skill")

    result = cli_runner.invoke(cli, ["skills", "install", "--global", str(source)])

    assert result.exit_code == 0
    assert (core_root / "skills" / "my-skill" / "SKILL.md").exists()
    assert not (tmp_path / ".codex" / "skills" / "my-skill").exists()
    assert not (tmp_path / ".cursor" / "rules" / "my-skill").exists()
    assert not (tmp_path / ".config" / "opencode" / "skill" / "my-skill").exists()


def test_skills_list_populated(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    skill_dir = core_root / "skills" / "my-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("skill content", encoding="utf-8")

    result = cli_runner.invoke(cli, ["skills", "list"])
    assert result.exit_code == 0
    assert "my-skill" in result.output
    assert "global" in result.output
    assert "legacy" in result.output
    assert "~/.config/code-agnostic/skills/my-skill" in result.output


def test_skills_list_bundle_source(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    skill_dir = core_root / "skills" / "bundle-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "meta.yaml").write_text(
        "spec_version: v1\nkind: skill\nname: bundle-skill\n", encoding="utf-8"
    )
    (skill_dir / "prompt.md").write_text("skill content", encoding="utf-8")

    result = cli_runner.invoke(cli, ["skills", "list"])

    assert result.exit_code == 0
    assert "bundle-skill" in result.output
    assert "bundle" in result.output


def test_skills_remove_existing(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    skill_dir = core_root / "skills" / "old-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("content", encoding="utf-8")

    result = cli_runner.invoke(cli, ["skills", "remove", "--name", "old-skill"])
    assert result.exit_code == 0
    assert "Removed global skill" in result.output
    assert not skill_dir.exists()


def test_skills_remove_bundle_source(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    skill_dir = core_root / "skills" / "bundle-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "meta.yaml").write_text(
        "spec_version: v1\nkind: skill\nname: bundle-skill\n", encoding="utf-8"
    )
    (skill_dir / "prompt.md").write_text("skill content", encoding="utf-8")

    result = cli_runner.invoke(cli, ["skills", "remove", "--name", "bundle-skill"])

    assert result.exit_code == 0
    assert "Removed" in result.output
    assert not skill_dir.exists()


def test_skills_remove_nonexistent(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["skills", "remove", "--name", "nope"])
    assert result.exit_code != 0


def test_skills_remove_rejects_path_like_name(
    minimal_shared_config: Path, core_root: Path, cli_runner
) -> None:
    (core_root / "skills").mkdir(parents=True, exist_ok=True)
    victim = core_root / "victim" / "keep.txt"
    victim.parent.mkdir(parents=True)
    victim.write_text("keep\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["skills", "remove", "--name", "../victim"])

    assert result.exit_code != 0
    assert "Invalid skill name" in result.output
    assert victim.read_text(encoding="utf-8") == "keep\n"


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
    assert "workspace:myws" in result.output
    assert "Source" in result.output


def test_skills_workspace_list_empty(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path, cli_runner
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    cli_runner.invoke(cli, ["workspaces", "add", "--name", "myws", "--path", str(ws)])

    result = cli_runner.invoke(cli, ["skills", "list", "-w", "myws"])

    assert result.exit_code == 0
    assert "No workspace skills configured for myws" in result.output
    assert (
        "Copy a skill into ~/.config/code-agnostic/workspaces/myws/skills/<name>"
        in result.output
    )
    assert "code-agnostic plan" in result.output
    assert "code-agnostic apply" in result.output
