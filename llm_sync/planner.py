import os
from pathlib import Path
from typing import Optional

from llm_sync.mappers.base import IConfigMapper
from llm_sync.mappers.opencode import OpenCodeMapper
from llm_sync.models import Action, PlanResult
from llm_sync.repositories.base import ISourceRepository, ITargetRepository
from llm_sync.utils import is_under, same_json
from llm_sync.workspaces import list_workspace_repos, resolve_workspace_rules_file


def _canonical_target(path: Path) -> str:
    return str(path.resolve())


def _plan_symlink(target: Path, source: Path) -> Action:
    desired = _canonical_target(source)
    if target.exists() or target.is_symlink():
        if target.is_symlink():
            current = os.path.realpath(target)
            if current == desired:
                return Action("symlink", target, "noop", "already linked", source=source)
            return Action("symlink", target, "fix", "symlink points elsewhere", source=source)
        return Action("symlink", target, "conflict", "non-symlink path exists", source=source)
    return Action("symlink", target, "create", "create symlink", source=source)


def build_plan(common: ISourceRepository, opencode: ITargetRepository, mapper: Optional[IConfigMapper] = None) -> PlanResult:
    actions: list[Action] = []
    errors: list[str] = []
    skipped: list[str] = []

    effective_mapper = mapper or OpenCodeMapper()

    mcp_base = common.load_mcp_base()
    opencode_base = common.load_opencode_base()
    mapped_mcp = effective_mapper.map_mcp_servers(mcp_base["mcpServers"])

    existing_config, config_error = opencode.load_config_object()
    if config_error is not None:
        errors.append(f"Cannot parse {opencode.config_path}: {config_error}")
    else:
        merged_config = opencode.merge_config(existing_config, opencode_base, mapped_mcp)
        if same_json(opencode.config_path, merged_config):
            actions.append(Action("write_json", opencode.config_path, "noop", "already in sync", payload=merged_config))
        else:
            status = "create" if not opencode.config_path.exists() else "update"
            actions.append(Action("write_json", opencode.config_path, status, "merge opencode base + canonical mcp", payload=merged_config))

    skill_sources = common.list_skill_sources()
    mapped_skill_sources = [effective_mapper.map_skill_source(source) for source in skill_sources]
    desired_skill_links = [opencode.skills_dir / source.name for source in mapped_skill_sources]
    for source in mapped_skill_sources:
        action = _plan_symlink(opencode.skills_dir / source.name, source)
        actions.append(action)
        if action.status == "conflict":
            skipped.append(f"Skill link skipped (conflict): {action.path}")

    agent_sources = common.list_agent_sources()
    mapped_agent_sources = [effective_mapper.map_agent_source(source) for source in agent_sources]
    desired_agent_links = [opencode.agents_dir / source.name for source in mapped_agent_sources]
    for source in mapped_agent_sources:
        action = _plan_symlink(opencode.agents_dir / source.name, source)
        actions.append(action)
        if action.status == "conflict":
            skipped.append(f"Agent link skipped (conflict): {action.path}")

    workspace_links: list[Path] = []
    for workspace in common.load_workspaces():
        workspace_name = workspace["name"]
        workspace_path = Path(workspace["path"])
        if not workspace_path.exists() or not workspace_path.is_dir():
            skipped.append(f"Workspace path missing, skipped: {workspace_name} ({workspace_path})")
            continue

        rules_file = resolve_workspace_rules_file(workspace_path)
        if rules_file is None:
            skipped.append(f"Workspace has no rules file (AGENTS.md/CLAUDE.md), skipped: {workspace_name}")
            continue
        mapped_rules_file = effective_mapper.map_workspace_rules_source(rules_file)

        for repo in list_workspace_repos(workspace_path):
            target = repo / "AGENTS.md"
            action = _plan_symlink(target, mapped_rules_file)
            actions.append(action)
            workspace_links.append(target)
            if action.status == "conflict":
                skipped.append(f"Workspace rules link skipped (conflict): {target}")

    state = common.load_state()
    opencode_roots = [opencode.skills_dir.resolve(), opencode.agents_dir.resolve()]

    old_skill_links = [Path(item) for item in state.get("managed_skill_links", []) if isinstance(item, str)]
    desired_skill_set = {str(path) for path in desired_skill_links}
    for old in old_skill_links:
        if str(old) in desired_skill_set:
            continue
        if not any(is_under(old, root) for root in opencode_roots):
            continue
        if old.is_symlink():
            actions.append(Action("remove_symlink", old, "remove", "remove stale managed skill symlink"))
        elif old.exists():
            actions.append(Action("remove_symlink", old, "conflict", "stale managed path is not a symlink"))
            skipped.append(f"Stale link cleanup skipped (not symlink): {old}")
        else:
            actions.append(Action("remove_symlink", old, "noop", "stale symlink already absent"))

    old_agent_links = [Path(item) for item in state.get("managed_agent_links", []) if isinstance(item, str)]
    desired_agent_set = {str(path) for path in desired_agent_links}
    for old in old_agent_links:
        if str(old) in desired_agent_set:
            continue
        if not any(is_under(old, root) for root in opencode_roots):
            continue
        if old.is_symlink():
            actions.append(Action("remove_symlink", old, "remove", "remove stale managed agent symlink"))
        elif old.exists():
            actions.append(Action("remove_symlink", old, "conflict", "stale managed path is not a symlink"))
            skipped.append(f"Stale link cleanup skipped (not symlink): {old}")
        else:
            actions.append(Action("remove_symlink", old, "noop", "stale symlink already absent"))

    old_workspace_links = [Path(item) for item in state.get("managed_workspace_links", []) if isinstance(item, str)]
    desired_workspace_set = {str(path) for path in workspace_links}
    for old in old_workspace_links:
        if str(old) in desired_workspace_set:
            continue
        if old.is_symlink():
            actions.append(Action("remove_symlink", old, "remove", "remove stale managed workspace symlink"))
        elif old.exists():
            actions.append(Action("remove_symlink", old, "conflict", "stale workspace path is not a symlink"))
            skipped.append(f"Stale workspace cleanup skipped (not symlink): {old}")
        else:
            actions.append(Action("remove_symlink", old, "noop", "stale workspace symlink already absent"))

    return PlanResult(actions=actions, errors=errors, skipped=skipped)


def filter_plan_for_target(plan: PlanResult, target: str, opencode: ITargetRepository) -> PlanResult:
    if target == "all":
        return plan

    if target != "opencode":
        return PlanResult(actions=[], errors=plan.errors, skipped=plan.skipped)

    skills_root = opencode.skills_dir.resolve()
    agents_root = opencode.agents_dir.resolve()
    filtered_actions: list[Action] = []
    for action in plan.actions:
        if action.path == opencode.config_path:
            filtered_actions.append(action)
            continue
        if is_under(action.path, skills_root) or is_under(action.path, agents_root):
            filtered_actions.append(action)

    return PlanResult(actions=filtered_actions, errors=plan.errors, skipped=plan.skipped)
