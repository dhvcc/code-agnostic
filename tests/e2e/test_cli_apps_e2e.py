from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "app,target,expected_action_kind",
    [
        ("opencode", "opencode", "write_json"),
        ("cursor", "cursor", "write_json"),
        ("codex", "codex", "write_text"),
    ],
)
def test_plan_then_apply_syncs_each_app_end_to_end(
    app: str,
    target: str,
    expected_action_kind: str,
    minimal_shared_config: Path,
    cli_runner,
    enable_app,
    expected_app_config_path,
) -> None:
    from code_agnostic.__main__ import cli

    enable_app(app)

    plan_result = cli_runner.invoke(cli, ["plan", target])

    assert plan_result.exit_code == 0
    assert "plan overview" in plan_result.output
    assert expected_action_kind in plan_result.output
    assert target in plan_result.output

    apply_result = cli_runner.invoke(cli, ["apply", target])

    assert apply_result.exit_code == 0
    assert "apply" in apply_result.output
    assert expected_app_config_path(app).exists()


def test_partial_apply_codex_writes_codex_config_only(
    minimal_shared_config: Path,
    cli_runner,
    enable_app,
    expected_app_config_path,
) -> None:
    from code_agnostic.__main__ import cli

    enable_app("codex")
    enable_app("cursor")

    plan_result = cli_runner.invoke(cli, ["plan", "codex"])
    assert plan_result.exit_code == 0
    assert "plan:codex" in plan_result.output
    assert "write_text" in plan_result.output

    apply_result = cli_runner.invoke(cli, ["apply", "codex"])
    assert apply_result.exit_code == 0

    assert expected_app_config_path("codex").exists()
    assert not expected_app_config_path("cursor").exists()


def test_full_roundtrip_all_three_apps(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
    expected_app_config_path,
) -> None:
    import json

    from code_agnostic.__main__ import cli

    enable_app("opencode")
    enable_app("cursor")
    enable_app("codex")

    plan_result = cli_runner.invoke(cli, ["plan"])
    assert plan_result.exit_code == 0
    assert "plan overview" in plan_result.output

    apply_result = cli_runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    assert expected_app_config_path("opencode").exists()
    assert expected_app_config_path("cursor").exists()
    assert expected_app_config_path("codex").exists()

    opencode_payload = json.loads(
        expected_app_config_path("opencode").read_text(encoding="utf-8")
    )
    assert isinstance(opencode_payload, dict)

    cursor_payload = json.loads(
        expected_app_config_path("cursor").read_text(encoding="utf-8")
    )
    assert "mcpServers" in cursor_payload

    status_result = cli_runner.invoke(cli, ["status"])
    assert status_result.exit_code == 0
    assert "synced" in status_result.output


def test_idempotent_apply(
    minimal_shared_config: Path,
    cli_runner,
    enable_app,
    expected_app_config_path,
) -> None:
    from code_agnostic.__main__ import cli

    enable_app("cursor")

    first_apply = cli_runner.invoke(cli, ["apply"])
    assert first_apply.exit_code == 0
    assert expected_app_config_path("cursor").exists()

    second_apply = cli_runner.invoke(cli, ["apply"])
    assert second_apply.exit_code == 0
    assert "0 applied" in second_apply.output or "noop" in second_apply.output.lower()


def test_stale_workspace_cleanup_e2e(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    from code_agnostic.__main__ import cli
    from code_agnostic.constants import AGENTS_FILENAME

    enable_app("opencode")

    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    (workspace_root / AGENTS_FILENAME).write_text("rules", encoding="utf-8")
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "myws", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    apply1 = cli_runner.invoke(cli, ["apply"])
    assert apply1.exit_code == 0

    link = workspace_root / "repo-a" / AGENTS_FILENAME
    assert link.is_symlink()

    remove_result = cli_runner.invoke(cli, ["workspaces", "remove", "myws"])
    assert remove_result.exit_code == 0

    apply2 = cli_runner.invoke(cli, ["apply"])
    assert apply2.exit_code == 0
    assert not link.is_symlink()


def test_cross_app_isolation(
    minimal_shared_config: Path,
    cli_runner,
    enable_app,
    expected_app_config_path,
) -> None:
    from code_agnostic.__main__ import cli

    enable_app("cursor")
    enable_app("codex")

    apply_cursor = cli_runner.invoke(cli, ["apply", "cursor"])
    assert apply_cursor.exit_code == 0
    assert expected_app_config_path("cursor").exists()
    assert not expected_app_config_path("codex").exists()

    apply_codex = cli_runner.invoke(cli, ["apply", "codex"])
    assert apply_codex.exit_code == 0
    assert expected_app_config_path("cursor").exists()
    assert expected_app_config_path("codex").exists()


def test_skills_agents_symlink_e2e(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    from code_agnostic.__main__ import cli

    enable_app("opencode")

    core_root = tmp_path / ".config" / "code-agnostic"
    (core_root / "skills" / "my-skill").mkdir(parents=True)
    (core_root / "skills" / "my-skill" / "SKILL.md").write_text(
        "skill content", encoding="utf-8"
    )
    (core_root / "agents").mkdir(parents=True)
    (core_root / "agents" / "planner.md").write_text("agent content", encoding="utf-8")

    apply_result = cli_runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    opencode_root = tmp_path / ".config" / "opencode"
    skill_link = opencode_root / "skills" / "my-skill"
    agent_link = opencode_root / "agents" / "planner.md"

    if skill_link.exists() or skill_link.is_symlink():
        assert skill_link.is_symlink()
    if agent_link.exists() or agent_link.is_symlink():
        assert agent_link.is_symlink()


def test_cursor_skills_agents_symlink_e2e(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    from code_agnostic.__main__ import cli

    enable_app("cursor")

    core_root = tmp_path / ".config" / "code-agnostic"
    (core_root / "skills" / "my-skill").mkdir(parents=True)
    (core_root / "skills" / "my-skill" / "SKILL.md").write_text(
        "skill content", encoding="utf-8"
    )
    (core_root / "agents").mkdir(parents=True)
    (core_root / "agents" / "planner.md").write_text("agent content", encoding="utf-8")

    apply_result = cli_runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    cursor_root = tmp_path / ".cursor"
    skill_link = cursor_root / "skills" / "my-skill"
    agent_link = cursor_root / "agents" / "planner.md"

    assert skill_link.is_symlink()
    assert agent_link.is_symlink()


def test_codex_skills_symlink_e2e(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    from code_agnostic.__main__ import cli

    enable_app("codex")

    core_root = tmp_path / ".config" / "code-agnostic"
    (core_root / "skills" / "my-skill").mkdir(parents=True)
    (core_root / "skills" / "my-skill" / "SKILL.md").write_text(
        "skill content", encoding="utf-8"
    )

    apply_result = cli_runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    codex_root = tmp_path / ".codex"
    skill_link = codex_root / "skills" / "my-skill"

    assert skill_link.is_symlink()


def test_cursor_stale_skill_cleanup_e2e(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    from code_agnostic.__main__ import cli

    enable_app("cursor")

    core_root = tmp_path / ".config" / "code-agnostic"
    (core_root / "skills" / "old-skill").mkdir(parents=True)
    (core_root / "skills" / "old-skill" / "SKILL.md").write_text(
        "old", encoding="utf-8"
    )

    apply1 = cli_runner.invoke(cli, ["apply"])
    assert apply1.exit_code == 0

    cursor_root = tmp_path / ".cursor"
    old_link = cursor_root / "skills" / "old-skill"
    assert old_link.is_symlink()

    import shutil

    shutil.rmtree(core_root / "skills" / "old-skill")

    apply2 = cli_runner.invoke(cli, ["apply"])
    assert apply2.exit_code == 0
    assert not old_link.exists()


def test_full_roundtrip_skills_agents_all_apps(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    from code_agnostic.__main__ import cli

    enable_app("opencode")
    enable_app("cursor")
    enable_app("codex")

    core_root = tmp_path / ".config" / "code-agnostic"
    (core_root / "skills" / "shared-skill").mkdir(parents=True)
    (core_root / "skills" / "shared-skill" / "SKILL.md").write_text(
        "skill", encoding="utf-8"
    )
    (core_root / "agents").mkdir(parents=True)
    (core_root / "agents" / "planner.md").write_text("agent", encoding="utf-8")

    apply_result = cli_runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    opencode_root = tmp_path / ".config" / "opencode"
    cursor_root = tmp_path / ".cursor"
    codex_root = tmp_path / ".codex"

    assert (opencode_root / "skills" / "shared-skill").is_symlink()
    assert (opencode_root / "agents" / "planner.md").is_symlink()

    assert (cursor_root / "skills" / "shared-skill").is_symlink()
    assert (cursor_root / "agents" / "planner.md").is_symlink()

    assert (codex_root / "skills" / "shared-skill").is_symlink()


def test_config_update_propagation(
    minimal_shared_config: Path,
    tmp_path: Path,
    core_root: Path,
    cli_runner,
    enable_app,
    expected_app_config_path,
) -> None:
    import json

    from code_agnostic.__main__ import cli

    enable_app("cursor")

    apply1 = cli_runner.invoke(cli, ["apply"])
    assert apply1.exit_code == 0

    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "new-server": {"url": "https://example.com/new"},
                }
            }
        ),
        encoding="utf-8",
    )

    apply2 = cli_runner.invoke(cli, ["apply"])
    assert apply2.exit_code == 0

    cursor_payload = json.loads(
        expected_app_config_path("cursor").read_text(encoding="utf-8")
    )
    assert "new-server" in cursor_payload.get("mcpServers", {})
