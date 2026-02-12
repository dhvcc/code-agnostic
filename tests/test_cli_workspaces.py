from pathlib import Path

from click.testing import CliRunner

from llm_sync.cli import cli


def test_workspaces_add_list_remove_commands(tmp_path: Path, minimal_shared_config: Path) -> None:
    runner = CliRunner()

    workspace_root = tmp_path / "example-workspace"
    workspace_root.mkdir()
    (workspace_root / "AGENTS.md").write_text("rules", encoding="utf-8")
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    add_result = runner.invoke(cli, ["workspaces", "add", "workspace-example", str(workspace_root)])
    assert add_result.exit_code == 0
    assert "Workspace added: workspace-example" in add_result.output

    list_result = runner.invoke(cli, ["workspaces", "list"])
    assert list_result.exit_code == 0
    assert "workspace-example" in list_result.output
    assert "repo-a" in list_result.output

    remove_result = runner.invoke(cli, ["workspaces", "remove", "workspace-example"])
    assert remove_result.exit_code == 0
    assert "Workspace removed: workspace-example" in remove_result.output

    list_after_remove = runner.invoke(cli, ["workspaces", "list"])
    assert list_after_remove.exit_code == 0
    assert "No workspaces configured" in list_after_remove.output
