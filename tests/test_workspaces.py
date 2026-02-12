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
