from pathlib import Path

from code_agnostic.workspaces import WorkspaceService


def test_list_workspace_repos_finds_git_subdirectories(tmp_path: Path) -> None:
    workspace_service = WorkspaceService()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "repo-one" / ".git").mkdir(parents=True)
    (workspace / "nested" / "repo-two" / ".git").mkdir(parents=True)
    (workspace / "not-a-repo").mkdir()

    repos = workspace_service.discover_git_repos(workspace)

    assert repos == [
        (workspace / "nested" / "repo-two").resolve(),
        (workspace / "repo-one").resolve(),
    ]


def test_discover_git_repos_skips_dotfile_dirs(tmp_path: Path) -> None:
    workspace_service = WorkspaceService()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / ".hidden" / ".git").mkdir(parents=True)
    (workspace / "visible" / ".git").mkdir(parents=True)

    repos = workspace_service.discover_git_repos(workspace)

    repo_names = [r.name for r in repos]
    assert "visible" in repo_names
    assert ".hidden" not in repo_names


def test_discover_git_repos_skips_ignored_dirs(tmp_path: Path) -> None:
    workspace_service = WorkspaceService()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "node_modules" / "pkg" / ".git").mkdir(parents=True)
    (workspace / ".venv" / "lib" / ".git").mkdir(parents=True)
    (workspace / "real-repo" / ".git").mkdir(parents=True)

    repos = workspace_service.discover_git_repos(workspace)

    repo_names = [r.name for r in repos]
    assert "real-repo" in repo_names
    assert "pkg" not in repo_names
    assert "lib" not in repo_names


def test_discover_git_repos_empty_workspace(tmp_path: Path) -> None:
    workspace_service = WorkspaceService()
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    repos = workspace_service.discover_git_repos(workspace)

    assert repos == []


def test_discover_git_repos_stops_at_nested_git(tmp_path: Path) -> None:
    workspace_service = WorkspaceService()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "outer" / ".git").mkdir(parents=True)
    (workspace / "outer" / "inner" / ".git").mkdir(parents=True)

    repos = workspace_service.discover_git_repos(workspace)

    repo_names = [r.name for r in repos]
    assert "outer" in repo_names
    assert "inner" not in repo_names
