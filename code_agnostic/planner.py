from pathlib import Path

from code_agnostic.apps.app_id import AppId, app_metadata
from code_agnostic.apps.common.compiled_planning import plan_compiled_text_action
from code_agnostic.apps.common.framework import create_registered_app_service
from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.apps.common.interfaces.service import IAppConfigService
from code_agnostic.apps.common.symlink_planning import (
    load_state_links,
    load_state_paths,
    plan_stale_files_group,
    plan_stale_group,
)
from code_agnostic.apps.codex.config_repository import CodexConfigRepository
from code_agnostic.apps.codex.mapper import CodexMCPMapper
from code_agnostic.apps.codex.schema_repository import CodexSchemaRepository
from code_agnostic.apps.codex.service import CodexConfigService
from code_agnostic.apps.common.utils import common_mcp_to_dto, mcp_servers_for_app
from code_agnostic.constants import (
    AGENTS_FILENAME,
    AGENTS_PROJECT_DIRNAME,
    CODEX_AGENTS_OVERRIDE_FILENAME,
    MCP_SERVERS_KEY,
    SKILLS_DIRNAME,
)
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.errors import MissingConfigFileError, SyncAppError
from code_agnostic.git_exclude_service import GitExcludeService
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan
from code_agnostic.rules.compilers import OpenCodeRuleCompiler
from code_agnostic.rules.repository import RulesRepository
from code_agnostic.workspaces import WorkspaceService


def _compile_workspace_agents(rules) -> str:
    compiler = OpenCodeRuleCompiler()
    sections = [compiler.compile(rule)[1] for rule in rules]
    return "\n\n".join(sections) + "\n"


def _create_workspace_project_service(
    app_id: AppId,
    target_root: Path,
    ws_source: WorkspaceConfigRepository,
) -> IAppConfigService:
    if app_id == AppId.CODEX:
        return CodexConfigService(
            repository=CodexConfigRepository(root=target_root),
            mapper=CodexMCPMapper(),
            schema_repository=CodexSchemaRepository(),
            base_config_path=(
                ws_source.codex_base_path
                if ws_source.codex_base_path.exists()
                else None
            ),
        )
    return create_registered_app_service(app_id, root=target_root)


def _workspace_skills_dir(app_id: AppId, project_root: Path) -> Path:
    if app_id == AppId.CODEX:
        return project_root.parent / AGENTS_PROJECT_DIRNAME / SKILLS_DIRNAME
    return project_root / SKILLS_DIRNAME


def _workspace_symlink_override_status(
    target: Path, removable_links: list[Path]
) -> ActionStatus | None:
    removable = {path.resolve(strict=False) for path in removable_links}
    current = target
    found_symlink = False
    while True:
        if current.is_symlink():
            found_symlink = True
            current_key = current.resolve(strict=False)
            if current_key in removable:
                return ActionStatus.CREATE
        if current.parent == current:
            return ActionStatus.CONFLICT if found_symlink else None
        current = current.parent


def _prepare_workspace_action(
    action: Action,
    *,
    workspace_name: str,
    scope: str,
    removable_links: list[Path],
) -> Action:
    if action.kind in {ActionKind.WRITE_JSON, ActionKind.WRITE_TEXT} and scope.endswith(
        "_mcp"
    ):
        override_status = _workspace_symlink_override_status(
            action.path, removable_links
        )
        if override_status is not None:
            action.status = override_status
    action.app = "workspace"
    action.workspace = workspace_name
    action.scope = scope
    return action


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
        derived_status = derive_status(existing, payload)
        if isinstance(derived_status, ActionStatus):
            action.status = derived_status
    action.payload = payload


def _plan_git_exclude_entries(
    *,
    exclude_path: Path,
    entries: list[str],
    workspace_name: str,
) -> Action:
    existing_lines: list[str] = []
    if exclude_path.exists() and not exclude_path.is_file():
        return Action(
            kind=ActionKind.WRITE_TEXT,
            path=exclude_path,
            status=ActionStatus.CONFLICT,
            detail="git exclude path is not a file",
            payload="",
            app="workspace",
            workspace=workspace_name,
        )
    if exclude_path.exists():
        existing_lines = exclude_path.read_text(encoding="utf-8").splitlines()

    seen = {
        line.strip()
        for line in existing_lines
        if line.strip() and not line.lstrip().startswith("#")
    }
    missing = [entry for entry in entries if entry not in seen]
    if not missing:
        return Action(
            kind=ActionKind.WRITE_TEXT,
            path=exclude_path,
            status=ActionStatus.NOOP,
            detail="workspace sync paths already excluded from git",
            payload="\n".join(existing_lines) + ("\n" if existing_lines else ""),
            app="workspace",
            workspace=workspace_name,
        )

    merged = list(existing_lines)
    if merged and merged[-1] != "":
        merged.append("")
    merged.extend(missing)
    return Action(
        kind=ActionKind.WRITE_TEXT,
        path=exclude_path,
        status=ActionStatus.UPDATE if exclude_path.exists() else ActionStatus.CREATE,
        detail="exclude workspace sync paths from git",
        payload="\n".join(merged) + "\n",
        app="workspace",
        workspace=workspace_name,
    )


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
        except MissingConfigFileError:
            mcp_base = {MCP_SERVERS_KEY: {}}
        except SyncAppError as exc:
            return SyncPlan(actions=[], errors=[exc], skipped=[])

        plans: list[SyncPlan] = []
        for service in self.app_services:
            try:
                target_servers = mcp_servers_for_app(
                    mcp_base.get(MCP_SERVERS_KEY, {}), service.app_id
                )
                desired_common = common_mcp_to_dto(target_servers)
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
        state = ws_source.load_state()
        managed_links = state.get("managed_links", {})
        if not isinstance(managed_links, dict):
            managed_links = {}
        managed_paths = state.get("managed_paths", {})
        if not isinstance(managed_paths, dict):
            managed_paths = {}

        has_config = ws_source.has_any_config()
        if not has_config and not repos:
            return SyncPlan([], [], [])

        actions: list[Action] = []
        skipped: list[str] = []

        # --- Rules compilation ---
        desired_paths_by_scope: dict[str, list[Path]] = {}
        rules_repo = RulesRepository(ws_source.root)
        rules = rules_repo.list_rules()
        workspace_agents_target: Path | None = None
        workspace_agents_content: str | None = None
        if rules:
            content = _compile_workspace_agents(rules)
            workspace_agents_content = content
            target = workspace_path / AGENTS_FILENAME
            rule_action = plan_compiled_text_action(
                target=target,
                payload=content,
                managed_paths={
                    path.resolve(strict=False)
                    for path in load_state_paths(managed_paths, "rules")
                },
                removable_link_paths={
                    path.resolve(strict=False)
                    for path in load_state_links(managed_links, "rules")
                },
                scope="rules",
                app="workspace",
                create_detail="create workspace rules file",
                noop_detail="workspace rules file already up to date",
                update_detail="update workspace rules file",
            )
            _prepare_workspace_action(
                rule_action,
                workspace_name=workspace_name,
                scope="rules",
                removable_links=load_state_links(managed_links, "rules"),
            )
            actions.append(rule_action)
            desired_paths_by_scope.setdefault("rules", []).append(target)
            workspace_agents_target = target
        elif not rules_repo.rules_dir.exists() and ws_source.rules_file.exists():
            content = ws_source.rules_file.read_text(encoding="utf-8")
            workspace_agents_content = content
            target = workspace_path / AGENTS_FILENAME
            rule_action = plan_compiled_text_action(
                target=target,
                payload=content,
                managed_paths={
                    path.resolve(strict=False)
                    for path in load_state_paths(managed_paths, "rules")
                },
                removable_link_paths={
                    path.resolve(strict=False)
                    for path in load_state_links(managed_links, "rules")
                },
                scope="rules",
                app="workspace",
                create_detail="create workspace rules file",
                noop_detail="workspace rules file already up to date",
                update_detail="update workspace rules file",
            )
            _prepare_workspace_action(
                rule_action,
                workspace_name=workspace_name,
                scope="rules",
                removable_links=load_state_links(managed_links, "rules"),
            )
            actions.append(rule_action)
            desired_paths_by_scope.setdefault("rules", []).append(target)
            workspace_agents_target = target

        # --- Workspace-level app config rendering + direct target writes ---

        # Workspace app config renders workspace-local MCP only. Global MCP remains in the
        # app-level config (`~/.cursor/mcp.json`, `~/.config/opencode/opencode.json`, etc.)
        # and is not duplicated into workspace-generated project config.
        skill_sources = ws_source.list_skill_sources()
        agent_sources = ws_source.list_agent_sources()

        common_servers = None
        if ws_source.has_mcp():
            try:
                mcp_base = ws_source.load_mcp_base()
                common_servers = mcp_base.get(MCP_SERVERS_KEY, {})
            except SyncAppError as exc:
                return SyncPlan(actions=actions, errors=[exc], skipped=skipped)

        for svc in self.app_services:
            meta = app_metadata(svc.app_id)
            if meta.project_dir_name is None or not meta.supports_workspace_propagation:
                continue

            mcp_payload = (
                common_mcp_to_dto(mcp_servers_for_app(common_servers, svc.app_id))
                if common_servers is not None
                else {}
            )
            has_workspace_mcp_render = common_servers is not None

            should_render_workspace_config = has_workspace_mcp_render or (
                workspace_agents_target is not None and svc.app_id == AppId.OPENCODE
            )
            if svc.app_id == AppId.CODEX and ws_source.codex_base_path.exists():
                should_render_workspace_config = True
            if svc.app_id == AppId.CODEX and agent_sources:
                should_render_workspace_config = True

            # Workspace root outputs
            workspace_target_service = _create_workspace_project_service(
                svc.app_id,
                workspace_path / meta.project_dir_name,
                ws_source,
            )
            if should_render_workspace_config:
                scope = f"ws:{svc.app_id.value}:workspace_root_mcp"
                mcp_action = workspace_target_service.build_action(
                    mcp_payload,
                    agent_sources=agent_sources,
                )
                _set_workspace_opencode_instructions(
                    workspace_target_service,
                    mcp_action,
                    workspace_agents_target,
                )
                _prepare_workspace_action(
                    mcp_action,
                    workspace_name=workspace_name,
                    scope=scope,
                    removable_links=load_state_links(managed_links, scope),
                )
                actions.append(mcp_action)
                desired_paths_by_scope.setdefault(scope, []).append(mcp_action.path)
            if skill_sources:
                scope = f"ws:{svc.app_id.value}:workspace_root_skills_dir"
                plan_skill_actions = getattr(
                    workspace_target_service, "plan_skill_actions"
                )
                skill_actions, desired_paths, skill_skipped = plan_skill_actions(
                    skill_sources,
                    _workspace_skills_dir(
                        svc.app_id, workspace_target_service.repository.root
                    ),
                    scope,
                    "workspace",
                    load_state_paths(managed_paths, scope),
                    load_state_links(managed_links, scope),
                )
                for a in skill_actions:
                    _prepare_workspace_action(
                        a,
                        workspace_name=workspace_name,
                        scope=scope,
                        removable_links=load_state_links(managed_links, scope),
                    )
                actions.extend(skill_actions)
                desired_paths_by_scope.setdefault(scope, []).extend(desired_paths)
                skipped.extend(skill_skipped)
            if agent_sources and meta.supports_import_agents:
                scope = f"ws:{svc.app_id.value}:workspace_root_agents_dir"
                plan_agent_actions = getattr(
                    workspace_target_service, "plan_agent_actions"
                )
                agent_actions, desired_paths, agent_skipped = plan_agent_actions(
                    agent_sources,
                    getattr(workspace_target_service.repository, "agents_dir"),
                    scope,
                    "workspace",
                    load_state_paths(managed_paths, scope),
                    load_state_links(managed_links, scope),
                )
                for a in agent_actions:
                    _prepare_workspace_action(
                        a,
                        workspace_name=workspace_name,
                        scope=scope,
                        removable_links=load_state_links(managed_links, scope),
                    )
                actions.extend(agent_actions)
                desired_paths_by_scope.setdefault(scope, []).extend(desired_paths)
                skipped.extend(agent_skipped)

            for repo in repos:
                repo_target_service = _create_workspace_project_service(
                    svc.app_id,
                    repo / meta.project_dir_name,
                    ws_source,
                )

                if svc.app_id == AppId.CODEX and workspace_agents_content is not None:
                    scope = "ws:codex:repo_agents_override"
                    override_target = repo / CODEX_AGENTS_OVERRIDE_FILENAME
                    override_action = plan_compiled_text_action(
                        target=override_target,
                        payload=workspace_agents_content,
                        managed_paths={
                            path.resolve(strict=False)
                            for path in load_state_paths(managed_paths, scope)
                        },
                        removable_link_paths={
                            path.resolve(strict=False)
                            for path in load_state_links(managed_links, scope)
                        },
                        scope=scope,
                        app="workspace",
                        create_detail="create codex workspace override",
                        noop_detail="codex workspace override already up to date",
                        update_detail="update codex workspace override",
                    )
                    _prepare_workspace_action(
                        override_action,
                        workspace_name=workspace_name,
                        scope=scope,
                        removable_links=load_state_links(managed_links, scope),
                    )
                    actions.append(override_action)
                    desired_paths_by_scope.setdefault(scope, []).append(override_target)

                if should_render_workspace_config:
                    scope = f"ws:{svc.app_id.value}:repo_mcp"
                    mcp_action = repo_target_service.build_action(
                        mcp_payload,
                        agent_sources=agent_sources,
                    )
                    _set_workspace_opencode_instructions(
                        repo_target_service,
                        mcp_action,
                        workspace_agents_target,
                    )
                    _prepare_workspace_action(
                        mcp_action,
                        workspace_name=workspace_name,
                        scope=scope,
                        removable_links=load_state_links(managed_links, scope),
                    )
                    actions.append(mcp_action)
                    desired_paths_by_scope.setdefault(scope, []).append(mcp_action.path)

                if skill_sources:
                    scope = f"ws:{svc.app_id.value}:repo_skills_dir"
                    plan_skill_actions = getattr(
                        repo_target_service, "plan_skill_actions"
                    )
                    skill_actions, desired_paths, skill_skipped = plan_skill_actions(
                        skill_sources,
                        _workspace_skills_dir(
                            svc.app_id, repo_target_service.repository.root
                        ),
                        scope,
                        "workspace",
                        load_state_paths(managed_paths, scope),
                        load_state_links(managed_links, scope),
                    )
                    for a in skill_actions:
                        _prepare_workspace_action(
                            a,
                            workspace_name=workspace_name,
                            scope=scope,
                            removable_links=load_state_links(managed_links, scope),
                        )
                    actions.extend(skill_actions)
                    desired_paths_by_scope.setdefault(scope, []).extend(desired_paths)
                    skipped.extend(skill_skipped)

                if agent_sources and meta.supports_import_agents:
                    scope = f"ws:{svc.app_id.value}:repo_agents_dir"
                    plan_agent_actions = getattr(
                        repo_target_service, "plan_agent_actions"
                    )
                    agent_actions, desired_paths, agent_skipped = plan_agent_actions(
                        agent_sources,
                        getattr(repo_target_service.repository, "agents_dir"),
                        scope,
                        "workspace",
                        load_state_paths(managed_paths, scope),
                        load_state_links(managed_links, scope),
                    )
                    for a in agent_actions:
                        _prepare_workspace_action(
                            a,
                            workspace_name=workspace_name,
                            scope=scope,
                            removable_links=load_state_links(managed_links, scope),
                        )
                    actions.extend(agent_actions)
                    desired_paths_by_scope.setdefault(scope, []).extend(desired_paths)
                    skipped.extend(agent_skipped)

        exclude_entries = GitExcludeService(self.core).compute_entries(
            workspace_name,
            [
                svc.app_id.value
                for svc in self.app_services
                if app_metadata(svc.app_id).supports_workspace_propagation
            ],
        )
        for repo in repos:
            git_dir = self.workspace_service.resolve_git_dir(repo)
            if git_dir is None:
                continue
            actions.append(
                _plan_git_exclude_entries(
                    exclude_path=git_dir / "info" / "exclude",
                    entries=exclude_entries,
                    workspace_name=workspace_name,
                )
            )

        # --- Stale cleanup ---
        active_workspace_apps = {
            svc.app_id.value
            for svc in self.app_services
            if app_metadata(svc.app_id).supports_workspace_propagation
        }

        stale_rules = plan_stale_group(
            old_links=load_state_links(managed_links, "rules"),
            desired_links=desired_paths_by_scope.get("rules", []),
            remove_detail="remove stale workspace rules symlink",
            conflict_detail="stale workspace rules path is not a symlink",
            noop_detail="stale workspace rules symlink already absent",
            app="workspace",
            scope="rules",
            skipped=skipped,
            skipped_message="Stale workspace rules cleanup skipped (not symlink): {path}",
        )
        for a in stale_rules:
            _prepare_workspace_action(
                a,
                workspace_name=workspace_name,
                scope="rules",
                removable_links=[],
            )
        actions.extend(stale_rules)

        for scope, desired in desired_paths_by_scope.items():
            if scope == "rules":
                continue
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
                _prepare_workspace_action(
                    a,
                    workspace_name=workspace_name,
                    scope=scope,
                    removable_links=[],
                )
            actions.extend(stale_actions)
            stale_actions = plan_stale_files_group(
                old_paths=load_state_paths(managed_paths, scope),
                desired_paths=desired,
                remove_detail=f"remove stale workspace {scope} file",
                conflict_detail=f"stale workspace {scope} path is not a file",
                noop_detail=f"stale workspace {scope} file already absent",
                app="workspace",
                scope=scope,
                skipped=skipped,
                skipped_message="Stale workspace cleanup skipped (not file): {path}",
            )
            for a in stale_actions:
                _prepare_workspace_action(
                    a,
                    workspace_name=workspace_name,
                    scope=scope,
                    removable_links=[],
                )
            actions.extend(stale_actions)

        all_stale_scopes = {
            scope
            for scope in managed_links.keys()
            if scope not in desired_paths_by_scope
            and (
                scope == "rules"
                or _workspace_scope_matches_app(scope, active_workspace_apps)
            )
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
                _prepare_workspace_action(
                    a,
                    workspace_name=workspace_name,
                    scope=scope,
                    removable_links=[],
                )
            actions.extend(stale_actions)

        all_stale_path_scopes = {
            scope
            for scope in managed_paths.keys()
            if scope not in desired_paths_by_scope
            and (
                scope == "rules"
                or _workspace_scope_matches_app(scope, active_workspace_apps)
            )
        }
        for scope in sorted(all_stale_path_scopes):
            stale_actions = plan_stale_files_group(
                old_paths=load_state_paths(managed_paths, scope),
                desired_paths=[],
                remove_detail=f"remove stale workspace {scope} file",
                conflict_detail=f"stale workspace {scope} path is not a file",
                noop_detail=f"stale workspace {scope} file already absent",
                app="workspace",
                scope=scope,
                skipped=skipped,
                skipped_message="Stale workspace cleanup skipped (not file): {path}",
            )
            for a in stale_actions:
                _prepare_workspace_action(
                    a,
                    workspace_name=workspace_name,
                    scope=scope,
                    removable_links=[],
                )
            actions.extend(stale_actions)

        return SyncPlan(actions=actions, errors=[], skipped=skipped)
