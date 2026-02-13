from pathlib import Path
from typing import Optional

from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.apps.common.interfaces.service import IAppConfigService
from code_agnostic.apps.common.utils import common_mcp_to_dto
from code_agnostic.constants import AGENTS_FILENAME, WORKSPACE_RULE_FILES_DISPLAY
from code_agnostic.errors import SyncAppError
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan
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
        workspace_service: Optional[WorkspaceService] = None,
        include_workspace: bool = True,
    ) -> None:
        self.core = core
        self.app_services = app_services
        self.workspace_service = workspace_service or WorkspaceService()
        self.include_workspace = include_workspace

    def build(self) -> SyncPlan:
        app_plan = self._plan_apps()
        workspace_plan = (
            self._plan_workspace_links()
            if self.include_workspace
            else SyncPlan([], [], [])
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

    def _plan_workspace_links(self) -> SyncPlan:
        actions: list[Action] = []
        skipped: list[str] = []
        desired_workspace_links: list[Path] = []

        for workspace in self.core.load_workspaces():
            workspace_name = workspace["name"]
            workspace_path = Path(workspace["path"])
            if not workspace_path.exists() or not workspace_path.is_dir():
                skipped.append(
                    f"Workspace path missing, skipped: {workspace_name} ({workspace_path})"
                )
                continue

            rules_file = self.workspace_service.resolve_rules_file(workspace_path)
            if rules_file is None:
                skipped.append(
                    "Workspace has no rules file "
                    f"({WORKSPACE_RULE_FILES_DISPLAY}), skipped: {workspace_name}"
                )
                continue

            for repo in self.workspace_service.discover_git_repos(workspace_path):
                target = repo / AGENTS_FILENAME
                action = self._plan_symlink(target, rules_file, scope="workspace")
                action.app = "workspace"
                actions.append(action)
                desired_workspace_links.append(target)
                if action.status == ActionStatus.CONFLICT:
                    skipped.append(f"Workspace rules link skipped (conflict): {target}")

        state = self.core.load_state()
        managed_links = state.get("managed_links", {})
        if not isinstance(managed_links, dict):
            managed_links = {}
        old_links_raw = managed_links.get("workspace", [])
        old_links = [
            Path(item)
            for item in old_links_raw
            if isinstance(old_links_raw, list) and isinstance(item, str)
        ]
        actions.extend(
            self._plan_stale_group(
                old_links=old_links,
                desired_links=desired_workspace_links,
                remove_detail="remove stale managed workspace symlink",
                conflict_detail="stale workspace path is not a symlink",
                noop_detail="stale workspace symlink already absent",
                app="workspace",
                scope="workspace",
                skipped=skipped,
                skipped_message="Stale workspace cleanup skipped (not symlink): {path}",
            )
        )

        return SyncPlan(actions=actions, errors=[], skipped=skipped)

    @staticmethod
    def _plan_stale_group(
        old_links: list[Path],
        desired_links: list[Path],
        remove_detail: str,
        conflict_detail: str,
        noop_detail: str,
        app: str,
        scope: str,
        skipped: list[str],
        skipped_message: str,
    ) -> list[Action]:
        desired = {str(path) for path in desired_links}
        actions: list[Action] = []
        for old in old_links:
            if str(old) in desired:
                continue
            if old.is_symlink():
                actions.append(
                    Action(
                        ActionKind.REMOVE_SYMLINK,
                        old,
                        ActionStatus.REMOVE,
                        remove_detail,
                        app=app,
                        scope=scope,
                    )
                )
            elif old.exists():
                actions.append(
                    Action(
                        ActionKind.REMOVE_SYMLINK,
                        old,
                        ActionStatus.CONFLICT,
                        conflict_detail,
                        app=app,
                        scope=scope,
                    )
                )
                skipped.append(skipped_message.format(path=old))
            else:
                actions.append(
                    Action(
                        ActionKind.REMOVE_SYMLINK,
                        old,
                        ActionStatus.NOOP,
                        noop_detail,
                        app=app,
                        scope=scope,
                    )
                )
        return actions

    @staticmethod
    def _plan_symlink(target: Path, source: Path, scope: str) -> Action:
        desired = str(source.resolve())
        if target.exists() or target.is_symlink():
            if target.is_symlink():
                current = str(target.resolve())
                if current == desired:
                    return Action(
                        ActionKind.SYMLINK,
                        target,
                        ActionStatus.NOOP,
                        "already linked",
                        source=source,
                        scope=scope,
                    )
                return Action(
                    ActionKind.SYMLINK,
                    target,
                    ActionStatus.FIX,
                    "symlink points elsewhere",
                    source=source,
                    scope=scope,
                )
            return Action(
                ActionKind.SYMLINK,
                target,
                ActionStatus.CONFLICT,
                "non-symlink path exists",
                source=source,
                scope=scope,
            )
        return Action(
            ActionKind.SYMLINK,
            target,
            ActionStatus.CREATE,
            "create symlink",
            source=source,
            scope=scope,
        )


def build_plan(
    core: ISourceRepository, app_services: list[IAppConfigService]
) -> SyncPlan:
    return SyncPlanner(core=core, app_services=app_services).build()
