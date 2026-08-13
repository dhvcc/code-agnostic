from pathlib import Path
from typing import Any

from code_agnostic.apps.app_id import AppId, app_ids_by_capability, app_scope
from code_agnostic.apps.common.framework import (
    create_registered_app_service,
    list_registered_app_services,
)
from code_agnostic.apps.claude.service import ClaudeConfigService
from code_agnostic.apps.common.interfaces.service import IAppConfigService
from code_agnostic.apps.common.symlink_planning import (
    load_state_links,
    load_state_paths,
    plan_stale_files_group,
    plan_stale_group,
)
from code_agnostic.core.project_repository import ProjectConfigRepository
from code_agnostic.core.repository import CoreRepository
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.executor import SyncExecutor
from code_agnostic.models import Action, AppStatusRow, AppSyncStatus, SyncPlan
from code_agnostic.planner import SyncPlanner
from code_agnostic.project_artifacts import load_project_entries, project_config_dir
from code_agnostic.utils import read_json_safe, write_json


class AppsService:
    def __init__(self, core_repository: CoreRepository) -> None:
        self.core_repository = core_repository

    @property
    def apps_path(self) -> Path:
        return self.core_repository.root / "config" / "apps.json"

    def available_apps(self) -> list[str]:
        registered = set(list_registered_app_services())
        manageable = set(app_ids_by_capability(toggleable=True))
        return [
            app.value
            for app in sorted(registered & manageable, key=lambda item: item.value)
        ]

    def load_apps(self) -> dict[str, bool]:
        payload, error = read_json_safe(self.apps_path)
        if error is not None or not isinstance(payload, dict):
            return self._default_apps()

        result = self._default_apps()
        for app_name in self.available_apps():
            value = payload.get(app_name)
            if isinstance(value, bool):
                result[app_name] = value
        return result

    def save_apps(self, apps: dict[str, bool]) -> None:
        normalized = self._default_apps()
        for app_name in self.available_apps():
            value = apps.get(app_name)
            if isinstance(value, bool):
                normalized[app_name] = value
        write_json(self.apps_path, normalized)

    def is_enabled(self, app_name: str) -> bool:
        return self.load_apps().get(app_name, False)

    def set_enabled(self, app_name: str, enabled: bool) -> None:
        if app_name not in self.available_apps():
            raise ValueError(f"Unknown app: {app_name}")
        apps = self.load_apps()
        apps[app_name] = enabled
        self.save_apps(apps)

    def enable(self, app_name: str) -> None:
        self.set_enabled(app_name=app_name, enabled=True)

    def disable(self, app_name: str) -> tuple[int, int, list[str]]:
        """Disable an app AND clean up everything it previously synced.

        Removes tracked skills/agents/compiled files and prunes the MCP servers
        we own from the app's shared config, across global, workspace, and
        project scopes, then clears the corresponding state. Without this,
        disabling would strand orphaned artifacts with no way to reclaim them.
        """
        normalized = app_name.lower()
        plan = self._plan_app_cleanup(normalized)
        result: tuple[int, int, list[str]] = (0, 0, [])
        if plan.actions:
            result = SyncExecutor(core=self.core_repository).execute(
                plan, persist_state=True
            )
        self.set_enabled(app_name=normalized, enabled=False)
        return result

    def _plan_app_cleanup(self, app_name: str) -> SyncPlan:
        try:
            app_id = AppId(app_name)
        except ValueError:
            return SyncPlan([], [], [])

        actions: list[Action] = []
        skipped: list[str] = []
        core = self.core_repository

        # --- Global scopes (app:<app>:*) ---
        global_state = core.load_state()
        global_links = global_state.managed_links
        global_paths = global_state.managed_paths
        global_mcp = global_state.managed_mcp
        global_prefix = f"app:{app_id.value}:"
        for scope in sorted(s for s in global_links if s.startswith(global_prefix)):
            actions.extend(self._cleanup_links(global_links, scope, app_id.value))
        for scope in sorted(s for s in global_paths if s.startswith(global_prefix)):
            actions.extend(
                self._cleanup_paths(global_paths, scope, app_id.value, skipped)
            )
        actions.extend(self._cleanup_global_mcp(app_id, global_mcp))
        if app_id == AppId.CLAUDE:
            actions.extend(self._cleanup_claude_projects(global_mcp))

        # --- Workspace scopes (ws:<app>:*) ---
        ws_prefix = f"ws:{app_id.value}:"
        for workspace in core.load_workspaces():
            ws_name = workspace.name
            ws_repo = WorkspaceConfigRepository(root=core.workspace_config_dir(ws_name))
            ws_state = ws_repo.load_state()
            ws_links = ws_state.managed_links
            ws_paths = ws_state.managed_paths
            for scope in sorted(s for s in ws_links if s.startswith(ws_prefix)):
                for action in self._cleanup_links(ws_links, scope, "workspace"):
                    action.workspace = ws_name
                    actions.append(action)
            for scope in sorted(s for s in ws_paths if s.startswith(ws_prefix)):
                for action in self._cleanup_paths(
                    ws_paths, scope, "workspace", skipped
                ):
                    action.workspace = ws_name
                    actions.append(action)

        # --- Project scopes (project:<app>:*) ---
        project_prefix = f"project:{app_id.value}:"
        for project in load_project_entries(core):
            project_name = project.name
            project_repo = ProjectConfigRepository(
                root=project_config_dir(core, project_name)
            )
            project_state = project_repo.load_state()
            project_links = project_state.managed_links
            project_paths = project_state.managed_paths
            for scope in sorted(
                s for s in project_links if s.startswith(project_prefix)
            ):
                for action in self._cleanup_links(project_links, scope, app_id.value):
                    action.project = project_name
                    actions.append(action)
            for scope in sorted(
                s for s in project_paths if s.startswith(project_prefix)
            ):
                for action in self._cleanup_paths(
                    project_paths, scope, app_id.value, skipped
                ):
                    action.project = project_name
                    actions.append(action)

        return SyncPlan(actions=actions, errors=[], skipped=skipped)

    @staticmethod
    def _cleanup_links(group: dict[str, Any], scope: str, app: str) -> list[Action]:
        return plan_stale_group(
            old_links=load_state_links(group, scope),
            desired_links=[],
            remove_detail=f"remove {scope} symlink on disable",
            conflict_detail="managed path is not a symlink",
            noop_detail="managed symlink already absent",
            app=app,
            scope=scope,
            skipped=[],
            skipped_message="Disable cleanup skipped (not symlink): {path}",
        )

    @staticmethod
    def _cleanup_paths(
        group: dict[str, Any], scope: str, app: str, skipped: list[str]
    ) -> list[Action]:
        return plan_stale_files_group(
            old_paths=load_state_paths(group, scope),
            desired_paths=[],
            remove_detail=f"remove {scope} file on disable",
            conflict_detail="managed path is not a file",
            noop_detail="managed file already absent",
            app=app,
            scope=scope,
            skipped=skipped,
            skipped_message="Disable cleanup skipped (not file): {path}",
        )

    def _cleanup_global_mcp(
        self, app_id: AppId, managed_mcp: dict[str, Any]
    ) -> list[Action]:
        managed = self._names_for_scope(managed_mcp, app_scope(app_id, "mcp"))
        managed_agents = self._names_for_scope(
            managed_mcp, app_scope(app_id, "agents_registry")
        )
        if not managed and not managed_agents:
            return []
        try:
            service = create_registered_app_service(app_id)
        except (KeyError, ValueError):
            return []
        if not service.repository.config_path.exists():
            return []
        # Empty desired + our previously-managed names → prune only what we wrote
        # (MCP servers and agent-registry entries), keep the user's, and clear the
        # ownership state (managed_entries becomes empty).
        return [
            service.build_action(
                {},
                previously_managed=managed,
                previously_managed_agents=managed_agents,
            )
        ]

    def _cleanup_claude_projects(self, managed_mcp: dict[str, Any]) -> list[Action]:
        managed = self._names_for_scope(
            managed_mcp, app_scope(AppId.CLAUDE, "projects")
        )
        if not managed:
            return []
        try:
            service = create_registered_app_service(AppId.CLAUDE)
        except (KeyError, ValueError):
            return []
        if not isinstance(service, ClaudeConfigService):
            return []
        if not service.repository.config_path.exists():
            return []
        # Empty desired + our previously-managed project paths → prune only the
        # `mcpServers` sub-keys we wrote, keep the rest of each project entry, and
        # clear the ownership state (managed_entries becomes empty).
        return [
            service.build_project_mcp_action({}, previously_managed_projects=managed)
        ]

    @staticmethod
    def _names_for_scope(group: dict[str, Any], scope: str) -> set[str]:
        raw = group.get(scope, [])
        if not isinstance(raw, list):
            return set()
        return {item for item in raw if isinstance(item, str)}

    def list_status_rows(self) -> list[AppStatusRow]:
        apps = self.load_apps()
        rows: list[AppStatusRow] = []
        for app_name in self.available_apps():
            enabled = apps.get(app_name, False)
            detail = "enabled by user" if enabled else "disabled by default"
            rows.append(
                AppStatusRow(
                    name=app_name,
                    status=AppSyncStatus.ENABLED if enabled else AppSyncStatus.DISABLED,
                    detail=detail,
                )
            )
        return rows

    def enabled_apps(self) -> list[str]:
        apps = self.load_apps()
        return [name for name in self.available_apps() if apps.get(name, False)]

    def _plan_disabled_app_cleanup(self) -> SyncPlan:
        apps = self.load_apps()
        plans = [
            self._plan_app_cleanup(app_name)
            for app_name in self.available_apps()
            if not apps.get(app_name, False)
        ]
        return SyncPlan(
            actions=[action for plan in plans for action in plan.actions],
            errors=[error for plan in plans for error in plan.errors],
            skipped=[item for plan in plans for item in plan.skipped],
        )

    def plan_for_target(self, target: str, *, apply_excludes: bool = False) -> SyncPlan:
        normalized = target.lower()
        if normalized != "all" and not self.is_enabled(normalized):
            return SyncPlan([], [], [f"{normalized} is disabled for sync."])

        app_services = self._resolve_services_for_target(normalized)
        plan = SyncPlanner(
            core=self.core_repository,
            app_services=app_services,
            include_workspace=True,
            include_git_excludes=apply_excludes,
        ).build()
        if normalized == "all":
            cleanup = self._plan_disabled_app_cleanup()
            plan = SyncPlan(
                actions=[*plan.actions, *cleanup.actions],
                errors=[*plan.errors, *cleanup.errors],
                skipped=[*plan.skipped, *cleanup.skipped],
            )
            if (
                not app_services
                and not plan.actions
                and not plan.errors
                and not plan.skipped
            ):
                return SyncPlan([], [], ["No apps enabled for sync."])
            return plan
        return plan.filter_for_target(normalized)

    def execute_plan(self, scoped_plan: SyncPlan) -> tuple[int, int, list[str]]:
        persist_state = self._requires_state_persist(scoped_plan)
        return SyncExecutor(core=self.core_repository).execute(
            scoped_plan, persist_state=persist_state
        )

    def _resolve_services_for_target(self, target: str) -> list[IAppConfigService]:
        enabled = set(self.enabled_apps())
        if target == "all":
            selected = enabled
        else:
            selected = {target} if target in enabled else set()

        services: list[IAppConfigService] = []
        for app in sorted(selected):
            try:
                services.append(create_registered_app_service(AppId(app)))
            except (KeyError, ValueError):
                continue
        return services

    @staticmethod
    def _requires_state_persist(scoped_plan: SyncPlan) -> bool:
        return any(
            action.kind.value in ("symlink", "remove_symlink") or action.app is not None
            for action in scoped_plan.actions
        )

    def _default_apps(self) -> dict[str, bool]:
        return {name: False for name in self.available_apps()}
