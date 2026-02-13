from pathlib import Path

from code_agnostic.__main__ import cli
from code_agnostic.constants import AGENTS_FILENAME


def test_plan_shows_invalid_json_error_for_mcp_base(
    minimal_shared_config: Path, core_root: Path, cli_runner, enable_app
) -> None:
    enable_app("opencode")
    (core_root / "config" / "mcp.base.json").write_text("{bad", encoding="utf-8")

    result = cli_runner.invoke(cli, ["plan"])

    assert result.exit_code != 0
    assert "Invalid JSON format" in result.output


def test_plan_target_cursor_includes_workspace_actions(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")

    workspace_root = tmp_path / "team-workspace"
    workspace_root.mkdir()
    (workspace_root / AGENTS_FILENAME).write_text("rules", encoding="utf-8")
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "team", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    plan_result = cli_runner.invoke(cli, ["plan", "cursor"])
    assert plan_result.exit_code == 0
    assert "cursor" in plan_result.output
    assert "workspace links" in plan_result.output
