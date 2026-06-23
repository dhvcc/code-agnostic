from pathlib import Path

from code_agnostic.__main__ import cli
from code_agnostic.apps.apps_service import AppsService
from code_agnostic.core.repository import CoreRepository
from code_agnostic.models import ActionKind


def test_plan_shows_invalid_json_error_for_mcp_base(
    minimal_shared_config: Path, core_root: Path, cli_runner, enable_app
) -> None:
    enable_app("opencode")
    (core_root / "config" / "mcp.base.json").write_text("{bad", encoding="utf-8")

    result = cli_runner.invoke(cli, ["plan"])

    assert result.exit_code != 0
    assert "Invalid JSON format" in result.output


def test_plan_target_cursor_includes_workspace_mcp_and_skills(
    minimal_shared_config: Path,
    tmp_path: Path,
    core_root: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")

    workspace_root = tmp_path / "team-workspace"
    workspace_root.mkdir()
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "team", "--path", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    ws_config_dir = core_root / "workspaces" / "team"
    (ws_config_dir / "mcp.base.json").write_text(
        '{"mcpServers":{"team-context":{"command":"node","args":["server.js"]}}}',
        encoding="utf-8",
    )
    (ws_config_dir / "skills" / "review").mkdir(parents=True, exist_ok=True)
    (ws_config_dir / "skills" / "review" / "SKILL.md").write_text(
        "Review skill\n", encoding="utf-8"
    )
    (ws_config_dir / "rules").mkdir(parents=True, exist_ok=True)
    (ws_config_dir / "rules" / "shared.md").write_text("rules", encoding="utf-8")

    core = CoreRepository(core_root)
    plan = AppsService(core).plan_for_target("cursor")
    scopes = {a.scope for a in plan.actions}
    assert any(
        a.kind == ActionKind.WRITE_TEXT and a.scope == "rules" for a in plan.actions
    )
    assert "ws:cursor:workspace_root_mcp" in scopes
    assert "ws:cursor:repo_mcp" in scopes
    assert "ws:cursor:workspace_root_skills_dir" in scopes
    assert "ws:cursor:repo_skills_dir" in scopes

    plan_result = cli_runner.invoke(cli, ["plan", "-a", "cursor"])
    assert plan_result.exit_code == 0
    assert "cursor" in plan_result.output
    assert "workspace config sync" in plan_result.output


def test_plan_with_no_apps_enabled(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["plan"])

    assert result.exit_code == 0
    assert "code-agnostic apps enable -a <app>" in result.output
    assert "code-agnostic plan -a <app>" in result.output
    assert "code-agnostic apply -a <app>" in result.output


def test_plan_target_opencode_when_not_enabled(
    minimal_shared_config: Path, cli_runner
) -> None:
    result = cli_runner.invoke(cli, ["plan", "-a", "opencode"])

    assert result.exit_code == 0
    assert "code-agnostic apps enable -a opencode" in result.output
    assert "code-agnostic plan -a opencode" in result.output
    assert "code-agnostic apply -a opencode" in result.output


def test_plan_target_copilot_when_not_enabled_uses_label_and_cli_id(
    minimal_shared_config: Path, cli_runner
) -> None:
    result = cli_runner.invoke(cli, ["plan", "-a", "copilot"])

    assert result.exit_code == 0
    assert "Enable GitHub Copilot (copilot)" in result.output
    assert "code-agnostic apps enable -a copilot" in result.output
    assert "code-agnostic plan -a copilot" in result.output
    assert "code-agnostic apply -a copilot" in result.output


def test_plan_target_enabled_app_shows_scoped_apply_next_step(
    minimal_shared_config: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")

    result = cli_runner.invoke(cli, ["plan", "-a", "cursor"])

    assert result.exit_code == 0
    assert "Review the planned changes" in result.output
    assert "code-agnostic apply -a cursor" in result.output
    assert "code-agnostic apps enable -a <app>" not in result.output


def test_plan_missing_mcp_base_json(tmp_path: Path, cli_runner, enable_app) -> None:
    core_root = tmp_path / ".config" / "code-agnostic"
    core_root.mkdir(parents=True, exist_ok=True)

    result = cli_runner.invoke(cli, ["plan"])

    assert result.exit_code == 0


def test_plan_default_view_shows_app_labels_not_paths(
    minimal_shared_config: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")

    result = cli_runner.invoke(cli, ["plan", "-a", "cursor"])

    assert result.exit_code == 0
    assert "Code Agnostic" in result.output
    assert "Cursor" in result.output
    assert "Source Path" not in result.output
    assert "Target Path" not in result.output


def test_plan_verbose_view_shows_path_columns_with_home_shorthand(
    minimal_shared_config: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")

    result = cli_runner.invoke(cli, ["plan", "-a", "cursor", "-v"])

    assert result.exit_code == 0
    assert "Path" in result.output
    assert "~/" in result.output
