from pathlib import Path

from code_agnostic.__main__ import cli
from code_agnostic.constants import AGENTS_FILENAME


def test_workspaces_add_list_remove_commands(
    tmp_path: Path, minimal_shared_config: Path, cli_runner
) -> None:
    workspace_root = tmp_path / "example-workspace"
    workspace_root.mkdir()
    (workspace_root / AGENTS_FILENAME).write_text("rules", encoding="utf-8")
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "workspace-example", str(workspace_root)]
    )
    assert add_result.exit_code == 0
    assert "Workspace added: workspace-example" in add_result.output

    list_result = cli_runner.invoke(cli, ["workspaces", "list"])
    assert list_result.exit_code == 0
    assert "workspace-example" in list_result.output
    assert "repo-a" in list_result.output

    remove_result = cli_runner.invoke(
        cli, ["workspaces", "remove", "workspace-example"]
    )
    assert remove_result.exit_code == 0
    assert "Workspace removed: workspace-example" in remove_result.output

    list_after_remove = cli_runner.invoke(cli, ["workspaces", "list"])
    assert list_after_remove.exit_code == 0
    assert "No workspaces configured" in list_after_remove.output


def test_workspaces_add_rejects_missing_path(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    missing_path = tmp_path / "does-not-exist"

    result = cli_runner.invoke(cli, ["workspaces", "add", "broken", str(missing_path)])

    assert result.exit_code != 0
    assert "does not exist or is not a directory" in result.output


def test_workspaces_remove_nonexistent(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["workspaces", "remove", "ghost"])

    assert result.exit_code != 0
    assert "Workspace not found" in result.output


def test_workspaces_add_empty_name(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()

    result = cli_runner.invoke(cli, ["workspaces", "add", "", str(workspace_root)])

    assert result.exit_code != 0
    assert "empty" in result.output.lower()


def test_workspaces_add_duplicate_name(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    ws1 = tmp_path / "ws1"
    ws1.mkdir()
    ws2 = tmp_path / "ws2"
    ws2.mkdir()

    add_result = cli_runner.invoke(cli, ["workspaces", "add", "myws", str(ws1)])
    assert add_result.exit_code == 0

    dup_result = cli_runner.invoke(cli, ["workspaces", "add", "myws", str(ws2)])
    assert dup_result.exit_code != 0
    assert "already exists" in dup_result.output


def test_workspaces_add_duplicate_path(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    ws1 = tmp_path / "ws1"
    ws1.mkdir()

    add_result = cli_runner.invoke(cli, ["workspaces", "add", "first", str(ws1)])
    assert add_result.exit_code == 0

    dup_result = cli_runner.invoke(cli, ["workspaces", "add", "second", str(ws1)])
    assert dup_result.exit_code != 0
    assert "already exists" in dup_result.output


def test_workspaces_list_with_inaccessible_path(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    (workspace_root / AGENTS_FILENAME).write_text("rules", encoding="utf-8")
    (workspace_root / "repo" / ".git").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "myws", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    list_result = cli_runner.invoke(cli, ["workspaces", "list"])
    assert list_result.exit_code == 0
    assert "myws" in list_result.output
