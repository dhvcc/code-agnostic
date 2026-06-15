from pathlib import Path

from code_agnostic.__main__ import cli
from code_agnostic.cli.commands.apply import _apply_next_steps
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan


def test_apps_list_shows_all_disabled_by_default(
    minimal_shared_config, cli_runner
) -> None:
    result = cli_runner.invoke(cli, ["apps", "list"])

    assert result.exit_code == 0
    assert "opencode" in result.output
    assert "cursor" in result.output
    assert "codex" in result.output
    assert "disabled" in result.output


def test_apps_enable_and_disable_updates_state(
    minimal_shared_config, cli_runner
) -> None:
    enable_result = cli_runner.invoke(cli, ["apps", "enable", "-a", "opencode"])
    assert enable_result.exit_code == 0
    assert "code-agnostic plan -a opencode" in enable_result.output
    assert "code-agnostic apply -a opencode" in enable_result.output

    list_after_enable = cli_runner.invoke(cli, ["apps", "list"])
    assert list_after_enable.exit_code == 0
    assert "opencode" in list_after_enable.output
    assert "enabled" in list_after_enable.output

    disable_result = cli_runner.invoke(cli, ["apps", "disable", "-a", "opencode"])
    assert disable_result.exit_code == 0

    list_after_disable = cli_runner.invoke(cli, ["apps", "list"])
    assert list_after_disable.exit_code == 0
    assert "opencode" in list_after_disable.output
    assert "disabled" in list_after_disable.output


def test_apply_skips_when_no_apps_enabled(minimal_shared_config, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["apply"])

    assert result.exit_code == 0
    assert "No apps enabled" in result.output


def test_apply_syncs_enabled_cursor_app(
    minimal_shared_config, cli_runner, tmp_path
) -> None:
    enable_cursor = cli_runner.invoke(cli, ["apps", "enable", "-a", "cursor"])
    assert enable_cursor.exit_code == 0

    result = cli_runner.invoke(cli, ["apply"])

    assert result.exit_code == 0
    assert "cursor" in result.output
    assert "code-agnostic status" in result.output
    assert "code-agnostic restore" in result.output
    assert (tmp_path / ".cursor" / "mcp.json").exists()


def test_apply_next_steps_offer_project_restore_for_project_outputs() -> None:
    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=Path("/tmp/project/.agents/skills/review/SKILL.md"),
                status=ActionStatus.CREATE,
                detail="create compiled codex skill",
                payload="review\n",
                scope="project:demo:codex:skills",
                app="codex",
                project="demo",
            )
        ],
        errors=[],
        skipped=[],
    )

    next_steps = _apply_next_steps(plan, "codex")

    assert next_steps is not None
    assert "code-agnostic status -a codex" in next_steps
    assert "- code-agnostic restore\n" not in f"{next_steps}\n"
    assert "- code-agnostic restore --project demo" in next_steps
    assert "project restore is not available yet" not in next_steps


def test_status_reports_cursor_enabled_and_sync_state(
    minimal_shared_config, cli_runner
) -> None:
    enable_cursor = cli_runner.invoke(cli, ["apps", "enable", "-a", "cursor"])
    assert enable_cursor.exit_code == 0

    drift_result = cli_runner.invoke(cli, ["status"])
    assert drift_result.exit_code == 0
    assert "cursor" in drift_result.output
    assert "drift" in drift_result.output

    apply_result = cli_runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    result = cli_runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "cursor" in result.output
    assert "synced" in result.output


def test_core_app_is_hidden_from_app_management_commands(
    minimal_shared_config, cli_runner
) -> None:
    list_result = cli_runner.invoke(cli, ["apps", "list"])
    assert list_result.exit_code == 0
    assert "core" not in list_result.output.lower()

    enable_result = cli_runner.invoke(cli, ["apps", "enable", "-a", "core"])
    assert enable_result.exit_code != 0
    assert "invalid value" in enable_result.output.lower()
