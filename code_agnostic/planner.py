import os
from pathlib import Path
from typing import Optional

from jsonschema import Draft202012Validator

from code_agnostic.apps.common.interfaces.mapper import IConfigMapper
from code_agnostic.apps.common.interfaces.repositories import (
    ISourceRepository,
    ITargetRepository,
)
from code_agnostic.apps.opencode.config_mapper import OpenCodeMapper
from code_agnostic.apps.opencode.schema_repository import OpenCodeSchemaRepository
from code_agnostic.apps.opencode.service import validate_opencode_config
from code_agnostic.constants import AGENTS_FILENAME, WORKSPACE_RULE_FILES_DISPLAY
from code_agnostic.errors import SyncAppError
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan, SyncTarget
from code_agnostic.utils import is_under, same_json
from code_agnostic.workspaces import WorkspaceService


def _canonical_target(path: Path) -> str:
    return str(path.resolve())


class SyncPlanner:
    def __init__(
        self,
        core: ISourceRepository,
        opencode: ITargetRepository,
        mapper: Optional[IConfigMapper] = None,
        workspace_service: Optional[WorkspaceService] = None,
        include_opencode: bool = True,
        include_workspace: bool = True,
    ) -> None:
        self.core = core
        self.opencode = opencode
        self.mapper = mapper or OpenCodeMapper()
        self.workspace_service = workspace_service or WorkspaceService()
        self.include_opencode = include_opencode
        self.include_workspace = include_workspace

        self.actions: list[Action] = []
        self.errors: list[Exception] = []
        self.skipped: list[str] = []

        self._desired_skill_links: list[Path] = []
        self._desired_agent_links: list[Path] = []
        self._desired_workspace_links: list[Path] = []

    def build(self) -> SyncPlan:
        if self.include_opencode:
            self._plan_opencode_config()
            self._plan_skills_links()
            self._plan_agents_links()
        if self.include_workspace:
            self._plan_workspace_links()
        self._plan_stale_cleanup(
            include_opencode=self.include_opencode,
            include_workspace=self.include_workspace,
        )
        return SyncPlan(actions=self.actions, errors=self.errors, skipped=self.skipped)

    def _plan_opencode_config(self) -> None:
        try:
            mcp_base = self.core.load_mcp_base()
            opencode_base = self.core.load_opencode_base()
        except SyncAppError as exc:
            self.errors.append(exc)
            return
        mapped_mcp = self.mapper.map_mcp_servers(mcp_base["mcpServers"])

        schema_validator = Draft202012Validator(
            OpenCodeSchemaRepository().load_schema()
        )

        existing_config, config_error = self.opencode.load_config_object()
        if config_error is not None:
            self.errors.append(config_error)
            return

        try:
            validate_opencode_config(
                existing_config, self.opencode.config_path, schema_validator
            )
        except Exception as exc:
            self.errors.append(exc)
            return

        merged_config = self.opencode.merge_config(
            existing_config, opencode_base, mapped_mcp
        )
        try:
            validate_opencode_config(
                merged_config, self.opencode.config_path, schema_validator
            )
        except Exception as exc:
            self.errors.append(exc)
            return

        if same_json(self.opencode.config_path, merged_config):
            self.actions.append(
                Action(
                    ActionKind.WRITE_JSON,
                    self.opencode.config_path,
                    ActionStatus.NOOP,
                    "already in sync",
                    payload=merged_config,
                    app=SyncTarget.OPENCODE.value,
                )
            )
            return

        status = (
            ActionStatus.CREATE
            if not self.opencode.config_path.exists()
            else ActionStatus.UPDATE
        )
        self.actions.append(
            Action(
                ActionKind.WRITE_JSON,
                self.opencode.config_path,
                status,
                "merge opencode base + canonical mcp",
                payload=merged_config,
                app=SyncTarget.OPENCODE.value,
            )
        )

    def _plan_skills_links(self) -> None:
        skill_sources = self.core.list_skill_sources()
        mapped_skill_sources = [
            self.mapper.map_skill_source(source) for source in skill_sources
        ]
        self._desired_skill_links = [
            self.opencode.skills_dir / source.name for source in mapped_skill_sources
        ]
        for source in mapped_skill_sources:
            action = self._plan_symlink(self.opencode.skills_dir / source.name, source)
            action.app = SyncTarget.OPENCODE.value
            self.actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                self.skipped.append(f"Skill link skipped (conflict): {action.path}")

    def _plan_agents_links(self) -> None:
        agent_sources = self.core.list_agent_sources()
        mapped_agent_sources = [
            self.mapper.map_agent_source(source) for source in agent_sources
        ]
        self._desired_agent_links = [
            self.opencode.agents_dir / source.name for source in mapped_agent_sources
        ]
        for source in mapped_agent_sources:
            action = self._plan_symlink(self.opencode.agents_dir / source.name, source)
            action.app = SyncTarget.OPENCODE.value
            self.actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                self.skipped.append(f"Agent link skipped (conflict): {action.path}")

    def _plan_workspace_links(self) -> None:
        for workspace in self.core.load_workspaces():
            workspace_name = workspace["name"]
            workspace_path = Path(workspace["path"])
            if not workspace_path.exists() or not workspace_path.is_dir():
                self.skipped.append(
                    f"Workspace path missing, skipped: {workspace_name} ({workspace_path})"
                )
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
                action.app = "workspace"
                self.actions.append(action)
                self._desired_workspace_links.append(target)
                if action.status == ActionStatus.CONFLICT:
                    self.skipped.append(
                        f"Workspace rules link skipped (conflict): {target}"
                    )

    def _plan_stale_cleanup(
        self, include_opencode: bool, include_workspace: bool
    ) -> None:
        state = self.core.load_state()
        if include_opencode:
            opencode_roots = [
                self.opencode.skills_dir.resolve(),
                self.opencode.agents_dir.resolve(),
            ]
            self._plan_stale_group(
                [
                    Path(item)
                    for item in state.get("managed_skill_links", [])
                    if isinstance(item, str)
                ],
                self._desired_skill_links,
                "remove stale managed skill symlink",
                "stale managed path is not a symlink",
                "stale symlink already absent",
                "Stale link cleanup skipped (not symlink): {path}",
                enforce_under_roots=opencode_roots,
                app=SyncTarget.OPENCODE.value,
            )
            self._plan_stale_group(
                [
                    Path(item)
                    for item in state.get("managed_agent_links", [])
                    if isinstance(item, str)
                ],
                self._desired_agent_links,
                "remove stale managed agent symlink",
                "stale managed path is not a symlink",
                "stale symlink already absent",
                "Stale link cleanup skipped (not symlink): {path}",
                enforce_under_roots=opencode_roots,
                app=SyncTarget.OPENCODE.value,
            )
        if include_workspace:
            self._plan_stale_group(
                [
                    Path(item)
                    for item in state.get("managed_workspace_links", [])
                    if isinstance(item, str)
                ],
                self._desired_workspace_links,
                "remove stale managed workspace symlink",
                "stale workspace path is not a symlink",
                "stale workspace symlink already absent",
                "Stale workspace cleanup skipped (not symlink): {path}",
                app="workspace",
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
        app: Optional[str] = None,
    ) -> None:
        desired = {str(path) for path in desired_links}
        for old in old_links:
            if str(old) in desired:
                continue
            if enforce_under_roots and not any(
                is_under(old, root) for root in enforce_under_roots
            ):
                continue
            if old.is_symlink():
                self.actions.append(
                    Action(
                        ActionKind.REMOVE_SYMLINK,
                        old,
                        ActionStatus.REMOVE,
                        remove_detail,
                        app=app,
                    )
                )
            elif old.exists():
                self.actions.append(
                    Action(
                        ActionKind.REMOVE_SYMLINK,
                        old,
                        ActionStatus.CONFLICT,
                        conflict_detail,
                        app=app,
                    )
                )
                self.skipped.append(skipped_message.format(path=old))
            else:
                self.actions.append(
                    Action(
                        ActionKind.REMOVE_SYMLINK,
                        old,
                        ActionStatus.NOOP,
                        noop_detail,
                        app=app,
                    )
                )

    @staticmethod
    def _plan_symlink(target: Path, source: Path) -> Action:
        desired = _canonical_target(source)
        if target.exists() or target.is_symlink():
            if target.is_symlink():
                current = os.path.realpath(target)
                if current == desired:
                    return Action(
                        ActionKind.SYMLINK,
                        target,
                        ActionStatus.NOOP,
                        "already linked",
                        source=source,
                    )
                return Action(
                    ActionKind.SYMLINK,
                    target,
                    ActionStatus.FIX,
                    "symlink points elsewhere",
                    source=source,
                )
            return Action(
                ActionKind.SYMLINK,
                target,
                ActionStatus.CONFLICT,
                "non-symlink path exists",
                source=source,
            )
        return Action(
            ActionKind.SYMLINK,
            target,
            ActionStatus.CREATE,
            "create symlink",
            source=source,
        )


def build_plan(
    core: ISourceRepository,
    opencode: ITargetRepository,
    mapper: Optional[IConfigMapper] = None,
) -> SyncPlan:
    return SyncPlanner(core=core, opencode=opencode, mapper=mapper).build()


def filter_plan_for_target(
    plan: SyncPlan, target: str, opencode: ITargetRepository
) -> SyncPlan:
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
