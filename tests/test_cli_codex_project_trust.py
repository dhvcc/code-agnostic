import json
from pathlib import Path

from code_agnostic.__main__ import cli
import tomlkit

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


TRUST_SCOPE = "app:codex:project_trust"


def _write_codex_base(root: Path, projects: dict[str, dict[str, str]]) -> None:
    path = root / "config" / "codex.base.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"projects": projects}), encoding="utf-8")


def _read_codex_config(tmp_path: Path) -> dict:
    return tomllib.loads(
        (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    )


def _enable_codex(cli_runner, *, source_root: Path | None = None):
    env = {"CODE_AGNOSTIC_CONFIG_ROOT": str(source_root)} if source_root else {}
    return cli_runner.invoke(cli, ["apps", "enable", "-a", "codex"], env=env)


def _run(cli_runner, args: list[str], *, source_root: Path | None = None):
    env = {"CODE_AGNOSTIC_CONFIG_ROOT": str(source_root)} if source_root else {}
    return cli_runner.invoke(cli, args, env=env)


def test_codex_project_trust_is_normalized_owned_and_idempotent(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
) -> None:
    assert _enable_codex(cli_runner).exit_code == 0
    real_project = tmp_path / "real-project"
    real_project.mkdir()
    project_link = tmp_path / "project-link"
    project_link.symlink_to(real_project, target_is_directory=True)
    _write_codex_base(
        core_root,
        {str(project_link): {"trust_level": "trusted"}},
    )

    first = _run(cli_runner, ["apply", "-a", "codex"])
    assert first.exit_code == 0, first.output

    canonical_project = str(real_project.resolve())
    config = _read_codex_config(tmp_path)
    assert config["projects"] == {canonical_project: {"trust_level": "trusted"}}
    state = json.loads((core_root / ".sync-state.json").read_text(encoding="utf-8"))
    assert state["managed_values"][TRUST_SCOPE] == {canonical_project: "trusted"}

    second = _run(cli_runner, ["apply", "-a", "codex"])
    assert second.exit_code == 0, second.output
    assert "applied  0" in second.output


def test_codex_project_trust_source_removal_preserves_unmanaged_and_user_changed(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
) -> None:
    assert _enable_codex(cli_runner).exit_code == 0
    owned_project = tmp_path / "owned"
    changed_project = tmp_path / "changed"
    other_project = tmp_path / "other"
    for project in (owned_project, changed_project, other_project):
        project.mkdir()
    _write_codex_base(
        core_root,
        {
            str(owned_project): {"trust_level": "trusted"},
            str(changed_project): {"trust_level": "trusted"},
        },
    )
    assert _run(cli_runner, ["apply", "-a", "codex"]).exit_code == 0

    config_path = tmp_path / ".codex" / "config.toml"
    config = _read_codex_config(tmp_path)
    config["projects"][str(changed_project.resolve())]["trust_level"] = "untrusted"
    config["projects"][str(other_project.resolve())] = {"trust_level": "untrusted"}
    config_path.write_text(
        tomlkit.dumps(config),
        encoding="utf-8",
    )
    _write_codex_base(core_root, {})

    cleanup = _run(cli_runner, ["apply", "-a", "codex"])
    assert cleanup.exit_code == 0, cleanup.output
    projects = _read_codex_config(tmp_path).get("projects", {})
    assert str(owned_project.resolve()) not in projects
    assert projects[str(changed_project.resolve())] == {"trust_level": "untrusted"}
    assert projects[str(other_project.resolve())] == {"trust_level": "untrusted"}
    state = json.loads((core_root / ".sync-state.json").read_text(encoding="utf-8"))
    assert TRUST_SCOPE not in state.get("managed_values", {})


def test_disabling_codex_reclaims_owned_project_trust(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
) -> None:
    assert _enable_codex(cli_runner).exit_code == 0
    project = tmp_path / "project"
    project.mkdir()
    _write_codex_base(core_root, {str(project): {"trust_level": "trusted"}})
    assert _run(cli_runner, ["apply", "-a", "codex"]).exit_code == 0

    disabled = _run(cli_runner, ["apps", "disable", "-a", "codex"])
    assert disabled.exit_code == 0, disabled.output
    assert str(project.resolve()) not in _read_codex_config(tmp_path).get(
        "projects", {}
    )


def test_codex_project_trust_conflict_preserves_unmanaged_setting(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
) -> None:
    assert _enable_codex(cli_runner).exit_code == 0
    project = tmp_path / "project"
    project.mkdir()
    config_path = tmp_path / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        tomlkit.dumps(
            {"projects": {str(project.resolve()): {"trust_level": "untrusted"}}}
        ),
        encoding="utf-8",
    )
    _write_codex_base(
        core_root,
        {str(project): {"trust_level": "trusted"}},
    )

    result = _run(cli_runner, ["plan", "-a", "codex"])
    assert result.exit_code == 1
    assert "trust" in result.output.lower()
    assert (
        _read_codex_config(tmp_path)["projects"][str(project.resolve())]["trust_level"]
        == "untrusted"
    )


def test_codex_project_trust_same_value_unmanaged_setting_is_conflict(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
) -> None:
    assert _enable_codex(cli_runner).exit_code == 0
    project = tmp_path / "project"
    project.mkdir()
    config_path = tmp_path / ".codex" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        tomlkit.dumps(
            {"projects": {str(project.resolve()): {"trust_level": "trusted"}}}
        ),
        encoding="utf-8",
    )
    _write_codex_base(
        core_root,
        {str(project): {"trust_level": "trusted"}},
    )

    result = _run(cli_runner, ["plan", "-a", "codex"])
    assert result.exit_code == 1
    assert "trust" in result.output.lower()
    assert not (core_root / ".sync-state.json").exists()


def test_codex_project_trust_user_change_after_apply_is_conflict(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
) -> None:
    assert _enable_codex(cli_runner).exit_code == 0
    project = tmp_path / "project"
    project.mkdir()
    _write_codex_base(
        core_root,
        {str(project): {"trust_level": "trusted"}},
    )
    assert _run(cli_runner, ["apply", "-a", "codex"]).exit_code == 0

    config_path = tmp_path / ".codex" / "config.toml"
    config = _read_codex_config(tmp_path)
    config["projects"][str(project.resolve())]["trust_level"] = "untrusted"
    config_path.write_text(tomlkit.dumps(config), encoding="utf-8")

    result = _run(cli_runner, ["plan", "-a", "codex"])
    assert result.exit_code == 1
    assert "user-modified" in result.output.lower()
    assert (
        _read_codex_config(tmp_path)["projects"][str(project.resolve())]["trust_level"]
        == "untrusted"
    )


def test_independent_source_roots_preserve_each_codex_project_trust_entry(
    tmp_path: Path,
    cli_runner,
) -> None:
    source_a = tmp_path / "source-a"
    source_b = tmp_path / "source-b"
    for source in (source_a, source_b):
        (source / "config" / "mcp.base.json").parent.mkdir(parents=True)
        (source / "config" / "mcp.base.json").write_text(
            json.dumps({"mcpServers": {}}), encoding="utf-8"
        )
        assert _enable_codex(cli_runner, source_root=source).exit_code == 0

    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    _write_codex_base(
        source_a,
        {str(project_a): {"trust_level": "trusted"}},
    )
    _write_codex_base(
        source_b,
        {str(project_b): {"trust_level": "trusted"}},
    )

    assert _run(cli_runner, ["apply"], source_root=source_a).exit_code == 0
    assert _run(cli_runner, ["apply"], source_root=source_b).exit_code == 0
    _write_codex_base(source_a, {})
    cleanup = _run(cli_runner, ["apply"], source_root=source_a)
    assert cleanup.exit_code == 0, cleanup.output

    assert _read_codex_config(tmp_path)["projects"] == {
        str(project_b.resolve()): {"trust_level": "trusted"}
    }
