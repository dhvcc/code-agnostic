"""Tests for rules planning in the SyncPlanner."""

from pathlib import Path

import pytest

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.core.repository import CoreRepository
from code_agnostic.models import ActionKind


@pytest.fixture
def setup_workspace(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path, cli_runner, enable_app
):
    """Set up a workspace with a repo and return key paths."""
    from code_agnostic.__main__ import cli

    workspace_root = tmp_path / "ws"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git").mkdir(parents=True)

    cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "myws", "--path", str(workspace_root)]
    )

    ws_config_dir = core_root / "workspaces" / "myws"

    return {
        "workspace_root": workspace_root,
        "ws_config_dir": ws_config_dir,
        "repo": workspace_root / "repo-a",
    }


def test_plan_workspace_with_rules_dir(setup_workspace, enable_app) -> None:
    enable_app("opencode")
    ws = setup_workspace
    rules_dir = ws["ws_config_dir"] / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "python.md").write_text(
        "---\ndescription: Python style\nalways_apply: true\n---\n\nUse type hints.\n",
        encoding="utf-8",
    )

    core = CoreRepository()
    apps = AppsService(core)
    plan = apps.plan_for_target("all")

    rule_actions = [a for a in plan.actions if a.kind == ActionKind.WRITE_RULE]
    assert len(rule_actions) >= 1
    assert any("rule" in a.detail.lower() for a in rule_actions)


def test_plan_workspace_no_rules(setup_workspace, enable_app) -> None:
    enable_app("opencode")

    core = CoreRepository()
    apps = AppsService(core)
    plan = apps.plan_for_target("all")

    rule_actions = [a for a in plan.actions if a.kind == ActionKind.WRITE_RULE]
    assert len(rule_actions) == 0


def test_plan_rules_compiled_only_for_workspace_propagation_apps(
    setup_workspace, enable_app
) -> None:
    enable_app("opencode")
    enable_app("cursor")
    ws = setup_workspace
    rules_dir = ws["ws_config_dir"] / "rules"
    rules_dir.mkdir(parents=True)
    (rules_dir / "shared.md").write_text(
        "---\ndescription: Shared rule\nalways_apply: true\n---\n\nShared content.\n",
        encoding="utf-8",
    )

    core = CoreRepository()
    apps = AppsService(core)
    plan = apps.plan_for_target("all")

    rule_actions = [a for a in plan.actions if a.kind == ActionKind.WRITE_RULE]
    # Cursor workspace propagation is intentionally disabled.
    assert len(rule_actions) == 1

    # OpenCode should get AGENTS.md
    opencode_rules = [a for a in rule_actions if "opencode" in a.detail]
    assert len(opencode_rules) >= 1
    assert any("AGENTS.md" in a.detail for a in opencode_rules)

    # Cursor should not compile workspace rules.
    cursor_rules = [a for a in rule_actions if "cursor" in a.detail]
    assert cursor_rules == []
