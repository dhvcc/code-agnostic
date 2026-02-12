from pathlib import Path

from click.testing import CliRunner

from llm_sync.__main__ import cli
from llm_sync.constants import AGENTS_FILENAME


def test_status_reports_editor_and_workspace_repo_sync(minimal_shared_config: Path, tmp_path: Path) -> None:
    runner = CliRunner()

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / AGENTS_FILENAME).write_text("workspace rules", encoding="utf-8")
    (workspace_root / "service-api" / ".git").mkdir(parents=True)
    (workspace_root / "service-web" / ".git").mkdir(parents=True)
    (workspace_root / "notes").mkdir()

    add_result = runner.invoke(cli, ["workspaces", "add", "workspace-example", str(workspace_root)])
    assert add_result.exit_code == 0

    initial_status = runner.invoke(cli, ["status"])
    assert initial_status.exit_code == 0
    assert "opencode" in initial_status.output
    assert "drift" in initial_status.output
    assert "workspace-example" in initial_status.output
    assert "service-api" in initial_status.output
    assert "service-web" in initial_status.output
    assert "notes" not in initial_status.output
    assert "needs sync" in initial_status.output

    apply_result = runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    synced_status = runner.invoke(cli, ["status"])
    assert synced_status.exit_code == 0
    assert "opencode" in synced_status.output
    assert "synced" in synced_status.output
    assert "service-api" in synced_status.output
    assert "service-web" in synced_status.output
