from dataclasses import dataclass
from datetime import datetime
from typing import Any
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
        global_touched_scopes: set[str] = set()
        workspace_links: dict[str, dict[str, list[str]]] = {}
        workspace_touched_scopes: dict[str, set[str]] = {}

        for action in plan.actions:
            if action.scope is None:
                continue

            if action.workspace is not None:
                ws_name = action.workspace
                workspace_touched_scopes.setdefault(ws_name, set()).add(action.scope)
                if action.kind == ActionKind.SYMLINK and action.path.is_symlink():
                    workspace_links.setdefault(ws_name, {}).setdefault(
                        action.scope, []
                    ).append(str(action.path))
            else:
                global_touched_scopes.add(action.scope)
                if action.kind == ActionKind.SYMLINK and action.path.is_symlink():
                    global_links.setdefault(action.scope, []).append(str(action.path))

        updated_at = datetime.now().isoformat(timespec="seconds")

        # Persist global state
        core = self.context.core
        existing_global_state = core.load_state()
        global_state = {
            "updated_at": updated_at,
            "managed_links": self._merge_managed_links(
                existing=existing_global_state.get("managed_links"),
                touched_scopes=global_touched_scopes,
                current_links=global_links,
            ),
            "skipped": plan.skipped,
        }
        core.save_state(global_state)

        # Persist workspace state
        for ws_name in workspace_touched_scopes:
            ws_repo = WorkspaceConfigRepository(root=core.workspace_config_dir(ws_name))
            existing_workspace_state = ws_repo.load_state()
            ws_state = {
                "updated_at": updated_at,
                "managed_links": self._merge_managed_links(
                    existing=existing_workspace_state.get("managed_links"),
                    touched_scopes=workspace_touched_scopes[ws_name],
                    current_links=workspace_links.get(ws_name, {}),
                ),
            }
            ws_repo.root.mkdir(parents=True, exist_ok=True)
            ws_repo.save_state(ws_state)

    @staticmethod
    def _merge_managed_links(
        *,
        existing: Any,
        touched_scopes: set[str],
        current_links: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        merged: dict[str, list[str]] = {}

        if isinstance(existing, dict):
            for scope, paths in existing.items():
                if scope in touched_scopes or not isinstance(scope, str):
                    continue
                if not isinstance(paths, list):
                    continue
                kept_paths = sorted({path for path in paths if isinstance(path, str)})
                if kept_paths:
                    merged[scope] = kept_paths

        for scope, paths in current_links.items():
            current = sorted({path for path in paths if isinstance(path, str)})
            if current:
                merged[scope] = current

        return merged
