import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, Protocol

from llm_sync.constants import AGENTS_FILENAME
from llm_sync.models import Action, ActionKind, ActionStatus, SyncPlan
from llm_sync.repositories.base import ISourceRepository, ITargetRepository
from llm_sync.utils import backup_file, write_json
from llm_sync.workspaces import WorkspaceService


@dataclass
class ExecutionContext:
    common: ISourceRepository
    opencode: ITargetRepository


class ActionHandler(Protocol):
    def handle(self, action: Action, context: ExecutionContext) -> tuple[bool, Optional[str]]:
        ...


class WriteJsonHandler:
    def handle(self, action: Action, context: ExecutionContext) -> tuple[bool, Optional[str]]:
        if action.status == ActionStatus.NOOP:
            return False, None
        if action.path.exists():
            backup_file(action.path)
        write_json(action.path, action.payload)
        return True, None


class SymlinkHandler:
    def handle(self, action: Action, context: ExecutionContext) -> tuple[bool, Optional[str]]:
        if action.status == ActionStatus.NOOP:
            return False, None
        if action.status == ActionStatus.CONFLICT:
            return False, f"Conflict (not overwritten): {action.path}"
        if action.source is None:
            return False, f"Missing source for symlink action: {action.path}"

        action.path.parent.mkdir(parents=True, exist_ok=True)
        if action.path.exists() or action.path.is_symlink():
            action.path.unlink()
        action.path.symlink_to(action.source.resolve())
        return True, None


class RemoveSymlinkHandler:
    def handle(self, action: Action, context: ExecutionContext) -> tuple[bool, Optional[str]]:
        if action.status == ActionStatus.NOOP:
            return False, None
        if action.status == ActionStatus.CONFLICT:
            return False, f"Stale cleanup conflict (not symlink): {action.path}"
        if action.path.is_symlink():
            action.path.unlink()
            return True, None
        return False, None


class SyncExecutor:
    def __init__(
        self,
        common: ISourceRepository,
        opencode: ITargetRepository,
        workspace_service: Optional[WorkspaceService] = None,
    ) -> None:
        self.context = ExecutionContext(common=common, opencode=opencode)
        self.workspace_service = workspace_service or WorkspaceService()
        self.handlers: dict[ActionKind, ActionHandler] = {
            ActionKind.WRITE_JSON: WriteJsonHandler(),
            ActionKind.SYMLINK: SymlinkHandler(),
            ActionKind.REMOVE_SYMLINK: RemoveSymlinkHandler(),
        }

    def execute(self, plan: SyncPlan) -> tuple[int, int, list[str]]:
        applied = 0
        failed = 0
        failures: list[str] = []

        for action in plan.actions:
            try:
                handler = self.handlers.get(action.kind)
                if handler is None:
                    failed += 1
                    failures.append(f"Unknown action kind: {action.kind.value}")
                    continue

                changed, failure = handler.handle(action, self.context)
                if failure is not None:
                    failed += 1
                    failures.append(failure)
                    continue
                if changed:
                    applied += 1
            except Exception as exc:
                failed += 1
                failures.append(f"{action.kind.value} failed for {action.path}: {exc}")

        self._persist_state(plan=plan)
        return applied, failed, failures

    def _persist_state(self, plan: SyncPlan) -> None:
        common = self.context.common
        opencode = self.context.opencode

        managed_skill_links = self._collect_managed_links(opencode.skills_dir, common.skills_dir)
        managed_agent_links = self._collect_managed_links(opencode.agents_dir, common.agents_dir)
        managed_workspace_links = self._collect_workspace_links(common)

        updated_at = datetime.now().isoformat(timespec="seconds")
        state = {
            "updated_at": updated_at,
            "managed_skill_links": sorted(set(managed_skill_links)),
            "managed_agent_links": sorted(set(managed_agent_links)),
            "managed_workspace_links": sorted(set(managed_workspace_links)),
            "skipped": plan.skipped,
        }
        common.save_state(state)

    def _collect_workspace_links(self, common: ISourceRepository) -> list[str]:
        managed: list[str] = []
        for workspace in common.load_workspaces():
            workspace_path = Path(workspace["path"])
            if not workspace_path.exists() or not workspace_path.is_dir():
                continue
            rules_file = self.workspace_service.resolve_rules_file(workspace_path)
            if rules_file is None:
                continue
            rules_target = str(rules_file.resolve())
            for repo in self.workspace_service.discover_git_repos(workspace_path):
                target = repo / AGENTS_FILENAME
                if not target.is_symlink():
                    continue
                if os.path.realpath(target) == rules_target:
                    managed.append(str(target))
        return managed

    @staticmethod
    def _collect_managed_links(target_root: Path, source_root: Path) -> list[str]:
        if not target_root.exists():
            return []

        managed: list[str] = []
        source_prefix = str(source_root.resolve())
        for child in target_root.iterdir():
            if not child.is_symlink():
                continue
            target = os.path.realpath(child)
            if target.startswith(source_prefix):
                managed.append(str(child))
        return managed


def execute_apply(plan: SyncPlan, common: ISourceRepository, opencode: ITargetRepository) -> tuple[int, int, list[str]]:
    return SyncExecutor(common=common, opencode=opencode).execute(plan)
