from pathlib import Path

from code_agnostic.__main__ import cli
from code_agnostic.constants import AGENTS_FILENAME


def test_status_reports_editor_and_workspace_repo_sync(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path, cli_runner, enable_app
) -> None:
    enable_app("opencode")

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / "service-api" / ".git").mkdir(parents=True)
    (workspace_root / "service-web" / ".git").mkdir(parents=True)
    (workspace_root / "notes").mkdir()

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "workspace-example", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    ws_config_dir = core_root / "workspaces" / "workspace-example"
    (ws_config_dir / AGENTS_FILENAME).write_text("workspace rules", encoding="utf-8")

    initial_status = cli_runner.invoke(cli, ["status"])
    assert initial_status.exit_code == 0
    assert "opencode" in initial_status.output
    assert "drift" in initial_status.output
    assert "workspace-example" in initial_status.output
    assert "service-api" in initial_status.output
    assert "service-web" in initial_status.output
    assert "notes" not in initial_status.output
    assert "needs sync" in initial_status.output

    apply_result = cli_runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    synced_status = cli_runner.invoke(cli, ["status"])
    assert synced_status.exit_code == 0
    assert "opencode" in synced_status.output
    assert "synced" in synced_status.output
    assert "service-api" in synced_status.output
    assert "service-web" in synced_status.output


def test_status_can_scope_to_single_app(
    minimal_shared_config: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")

    result = cli_runner.invoke(cli, ["status", "cursor"])

    assert result.exit_code == 0
    assert "cursor" in result.output
    assert "opencode" not in result.output
