from pathlib import Path

from code_agnostic.constants import AGENTS_FILENAME, CLAUDE_FILENAME
from code_agnostic.workspaces import WorkspaceService


def test_resolve_workspace_rules_prefers_agents_md(tmp_path: Path) -> None:
    workspace_service = WorkspaceService()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agents = workspace / AGENTS_FILENAME
    claude = workspace / CLAUDE_FILENAME
    agents.write_text("agents", encoding="utf-8")
    claude.write_text("claude", encoding="utf-8")

    resolved = workspace_service.resolve_rules_file(workspace)

    assert resolved == agents


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


def test_resolve_rules_file_none_when_no_rules(tmp_path: Path) -> None:
    workspace_service = WorkspaceService()
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    resolved = workspace_service.resolve_rules_file(workspace)

    assert resolved is None


def test_resolve_rules_file_claude_md_fallback(tmp_path: Path) -> None:
    workspace_service = WorkspaceService()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    claude = workspace / CLAUDE_FILENAME
    claude.write_text("claude rules", encoding="utf-8")

    resolved = workspace_service.resolve_rules_file(workspace)

    assert resolved == claude


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


def test_workspace_sync_targets_with_rules_none(tmp_path: Path) -> None:
    workspace_service = WorkspaceService()
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    targets = workspace_service.workspace_sync_targets(workspace, rules_file=None)

    assert targets == []


def test_workspace_sync_targets_with_rules_file(tmp_path: Path) -> None:
    workspace_service = WorkspaceService()
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    rules = workspace / AGENTS_FILENAME
    rules.write_text("rules", encoding="utf-8")
    (workspace / "repo-a" / ".git").mkdir(parents=True)

    targets = workspace_service.workspace_sync_targets(workspace, rules_file=rules)

    assert len(targets) == 1
    assert targets[0].name == AGENTS_FILENAME
