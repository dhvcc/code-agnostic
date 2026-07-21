"""P0-3: `apps disable` cleans up everything the app previously synced (compiled
skills/agents and the MCP servers we own) and clears the tracked state, instead
of stranding orphans on disk."""

import json
from pathlib import Path

from code_agnostic.__main__ import cli
from code_agnostic.core.repository import CoreRepository


def _write_skill(core_root: Path, name: str) -> None:
    skill = core_root / "skills" / name / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        f"---\nname: {name}\ndescription: {name} skill\n---\n\nDo {name}.\n",
        encoding="utf-8",
    )


def test_disable_cursor_removes_skill_and_prunes_owned_mcp(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")
    _write_skill(core_root, "reviewer")
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps({"mcpServers": {"team": {"command": "uvx", "args": ["team"]}}}),
        encoding="utf-8",
    )
    # User's own server, added directly.
    (tmp_path / ".cursor").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".cursor" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"personal": {"url": "https://p/mcp"}}}),
        encoding="utf-8",
    )

    assert cli_runner.invoke(cli, ["apply", "-a", "cursor"]).exit_code == 0

    skill_file = tmp_path / ".cursor" / "skills" / "reviewer" / "SKILL.md"
    mcp_file = tmp_path / ".cursor" / "mcp.json"
    assert skill_file.exists()
    assert set(json.loads(mcp_file.read_text())["mcpServers"]) == {"personal", "team"}

    state = json.loads((core_root / ".sync-state.json").read_text())
    assert state["managed_mcp"]["app:cursor:mcp"] == ["team"]
    assert any(
        scope.startswith("app:cursor:") for scope in state.get("managed_paths", {})
    )

    # Disable → everything cursor-synced must be reclaimed.
    result = cli_runner.invoke(cli, ["apps", "disable", "-a", "cursor"])
    assert result.exit_code == 0

    assert not skill_file.exists(), "compiled skill must be removed on disable"
    remaining = json.loads(mcp_file.read_text())["mcpServers"]
    assert set(remaining) == {"personal"}, "our server pruned, user's kept"

    state = json.loads((core_root / ".sync-state.json").read_text())
    assert not any(
        scope.startswith("app:cursor:") for scope in state.get("managed_paths", {})
    ), "cursor state must be cleared after disable"
    assert "app:cursor:mcp" not in state.get("managed_mcp", {})

    # Flag is off.
    apps_cfg = json.loads((core_root / "config" / "apps.json").read_text())
    assert apps_cfg["cursor"] is False


def test_disable_claude_prunes_project_mcp_keeps_user_project(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("claude")
    workspace_root = tmp_path / "workspace"
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    core = CoreRepository(core_root)
    core.add_workspace("myws", workspace_root)
    (core.workspace_config_dir("myws") / "mcp.base.json").write_text(
        json.dumps({"mcpServers": {"ws-server": {"url": "https://example.com/mcp"}}}),
        encoding="utf-8",
    )

    # User's own project entry — must survive disable untouched.
    config_path = tmp_path / ".claude.json"
    user_project = str((tmp_path / "user-repo").resolve())
    config_path.write_text(
        json.dumps(
            {"projects": {user_project: {"mcpServers": {"personal": {"type": "http"}}}}}
        ),
        encoding="utf-8",
    )

    assert cli_runner.invoke(cli, ["apply", "-a", "claude"]).exit_code == 0

    projects = json.loads(config_path.read_text())["projects"]
    repo_key = str((workspace_root / "repo-a").resolve())
    assert "mcpServers" in projects[repo_key]
    state = json.loads((core_root / ".sync-state.json").read_text())
    assert repo_key in state["managed_mcp"]["app:claude:projects"]

    # Disable → our project mcpServers pruned, user's project kept.
    assert cli_runner.invoke(cli, ["apps", "disable", "-a", "claude"]).exit_code == 0

    projects = json.loads(config_path.read_text())["projects"]
    assert "mcpServers" not in projects.get(repo_key, {})
    assert projects[user_project] == {"mcpServers": {"personal": {"type": "http"}}}

    state = json.loads((core_root / ".sync-state.json").read_text())
    assert "app:claude:projects" not in state.get("managed_mcp", {})
