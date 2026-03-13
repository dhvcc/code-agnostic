from pathlib import Path

from code_agnostic.apps.app_id import AppId, app_metadata
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
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan
from code_agnostic.rules.compilers import OpenCodeRuleCompiler
from code_agnostic.rules.repository import RulesRepository
from code_agnostic.workspaces import WorkspaceService


def _write_rule_status(path: Path, content: str) -> ActionStatus:
    if not path.exists():
        return ActionStatus.CREATE
    existing = path.read_text(encoding="utf-8")
    if existing == content:
        return ActionStatus.NOOP
    return ActionStatus.UPDATE


def _compile_workspace_agents(rules) -> str:
    compiler = OpenCodeRuleCompiler()
    sections = [compiler.compile(rule)[1] for rule in rules]
    return "\n\n".join(sections) + "\n"


def _set_workspace_opencode_instructions(
    service: IAppConfigService,
    action: Action,
    workspace_agents_path: Path | None,
) -> None:
    if service.app_id != AppId.OPENCODE or not isinstance(action.payload, dict):
        return

    payload = dict(action.payload)
    if workspace_agents_path is None:
        payload.pop("instructions", None)
    else:
        payload["instructions"] = [str(workspace_agents_path)]

    validate_config = getattr(service, "validate_config", None)
    if callable(validate_config):
        validate_config(payload)

    existing = service.repository.load_config()
    derive_status = getattr(service, "derive_status", None)
    if callable(derive_status):
        action.status = derive_status(existing, payload)
    action.payload = payload


def _merge_plans(*plans: SyncPlan) -> SyncPlan:
    actions: list[Action] = []
    errors: list[Exception] = []
    skipped: list[str] = []
    for plan in plans:
        actions.extend(plan.actions)
        errors.extend(plan.errors)
        skipped.extend(plan.skipped)
    return SyncPlan(actions=actions, errors=errors, skipped=skipped)


def _workspace_scope_matches_app(scope: str, app_ids: set[str]) -> bool:
    return any(scope.startswith(f"ws:{app_id}:") for app_id in app_ids)


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

        def _mark_workspace(action: Action) -> None:
            action.app = "workspace"
            action.workspace = workspace_name

        # --- Rules compilation ---
        desired_rules_links: list[Path] = []
        rules_repo = RulesRepository(ws_source.root)
        rules = rules_repo.list_rules()
        workspace_agents_source: Path | None = None
        if rules:
            content = _compile_workspace_agents(rules)
            status = _write_rule_status(ws_source.rules_file, content)
            rule_action = Action(
                kind=ActionKind.WRITE_RULE,
                path=ws_source.rules_file,
                status=status,
                detail=f"compile rules to {AGENTS_FILENAME} for workspace",
                payload=content,
                app="workspace",
                workspace=workspace_name,
            )
            _mark_workspace(rule_action)
            actions.append(rule_action)
            workspace_agents_source = ws_source.rules_file
        elif not rules_repo.rules_dir.exists() and ws_source.rules_file.exists():
            workspace_agents_source = ws_source.rules_file

        # --- Workspace-level app config rendering + repo symlinks ---
        desired_links_by_scope: dict[str, list[Path]] = {}

        # Workspace sources are intentionally isolated from global sources.
        # Global app configs still apply naturally; workspace config only adds workspace-specific config.
        skill_sources = ws_source.list_skill_sources()
        agent_sources = ws_source.list_agent_sources()

        common_servers = None
        if ws_source.has_mcp():
            try:
                mcp_base = ws_source.load_mcp_base()
                common_servers = common_mcp_to_dto(mcp_base.get("mcpServers", {}))
            except SyncAppError as exc:
                return SyncPlan(actions=actions, errors=[exc], skipped=skipped)

        for svc in self.app_services:
            meta = app_metadata(svc.app_id)
            if meta.project_dir_name is None or not meta.supports_workspace_propagation:
                continue

            ws_project_root = ws_source.root / meta.project_dir_name
            project_svc = create_registered_app_service(
                svc.app_id, root=ws_project_root
            )

            # Note: skills_dir/agents_dir are implemented by concrete repositories,
            # but are not part of the IAppConfigRepository interface.
            project_skills_dir: Path = getattr(project_svc.repository, "skills_dir")
            project_agents_dir: Path | None = (
                getattr(project_svc.repository, "agents_dir")
                if meta.supports_import_agents
                else None
            )

            # Render workspace config once into workspace project dir
            should_render_workspace_config = common_servers is not None or (
                workspace_agents_source is not None and svc.app_id == AppId.OPENCODE
            )
            if should_render_workspace_config:
                try:
                    mcp_action = project_svc.build_action(common_servers or {})
                    _set_workspace_opencode_instructions(
                        project_svc,
                        mcp_action,
                        workspace_path / AGENTS_FILENAME
                        if workspace_agents_source is not None
                        else None,
                    )
                    _mark_workspace(mcp_action)
                    actions.append(mcp_action)
                except SyncAppError as exc:
                    skipped.append(
                        f"MCP sync error for workspace {workspace_name}/{svc.app_id.value}: {exc}"
                    )

            # Workspace skill entries symlinked into workspace project dir
            if skill_sources:
                scope = f"ws:{svc.app_id.value}:skills_entries"
                skill_actions, desired, skill_skipped = plan_resource_symlinks(
                    skill_sources,
                    project_skills_dir,
                    scope=scope,
                    app="workspace",
                )
                for a in skill_actions:
                    _mark_workspace(a)
                actions.extend(skill_actions)
                desired_links_by_scope.setdefault(scope, []).extend(desired)
                skipped.extend(skill_skipped)

            # Workspace agent entries symlinked into workspace project dir
            if agent_sources and meta.supports_import_agents:
                scope = f"ws:{svc.app_id.value}:agents_entries"
                agent_actions, desired, agent_skipped = plan_resource_symlinks(
                    agent_sources,
                    project_agents_dir or ws_project_root / "agents",
                    scope=scope,
                    app="workspace",
                )
                for a in agent_actions:
                    _mark_workspace(a)
                actions.extend(agent_actions)
                desired_links_by_scope.setdefault(scope, []).extend(desired)
                skipped.extend(agent_skipped)

            # --- Repo symlinks for managed workspace config paths ---
            # Also symlink into the workspace root itself so opening the whole workspace
            # in an editor picks up the shared config.
            def _plan_target_link(
                *,
                target: Path,
                source: Path,
                scope: str,
                conflict_message: str,
            ) -> None:
                link_action = plan_symlink(
                    target,
                    source,
                    scope=scope,
                    app="workspace",
                )
                _mark_workspace(link_action)
                actions.append(link_action)
                desired_links_by_scope.setdefault(scope, []).append(target)
                if link_action.status == ActionStatus.CONFLICT:
                    skipped.append(conflict_message.format(path=target))

            # Workspace root links
            if should_render_workspace_config:
                _plan_target_link(
                    target=workspace_path
                    / meta.project_dir_name
                    / project_svc.repository.config_path.name,
                    source=project_svc.repository.config_path,
                    scope=f"ws:{svc.app_id.value}:workspace_root_mcp",
                    conflict_message="Workspace root MCP link skipped (conflict): {path}",
                )
            if skill_sources:
                _plan_target_link(
                    target=workspace_path / meta.project_dir_name / "skills",
                    source=project_skills_dir,
                    scope=f"ws:{svc.app_id.value}:workspace_root_skills_dir",
                    conflict_message="Workspace root skills dir link skipped (conflict): {path}",
                )
            if agent_sources and meta.supports_import_agents:
                _plan_target_link(
                    target=workspace_path / meta.project_dir_name / "agents",
                    source=project_agents_dir or ws_project_root / "agents",
                    scope=f"ws:{svc.app_id.value}:workspace_root_agents_dir",
                    conflict_message="Workspace root agents dir link skipped (conflict): {path}",
                )

            for repo in repos:
                # MCP config file link
                if should_render_workspace_config:
                    _plan_target_link(
                        target=repo
                        / meta.project_dir_name
                        / project_svc.repository.config_path.name,
                        source=project_svc.repository.config_path,
                        scope=f"ws:{svc.app_id.value}:repo_mcp",
                        conflict_message="Workspace MCP link skipped (conflict): {path}",
                    )

                # Skills dir link
                if skill_sources:
                    _plan_target_link(
                        target=repo / meta.project_dir_name / "skills",
                        source=project_skills_dir,
                        scope=f"ws:{svc.app_id.value}:repo_skills_dir",
                        conflict_message="Workspace skills dir link skipped (conflict): {path}",
                    )

                # Agents dir link
                if agent_sources and meta.supports_import_agents:
                    _plan_target_link(
                        target=repo / meta.project_dir_name / "agents",
                        source=project_agents_dir or ws_project_root / "agents",
                        scope=f"ws:{svc.app_id.value}:repo_agents_dir",
                        conflict_message="Workspace agents dir link skipped (conflict): {path}",
                    )

        if workspace_agents_source is not None:
            target = workspace_path / AGENTS_FILENAME
            action = plan_symlink(
                target,
                workspace_agents_source,
                scope="rules",
                app="workspace",
            )
            _mark_workspace(action)
            actions.append(action)
            desired_rules_links.append(target)
            if action.status == ActionStatus.CONFLICT:
                skipped.append(f"Workspace rules link skipped (conflict): {target}")

        # --- Stale cleanup ---
        state = ws_source.load_state()
        managed_links = state.get("managed_links", {})
        if not isinstance(managed_links, dict):
            managed_links = {}

        active_workspace_apps = {
            svc.app_id.value
            for svc in self.app_services
            if app_metadata(svc.app_id).supports_workspace_propagation
        }

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
            _mark_workspace(a)
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
                _mark_workspace(a)
            actions.extend(stale_actions)

        # Clean scopes in state that no longer have any desired links
        all_stale_scopes = {
            scope
            for scope in managed_links.keys()
            if scope != "rules"
            and scope not in desired_links_by_scope
            and _workspace_scope_matches_app(scope, active_workspace_apps)
        }
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
                _mark_workspace(a)
            actions.extend(stale_actions)

        return SyncPlan(actions=actions, errors=[], skipped=skipped)
