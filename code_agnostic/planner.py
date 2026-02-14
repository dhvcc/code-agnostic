from pathlib import Path

from code_agnostic.apps.app_id import app_metadata
from code_agnostic.apps.common.framework import create_registered_app_service
from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.apps.common.interfaces.service import IAppConfigService
from code_agnostic.apps.common.symlink_planning import (
    load_state_links,
    plan_resource_symlinks,
    plan_stale_group,
    plan_symlink,
)
from code_agnostic.apps.common.utils import common_mcp_to_dto
from code_agnostic.constants import AGENTS_FILENAME
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.errors import SyncAppError
from code_agnostic.models import Action, ActionStatus, SyncPlan
from code_agnostic.workspaces import WorkspaceService


def _merge_plans(*plans: SyncPlan) -> SyncPlan:
    actions: list[Action] = []
    errors: list[Exception] = []
    skipped: list[str] = []
    for plan in plans:
        actions.extend(plan.actions)
        errors.extend(plan.errors)
        skipped.extend(plan.skipped)
    return SyncPlan(actions=actions, errors=errors, skipped=skipped)


class SyncPlanner:
    def __init__(
        self,
        core: ISourceRepository,
        app_services: list[IAppConfigService],
        workspace_service: WorkspaceService | None = None,
        include_workspace: bool = True,
    ) -> None:
        self.core = core
        self.app_services = app_services
        self.workspace_service = workspace_service or WorkspaceService()
        self.include_workspace = include_workspace

    def build(self) -> SyncPlan:
        app_plan = self._plan_apps()
        workspace_plan = (
            self._plan_workspaces() if self.include_workspace else SyncPlan([], [], [])
        )
        return _merge_plans(app_plan, workspace_plan)

    def _plan_apps(self) -> SyncPlan:
        if not self.app_services:
            return SyncPlan(actions=[], errors=[], skipped=[])

        try:
            mcp_base = self.core.load_mcp_base()
        except SyncAppError as exc:
            return SyncPlan(actions=[], errors=[exc], skipped=[])

        desired_common = common_mcp_to_dto(mcp_base.get("mcpServers", {}))
        plans: list[SyncPlan] = []
        for service in self.app_services:
            try:
                plans.append(service.build_plan(desired_common, self.core))
            except SyncAppError as exc:
                plans.append(SyncPlan(actions=[], errors=[exc], skipped=[]))
        return _merge_plans(*plans)

    def _plan_workspaces(self) -> SyncPlan:
        plans = []
        for workspace in self.core.load_workspaces():
            plans.append(self._plan_single_workspace(workspace))
        return _merge_plans(*plans) if plans else SyncPlan([], [], [])

    def _plan_single_workspace(self, workspace: dict) -> SyncPlan:
        workspace_name = workspace["name"]
        workspace_path = Path(workspace["path"])

        if not workspace_path.exists() or not workspace_path.is_dir():
            return SyncPlan(
                [],
                [],
                [f"Workspace path missing: {workspace_name} ({workspace_path})"],
            )

        ws_source = WorkspaceConfigRepository(
            root=self.core.workspace_config_dir(workspace_name)
        )

        repos = self.workspace_service.discover_git_repos(workspace_path)

        has_config = ws_source.has_any_config()
        if not has_config and not repos:
            return SyncPlan([], [], [])

        actions: list[Action] = []
        skipped: list[str] = []

        # --- AGENTS.md symlinks ---
        desired_rules_links: list[Path] = []
        if ws_source.has_rules():
            for repo in repos:
                target = repo / AGENTS_FILENAME
                action = plan_symlink(
                    target,
                    ws_source.rules_file,
                    scope="rules",
                    app="workspace",
                )
                action.workspace = workspace_name
                actions.append(action)
                desired_rules_links.append(target)
                if action.status == ActionStatus.CONFLICT:
                    skipped.append(f"Workspace rules link skipped (conflict): {target}")

        # --- Per-app config sync ---
        desired_links_by_scope: dict[str, list[Path]] = {}

        if ws_source.has_mcp():
            try:
                mcp_base = ws_source.load_mcp_base()
                common_servers = common_mcp_to_dto(mcp_base.get("mcpServers", {}))
            except SyncAppError as exc:
                return SyncPlan(actions=actions, errors=[exc], skipped=skipped)

            for svc in self.app_services:
                meta = app_metadata(svc.app_id)
                if meta.project_dir_name is None:
                    continue
                for repo in repos:
                    project_root = repo / meta.project_dir_name
                    try:
                        project_svc = create_registered_app_service(
                            svc.app_id, root=project_root
                        )
                        mcp_action = project_svc.build_action(common_servers)
                        mcp_action.app = "workspace"
                        mcp_action.workspace = workspace_name
                        actions.append(mcp_action)
                    except SyncAppError as exc:
                        skipped.append(
                            f"MCP sync error for {repo.name}/{svc.app_id.value}: {exc}"
                        )

        # --- Skill symlinks ---
        skill_sources = ws_source.list_skill_sources()
        if skill_sources:
            for svc in self.app_services:
                meta = app_metadata(svc.app_id)
                if meta.project_dir_name is None:
                    continue
                scope = f"{svc.app_id.value}:skills"
                for repo in repos:
                    project_root = repo / meta.project_dir_name
                    project_svc = create_registered_app_service(
                        svc.app_id, root=project_root
                    )
                    skill_actions, desired, skill_skipped = plan_resource_symlinks(
                        skill_sources,
                        project_svc.repository.skills_dir,
                        scope=scope,
                        app="workspace",
                    )
                    for a in skill_actions:
                        a.workspace = workspace_name
                    actions.extend(skill_actions)
                    desired_links_by_scope.setdefault(scope, []).extend(desired)
                    skipped.extend(skill_skipped)

        # --- Agent symlinks ---
        agent_sources = ws_source.list_agent_sources()
        if agent_sources:
            for svc in self.app_services:
                meta = app_metadata(svc.app_id)
                if meta.project_dir_name is None:
                    continue
                if not meta.supports_import_agents:
                    continue
                scope = f"{svc.app_id.value}:agents"
                for repo in repos:
                    project_root = repo / meta.project_dir_name
                    project_svc = create_registered_app_service(
                        svc.app_id, root=project_root
                    )
                    agent_actions, desired, agent_skipped = plan_resource_symlinks(
                        agent_sources,
                        project_svc.repository.agents_dir,
                        scope=scope,
                        app="workspace",
                    )
                    for a in agent_actions:
                        a.workspace = workspace_name
                    actions.extend(agent_actions)
                    desired_links_by_scope.setdefault(scope, []).extend(desired)
                    skipped.extend(agent_skipped)

        # --- Stale cleanup ---
        state = ws_source.load_state()
        managed_links = state.get("managed_links", {})
        if not isinstance(managed_links, dict):
            managed_links = {}

        # Rules stale cleanup
        stale_rules = plan_stale_group(
            old_links=load_state_links(managed_links, "rules"),
            desired_links=desired_rules_links,
            remove_detail="remove stale workspace rules symlink",
            conflict_detail="stale workspace rules path is not a symlink",
            noop_detail="stale workspace rules symlink already absent",
            app="workspace",
            scope="rules",
            skipped=skipped,
            skipped_message="Stale workspace rules cleanup skipped (not symlink): {path}",
        )
        for a in stale_rules:
            a.workspace = workspace_name
        actions.extend(stale_rules)

        # Per-scope stale cleanup for skills/agents
        for scope, desired in desired_links_by_scope.items():
            stale_actions = plan_stale_group(
                old_links=load_state_links(managed_links, scope),
                desired_links=desired,
                remove_detail=f"remove stale workspace {scope} symlink",
                conflict_detail=f"stale workspace {scope} path is not a symlink",
                noop_detail=f"stale workspace {scope} symlink already absent",
                app="workspace",
                scope=scope,
                skipped=skipped,
                skipped_message="Stale workspace cleanup skipped (not symlink): {path}",
            )
            for a in stale_actions:
                a.workspace = workspace_name
            actions.extend(stale_actions)

        # Clean scopes in state that no longer have any desired links
        all_stale_scopes = (
            set(managed_links.keys()) - {"rules"} - set(desired_links_by_scope.keys())
        )
        for scope in sorted(all_stale_scopes):
            stale_actions = plan_stale_group(
                old_links=load_state_links(managed_links, scope),
                desired_links=[],
                remove_detail=f"remove stale workspace {scope} symlink",
                conflict_detail=f"stale workspace {scope} path is not a symlink",
                noop_detail=f"stale workspace {scope} symlink already absent",
                app="workspace",
                scope=scope,
                skipped=skipped,
                skipped_message="Stale workspace cleanup skipped (not symlink): {path}",
            )
            for a in stale_actions:
                a.workspace = workspace_name
            actions.extend(stale_actions)

        return SyncPlan(actions=actions, errors=[], skipped=skipped)
