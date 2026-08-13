import json
from pathlib import Path

from code_agnostic.__main__ import cli
from code_agnostic.core.repository import CoreRepository


def _write_skill(root: Path, name: str) -> None:
    skill = root / "skills" / name / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        f"---\nname: {name}\ndescription: {name} skill\n---\n\nUse {name}.\n",
        encoding="utf-8",
    )


def _write_user_skill(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("user skill\n", encoding="utf-8")


def test_bare_apply_reclaims_outputs_after_apps_config_disable(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
    write_json,
) -> None:
    enable_app("cursor")
    _write_skill(core_root, "global-owned")
    write_json(
        core_root / "config" / "mcp.base.json",
        {"mcpServers": {"managed-global": {"url": "https://global.example/mcp"}}},
    )

    global_mcp = tmp_path / ".cursor" / "mcp.json"
    write_json(
        global_mcp,
        {"mcpServers": {"personal": {"url": "https://personal.example/mcp"}}},
    )
    global_user_skill = tmp_path / ".cursor" / "skills" / "user" / "SKILL.md"
    _write_user_skill(global_user_skill)

    workspace_root = tmp_path / "workspace"
    repo_root = workspace_root / "repo"
    (repo_root / ".git").mkdir(parents=True)
    CoreRepository(core_root).add_workspace("team", workspace_root)
    ws_config = core_root / "workspaces" / "team"
    _write_skill(ws_config, "workspace-owned")
    write_json(
        ws_config / "mcp.base.json",
        {"mcpServers": {"managed-workspace": {"url": "https://workspace.example/mcp"}}},
    )
    workspace_user_skill = workspace_root / ".cursor" / "skills" / "user" / "SKILL.md"
    repo_user_skill = repo_root / ".cursor" / "skills" / "user" / "SKILL.md"
    _write_user_skill(workspace_user_skill)
    _write_user_skill(repo_user_skill)

    project_root = tmp_path / "project"
    project_root.mkdir()
    CoreRepository(core_root).add_project("service", project_root)
    project_config = core_root / "projects" / "service"
    _write_skill(project_config, "project-owned")
    write_json(
        project_config / "mcp.base.json",
        {"mcpServers": {"managed-project": {"url": "https://project.example/mcp"}}},
    )
    project_user_skill = project_root / ".cursor" / "skills" / "user" / "SKILL.md"
    _write_user_skill(project_user_skill)

    initial_apply = cli_runner.invoke(cli, ["apply"])
    assert initial_apply.exit_code == 0, initial_apply.output

    global_owned = tmp_path / ".cursor" / "skills" / "global-owned" / "SKILL.md"
    workspace_owned = (
        workspace_root / ".cursor" / "skills" / "workspace-owned" / "SKILL.md"
    )
    repo_owned = repo_root / ".cursor" / "skills" / "workspace-owned" / "SKILL.md"
    project_owned = project_root / ".cursor" / "skills" / "project-owned" / "SKILL.md"
    workspace_mcp = workspace_root / ".cursor" / "mcp.json"
    repo_mcp = repo_root / ".cursor" / "mcp.json"
    assert all(
        path.exists()
        for path in (
            global_owned,
            workspace_owned,
            repo_owned,
            project_owned,
            workspace_mcp,
            repo_mcp,
        )
    ), initial_apply.output

    apps_path = core_root / "config" / "apps.json"
    apps = json.loads(apps_path.read_text(encoding="utf-8"))
    apps["cursor"] = False
    apps_path.write_text(json.dumps(apps), encoding="utf-8")

    plan = cli_runner.invoke(cli, ["plan"])
    assert plan.exit_code == 0, plan.output
    assert "remove" in plan.output
    assert "workspace config sync" in plan.output
    assert "project config sync" in plan.output

    cleanup = cli_runner.invoke(cli, ["apply"])
    assert cleanup.exit_code == 0, cleanup.output

    assert not any(
        path.exists()
        for path in (
            global_owned,
            workspace_owned,
            repo_owned,
            project_owned,
            workspace_mcp,
            repo_mcp,
        )
    )
    assert all(
        path.exists()
        for path in (
            global_user_skill,
            workspace_user_skill,
            repo_user_skill,
            project_user_skill,
        )
    )
    assert set(json.loads(global_mcp.read_text(encoding="utf-8"))["mcpServers"]) == {
        "personal"
    }

    for state_path, prefix in (
        (core_root / ".sync-state.json", "app:cursor:"),
        (core_root / "workspaces" / "team" / ".sync-state.json", "ws:cursor:"),
        (core_root / "projects" / "service" / ".sync-state.json", "project:cursor:"),
    ):
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert not any(
            scope.startswith(prefix)
            for group in ("managed_links", "managed_paths", "managed_mcp")
            for scope in state.get(group, {})
        )
