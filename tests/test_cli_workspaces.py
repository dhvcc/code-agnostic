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
        cli,
        [
            "workspaces",
            "add",
            "--name",
            "workspace-example",
            "--path",
            str(workspace_root),
        ],
    )
    assert add_result.exit_code == 0
    assert "Workspace added: workspace-example" in add_result.output

    list_result = cli_runner.invoke(cli, ["workspaces", "list"])
    assert list_result.exit_code == 0
    assert "workspace-example" in list_result.output
    assert "repo-a" in list_result.output

    remove_result = cli_runner.invoke(
        cli, ["workspaces", "remove", "--name", "workspace-example"]
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

    result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "broken", "--path", str(missing_path)]
    )

    assert result.exit_code != 0
    assert "does not exist or is not a directory" in result.output


def test_workspaces_remove_nonexistent(minimal_shared_config: Path, cli_runner) -> None:
    result = cli_runner.invoke(cli, ["workspaces", "remove", "--name", "ghost"])

    assert result.exit_code != 0
    assert "Workspace not found" in result.output


def test_workspaces_add_empty_name(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()

    result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "", "--path", str(workspace_root)]
    )

    assert result.exit_code != 0
    assert "empty" in result.output.lower()


def test_workspaces_add_duplicate_name(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    ws1 = tmp_path / "ws1"
    ws1.mkdir()
    ws2 = tmp_path / "ws2"
    ws2.mkdir()

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "myws", "--path", str(ws1)]
    )
    assert add_result.exit_code == 0

    dup_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "myws", "--path", str(ws2)]
    )
    assert dup_result.exit_code != 0
    assert "already exists" in dup_result.output


def test_workspaces_add_duplicate_path(
    minimal_shared_config: Path, tmp_path: Path, cli_runner
) -> None:
    ws1 = tmp_path / "ws1"
    ws1.mkdir()

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "first", "--path", str(ws1)]
    )
    assert add_result.exit_code == 0

    dup_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "second", "--path", str(ws1)]
    )
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
        cli, ["workspaces", "add", "--name", "myws", "--path", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    list_result = cli_runner.invoke(cli, ["workspaces", "list"])
    assert list_result.exit_code == 0
    assert "myws" in list_result.output


def test_workspaces_git_exclude_writes_enabled_apps_and_default_rules(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    workspace_root = tmp_path / "corp-ws"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git" / "info").mkdir(parents=True)
    (workspace_root / "repo-b" / ".git" / "info").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "corp", "--path", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    enable_app("cursor")

    result = cli_runner.invoke(cli, ["workspaces", "git-exclude"])
    assert result.exit_code == 0
    assert "Updated git excludes" in result.output

    expected_entries = ["AGENTS.md", "CLAUDE.md"]
    unexpected_entries = [".opencode", ".codex"]

    for repo_name in ["repo-a", "repo-b"]:
        exclude = workspace_root / repo_name / ".git" / "info" / "exclude"
        content = exclude.read_text(encoding="utf-8")
        for item in expected_entries:
            assert item in content
        for item in unexpected_entries:
            assert item not in content


def test_workspaces_git_exclude_can_target_single_workspace(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    ws_a = tmp_path / "ws-a"
    ws_b = tmp_path / "ws-b"
    ws_a.mkdir()
    ws_b.mkdir()
    (ws_a / "repo-a" / ".git" / "info").mkdir(parents=True)
    (ws_b / "repo-b" / ".git" / "info").mkdir(parents=True)

    assert (
        cli_runner.invoke(
            cli, ["workspaces", "add", "--name", "a", "--path", str(ws_a)]
        ).exit_code
        == 0
    )
    assert (
        cli_runner.invoke(
            cli, ["workspaces", "add", "--name", "b", "--path", str(ws_b)]
        ).exit_code
        == 0
    )

    enable_app("cursor")

    result = cli_runner.invoke(cli, ["workspaces", "git-exclude", "-w", "a"])
    assert result.exit_code == 0

    exclude_a = ws_a / "repo-a" / ".git" / "info" / "exclude"
    exclude_b = ws_b / "repo-b" / ".git" / "info" / "exclude"

    assert ".cursor" in exclude_a.read_text(encoding="utf-8")
    assert not exclude_b.exists()


def test_workspaces_git_exclude_preserves_existing_file_content(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    workspace_root = tmp_path / "corp-ws"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git" / "info").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "corp", "--path", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    enable_app("codex")

    exclude = workspace_root / "repo-a" / ".git" / "info" / "exclude"
    exclude.write_text("# existing comment\nbuild/\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["workspaces", "git-exclude"])
    assert result.exit_code == 0

    content = exclude.read_text(encoding="utf-8").splitlines()
    assert content[:2] == ["# existing comment", "build/"]
    assert ".codex" in content
    assert "AGENTS.md" in content
    assert "CLAUDE.md" in content


def test_workspaces_git_exclude_does_not_duplicate_existing_entries(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    workspace_root = tmp_path / "corp-ws"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git" / "info").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "corp", "--path", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    enable_app("codex")

    exclude = workspace_root / "repo-a" / ".git" / "info" / "exclude"
    exclude.write_text(" .codex \nAGENTS.md\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["workspaces", "git-exclude"])
    assert result.exit_code == 0
    assert "lines_added=1" in result.output

    content = exclude.read_text(encoding="utf-8")
    assert content.count(".codex") == 1
    assert content.count("AGENTS.md") == 1
    assert content.count("CLAUDE.md") == 1


def test_workspaces_git_exclude_supports_git_file_repos(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    workspace_root = tmp_path / "corp-ws"
    workspace_root.mkdir()
    repo = workspace_root / "repo-a"
    repo.mkdir()

    git_dir = tmp_path / "gitdirs" / "repo-a"
    (git_dir / "info").mkdir(parents=True)
    (repo / ".git").write_text(f"gitdir: {git_dir}\n", encoding="utf-8")

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "corp", "--path", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    enable_app("codex")

    exclude = git_dir / "info" / "exclude"
    exclude.write_text("# existing\nbuild/\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["workspaces", "git-exclude"])
    assert result.exit_code == 0

    content = exclude.read_text(encoding="utf-8").splitlines()
    assert content[:2] == ["# existing", "build/"]
    assert ".codex" in content
    assert "AGENTS.md" in content
    assert "CLAUDE.md" in content
