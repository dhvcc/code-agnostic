from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan
from code_agnostic.utils import backup_file, write_json


@dataclass
class ExecutionContext:
    core: ISourceRepository


class ActionHandler(Protocol):
    def handle(
        self, action: Action, context: ExecutionContext
    ) -> tuple[bool, str | None]: ...


class WriteJsonHandler:
    def handle(
        self, action: Action, context: ExecutionContext
    ) -> tuple[bool, str | None]:
        if action.status == ActionStatus.NOOP:
            return False, None
        if action.path.exists():
            backup_file(action.path)
        write_json(action.path, action.payload)
        return True, None


class SymlinkHandler:
    def handle(
        self, action: Action, context: ExecutionContext
    ) -> tuple[bool, str | None]:
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


class WriteTextHandler:
    def handle(
        self, action: Action, context: ExecutionContext
    ) -> tuple[bool, str | None]:
        if action.status == ActionStatus.NOOP:
            return False, None
        if not isinstance(action.payload, str):
            return False, f"Missing text payload for write action: {action.path}"

        if action.path.exists():
            backup_file(action.path)
        action.path.parent.mkdir(parents=True, exist_ok=True)
        action.path.write_text(action.payload, encoding="utf-8")
        return True, None


class RemoveSymlinkHandler:
    def handle(
        self, action: Action, context: ExecutionContext
    ) -> tuple[bool, str | None]:
        if action.status == ActionStatus.NOOP:
            return False, None
        if action.status == ActionStatus.CONFLICT:
            return False, f"Stale cleanup conflict (not symlink): {action.path}"
        if action.path.is_symlink():
            action.path.unlink()
            return True, None
        return False, None


class WriteRuleHandler:
    def handle(
        self, action: Action, context: ExecutionContext
    ) -> tuple[bool, str | None]:
        if action.status == ActionStatus.NOOP:
            return False, None
        if not isinstance(action.payload, str):
            return False, f"Missing rule payload for write action: {action.path}"

        action.path.parent.mkdir(parents=True, exist_ok=True)
        action.path.write_text(action.payload, encoding="utf-8")
        return True, None


class SyncExecutor:
    def __init__(self, core: ISourceRepository) -> None:
        self.context = ExecutionContext(core=core)
        self.handlers: dict[ActionKind, ActionHandler] = {
            ActionKind.WRITE_JSON: WriteJsonHandler(),
            ActionKind.WRITE_TEXT: WriteTextHandler(),
            ActionKind.WRITE_RULE: WriteRuleHandler(),
            ActionKind.SYMLINK: SymlinkHandler(),
            ActionKind.REMOVE_SYMLINK: RemoveSymlinkHandler(),
        }

    def execute(
        self, plan: SyncPlan, persist_state: bool = True
    ) -> tuple[int, int, list[str]]:
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

        if persist_state:
            self._persist_state(plan=plan)
        return applied, failed, failures

    def _persist_state(self, plan: SyncPlan) -> None:
        global_links: dict[str, list[str]] = {}
        workspace_links: dict[str, dict[str, list[str]]] = {}

        for action in plan.actions:
            if action.kind != ActionKind.SYMLINK:
                continue
            if action.scope is None:
                continue
            if not action.path.is_symlink():
                continue

            if action.workspace is not None:
                ws_name = action.workspace
                workspace_links.setdefault(ws_name, {}).setdefault(
                    action.scope, []
                ).append(str(action.path))
            else:
                global_links.setdefault(action.scope, []).append(str(action.path))

        updated_at = datetime.now().isoformat(timespec="seconds")

        # Persist global state
        core = self.context.core
        global_state = {
            "updated_at": updated_at,
            "managed_links": {
                scope: sorted(set(paths)) for scope, paths in global_links.items()
            },
            "skipped": plan.skipped,
        }
        core.save_state(global_state)

        # Persist workspace state
        for ws_name, links in workspace_links.items():
            ws_repo = WorkspaceConfigRepository(root=core.workspace_config_dir(ws_name))
            ws_state = {
                "updated_at": updated_at,
                "managed_links": {
                    scope: sorted(set(paths)) for scope, paths in links.items()
                },
            }
            ws_repo.root.mkdir(parents=True, exist_ok=True)
            ws_repo.save_state(ws_state)
