from pathlib import Path

from llm_sync.workspaces import list_workspace_repos, resolve_workspace_rules_file


def test_resolve_workspace_rules_prefers_agents_md(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    agents = workspace / "AGENTS.md"
    claude = workspace / "CLAUDE.md"
    agents.write_text("agents", encoding="utf-8")
    claude.write_text("claude", encoding="utf-8")

    resolved = resolve_workspace_rules_file(workspace)

    assert resolved == agents


def test_list_workspace_repos_finds_git_subdirectories(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "repo-one" / ".git").mkdir(parents=True)
    (workspace / "nested" / "repo-two" / ".git").mkdir(parents=True)
    (workspace / "not-a-repo").mkdir()

    repos = list_workspace_repos(workspace)

    assert repos == [
        (workspace / "nested" / "repo-two").resolve(),
        (workspace / "repo-one").resolve(),
    ]
