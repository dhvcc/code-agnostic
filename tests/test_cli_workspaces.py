from pathlib import Path

from llm_sync.__main__ import cli
from llm_sync.constants import AGENTS_FILENAME


def test_workspaces_add_list_remove_commands(tmp_path: Path, minimal_shared_config: Path, cli_runner) -> None:

    workspace_root = tmp_path / "example-workspace"
    workspace_root.mkdir()
    (workspace_root / AGENTS_FILENAME).write_text("rules", encoding="utf-8")
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    add_result = cli_runner.invoke(cli, ["workspaces", "add", "workspace-example", str(workspace_root)])
    assert add_result.exit_code == 0
    assert "Workspace added: workspace-example" in add_result.output

    list_result = cli_runner.invoke(cli, ["workspaces", "list"])
    assert list_result.exit_code == 0
    assert "workspace-example" in list_result.output
    assert "repo-a" in list_result.output

    remove_result = cli_runner.invoke(cli, ["workspaces", "remove", "workspace-example"])
    assert remove_result.exit_code == 0
    assert "Workspace removed: workspace-example" in remove_result.output

    list_after_remove = cli_runner.invoke(cli, ["workspaces", "list"])
    assert list_after_remove.exit_code == 0
    assert "No workspaces configured" in list_after_remove.output


def test_workspaces_add_rejects_missing_path(minimal_shared_config: Path, tmp_path: Path, cli_runner) -> None:
    missing_path = tmp_path / "does-not-exist"

    result = cli_runner.invoke(cli, ["workspaces", "add", "broken", str(missing_path)])

    assert result.exit_code != 0
    assert "does not exist or is not a directory" in result.output
