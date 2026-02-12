import os
from pathlib import Path
from typing import Optional

from llm_sync.constants import AGENTS_FILENAME, WORKSPACE_RULE_FILES_DISPLAY
from llm_sync.errors import SyncAppError
from llm_sync.mappers.base import IConfigMapper
from llm_sync.mappers.opencode import OpenCodeMapper
from llm_sync.models import Action, ActionKind, ActionStatus, SyncPlan, SyncTarget
from llm_sync.repositories.base import ISourceRepository, ITargetRepository
from llm_sync.utils import is_under, same_json
from llm_sync.workspaces import WorkspaceService


def _canonical_target(path: Path) -> str:
    return str(path.resolve())


class SyncPlanner:
    def __init__(
        self,
        common: ISourceRepository,
        opencode: ITargetRepository,
        mapper: Optional[IConfigMapper] = None,
        workspace_service: Optional[WorkspaceService] = None,
    ) -> None:
        self.common = common
        self.opencode = opencode
        self.mapper = mapper or OpenCodeMapper()
        self.workspace_service = workspace_service or WorkspaceService()

        self.actions: list[Action] = []
        self.errors: list[Exception] = []
        self.skipped: list[str] = []

        self._desired_skill_links: list[Path] = []
        self._desired_agent_links: list[Path] = []
        self._desired_workspace_links: list[Path] = []

    def build(self) -> SyncPlan:
        self._plan_opencode_config()
        self._plan_skills_links()
        self._plan_agents_links()
        self._plan_workspace_links()
        self._plan_stale_cleanup()
        return SyncPlan(actions=self.actions, errors=self.errors, skipped=self.skipped)

    def _plan_opencode_config(self) -> None:
        try:
            mcp_base = self.common.load_mcp_base()
            opencode_base = self.common.load_opencode_base()
        except SyncAppError as exc:
            self.errors.append(exc)
            return
        mapped_mcp = self.mapper.map_mcp_servers(mcp_base["mcpServers"])

        existing_config, config_error = self.opencode.load_config_object()
        if config_error is not None:
            self.errors.append(config_error)
            return

        merged_config = self.opencode.merge_config(existing_config, opencode_base, mapped_mcp)
        if same_json(self.opencode.config_path, merged_config):
            self.actions.append(
                Action(
                    ActionKind.WRITE_JSON,
                    self.opencode.config_path,
                    ActionStatus.NOOP,
                    "already in sync",
                    payload=merged_config,
                )
            )
            return

        status = ActionStatus.CREATE if not self.opencode.config_path.exists() else ActionStatus.UPDATE
        self.actions.append(
            Action(
                ActionKind.WRITE_JSON,
                self.opencode.config_path,
                status,
                "merge opencode base + canonical mcp",
                payload=merged_config,
            )
        )

    def _plan_skills_links(self) -> None:
        skill_sources = self.common.list_skill_sources()
        mapped_skill_sources = [self.mapper.map_skill_source(source) for source in skill_sources]
        self._desired_skill_links = [self.opencode.skills_dir / source.name for source in mapped_skill_sources]
        for source in mapped_skill_sources:
            action = self._plan_symlink(self.opencode.skills_dir / source.name, source)
            self.actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                self.skipped.append(f"Skill link skipped (conflict): {action.path}")

    def _plan_agents_links(self) -> None:
        agent_sources = self.common.list_agent_sources()
        mapped_agent_sources = [self.mapper.map_agent_source(source) for source in agent_sources]
        self._desired_agent_links = [self.opencode.agents_dir / source.name for source in mapped_agent_sources]
        for source in mapped_agent_sources:
            action = self._plan_symlink(self.opencode.agents_dir / source.name, source)
            self.actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                self.skipped.append(f"Agent link skipped (conflict): {action.path}")

    def _plan_workspace_links(self) -> None:
        for workspace in self.common.load_workspaces():
            workspace_name = workspace["name"]
            workspace_path = Path(workspace["path"])
            if not workspace_path.exists() or not workspace_path.is_dir():
                self.skipped.append(f"Workspace path missing, skipped: {workspace_name} ({workspace_path})")
                continue

            rules_file = self.workspace_service.resolve_rules_file(workspace_path)
            if rules_file is None:
                self.skipped.append(
                    f"Workspace has no rules file ({WORKSPACE_RULE_FILES_DISPLAY}), skipped: {workspace_name}"
                )
                continue
            mapped_rules_file = self.mapper.map_workspace_rules_source(rules_file)

            for repo in self.workspace_service.discover_git_repos(workspace_path):
                target = repo / AGENTS_FILENAME
                action = self._plan_symlink(target, mapped_rules_file)
                self.actions.append(action)
                self._desired_workspace_links.append(target)
                if action.status == ActionStatus.CONFLICT:
                    self.skipped.append(f"Workspace rules link skipped (conflict): {target}")

    def _plan_stale_cleanup(self) -> None:
        state = self.common.load_state()
        opencode_roots = [self.opencode.skills_dir.resolve(), self.opencode.agents_dir.resolve()]

        self._plan_stale_group(
            [Path(item) for item in state.get("managed_skill_links", []) if isinstance(item, str)],
            self._desired_skill_links,
            "remove stale managed skill symlink",
            "stale managed path is not a symlink",
            "stale symlink already absent",
            "Stale link cleanup skipped (not symlink): {path}",
            enforce_under_roots=opencode_roots,
        )
        self._plan_stale_group(
            [Path(item) for item in state.get("managed_agent_links", []) if isinstance(item, str)],
            self._desired_agent_links,
            "remove stale managed agent symlink",
            "stale managed path is not a symlink",
            "stale symlink already absent",
            "Stale link cleanup skipped (not symlink): {path}",
            enforce_under_roots=opencode_roots,
        )
        self._plan_stale_group(
            [Path(item) for item in state.get("managed_workspace_links", []) if isinstance(item, str)],
            self._desired_workspace_links,
            "remove stale managed workspace symlink",
            "stale workspace path is not a symlink",
            "stale workspace symlink already absent",
            "Stale workspace cleanup skipped (not symlink): {path}",
        )

    def _plan_stale_group(
        self,
        old_links: list[Path],
        desired_links: list[Path],
        remove_detail: str,
        conflict_detail: str,
        noop_detail: str,
        skipped_message: str,
        enforce_under_roots: Optional[list[Path]] = None,
    ) -> None:
        desired = {str(path) for path in desired_links}
        for old in old_links:
            if str(old) in desired:
                continue
            if enforce_under_roots and not any(is_under(old, root) for root in enforce_under_roots):
                continue
            if old.is_symlink():
                self.actions.append(Action(ActionKind.REMOVE_SYMLINK, old, ActionStatus.REMOVE, remove_detail))
            elif old.exists():
                self.actions.append(Action(ActionKind.REMOVE_SYMLINK, old, ActionStatus.CONFLICT, conflict_detail))
                self.skipped.append(skipped_message.format(path=old))
            else:
                self.actions.append(Action(ActionKind.REMOVE_SYMLINK, old, ActionStatus.NOOP, noop_detail))

    @staticmethod
    def _plan_symlink(target: Path, source: Path) -> Action:
        desired = _canonical_target(source)
        if target.exists() or target.is_symlink():
            if target.is_symlink():
                current = os.path.realpath(target)
                if current == desired:
                    return Action(ActionKind.SYMLINK, target, ActionStatus.NOOP, "already linked", source=source)
                return Action(ActionKind.SYMLINK, target, ActionStatus.FIX, "symlink points elsewhere", source=source)
            return Action(ActionKind.SYMLINK, target, ActionStatus.CONFLICT, "non-symlink path exists", source=source)
        return Action(ActionKind.SYMLINK, target, ActionStatus.CREATE, "create symlink", source=source)


def build_plan(common: ISourceRepository, opencode: ITargetRepository, mapper: Optional[IConfigMapper] = None) -> SyncPlan:
    return SyncPlanner(common=common, opencode=opencode, mapper=mapper).build()


def filter_plan_for_target(plan: SyncPlan, target: str, opencode: ITargetRepository) -> SyncPlan:
    try:
        normalized_target = SyncTarget(target)
    except ValueError:
        return SyncPlan(actions=[], errors=plan.errors, skipped=plan.skipped)
    return plan.filter_for_target(
        target=normalized_target,
        config_path=opencode.config_path,
        skills_root=opencode.skills_dir,
        agents_root=opencode.agents_dir,
    )
