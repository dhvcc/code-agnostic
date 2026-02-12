from pathlib import Path
import json

from llm_sync.executor import execute_apply
from llm_sync.planner import build_plan
from llm_sync.repositories.common import CommonRepository
from llm_sync.repositories.opencode import OpenCodeRepository


def test_build_plan_and_apply_create_opencode_and_workspace_links(
    tmp_path: Path,
    common_root: Path,
    opencode_root: Path,
    write_json,
) -> None:
    workspace_root = tmp_path / "example-workspace"

    workspace_root.mkdir()
    (workspace_root / "CLAUDE.md").write_text("workspace rules", encoding="utf-8")
    (workspace_root / "shop-api" / ".git").mkdir(parents=True)
    (workspace_root / "shop-web" / ".git").mkdir(parents=True)

    write_json(
        common_root / "config" / "mcp.base.json",
        {
            "mcpServers": {
                "context7": {"url": "https://mcp.context7.com/mcp"},
                "sentry": {"command": "npx", "args": ["@sentry/mcp-server@latest"]},
            }
        },
    )
    write_json(
        common_root / "config" / "opencode.base.json",
        {
            "$schema": "https://opencode.ai/config.json",
            "instructions": ["/tmp/AGENTS.md"],
        },
    )

    (common_root / "skills" / "frontend-design").mkdir(parents=True)
    (common_root / "skills" / "frontend-design" / "SKILL.md").write_text("skill", encoding="utf-8")
    (common_root / "agents").mkdir(parents=True)
    (common_root / "agents" / "planner.md").write_text("agent", encoding="utf-8")

    common = CommonRepository(common_root)
    common.add_workspace("workspace-example", workspace_root)
    opencode = OpenCodeRepository(opencode_root)

    plan = build_plan(common, opencode)

    assert plan.errors == []
    assert any(action.kind == "write_json" and action.path == opencode.config_path for action in plan.actions)
    workspace_targets = {
        str(workspace_root / "shop-api" / "AGENTS.md"),
        str(workspace_root / "shop-web" / "AGENTS.md"),
    }
    planned_workspace_targets = {
        str(action.path)
        for action in plan.actions
        if action.kind == "symlink" and action.path.name == "AGENTS.md" and "example-workspace" in str(action.path)
    }
    assert workspace_targets.issubset(planned_workspace_targets)

    applied, failed, failures = execute_apply(plan, common, opencode)

    assert failed == 0
    assert failures == []
    assert applied > 0

    opencode_config = json.loads(opencode.config_path.read_text(encoding="utf-8"))
    assert opencode_config["mcp"]["context7"] == {"type": "remote", "url": "https://mcp.context7.com/mcp"}
    assert opencode_config["mcp"]["sentry"] == {"type": "local", "command": ["npx", "@sentry/mcp-server@latest"]}

    for repo_name in ["shop-api", "shop-web"]:
        link_path = workspace_root / repo_name / "AGENTS.md"
        assert link_path.is_symlink()
        assert link_path.resolve() == (workspace_root / "CLAUDE.md").resolve()

    state = common.load_state()
    assert len(state["managed_workspace_links"]) == 2
