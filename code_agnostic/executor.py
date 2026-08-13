from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from typing import Protocol

from code_agnostic.constants import (
    SYNC_LOCK_FILENAME,
    SYNC_REVISIONS_DIRNAME,
    SYNC_STAGING_DIRNAME,
    SYNC_STATE_FILENAME,
)
from code_agnostic.core.project_repository import ProjectConfigRepository
from code_agnostic.core.repository import CoreRepository
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan
from code_agnostic.utils import file_lock, write_json


@dataclass
class ExecutionContext:
    core: CoreRepository


@dataclass(frozen=True)
class PathSnapshot:
    path: Path
    existed: bool
    is_symlink: bool
    symlink_target: str | None = None
    content: bytes | None = None


@dataclass(frozen=True)
class RevisionRecord:
    root: Path
    workspace: str | None
    project: str | None
    revision_id: str
    manifest_path: Path
    active_path: Path
    pending_path: Path
    artifacts_root: Path


@dataclass(frozen=True)
class StoredRevision:
    revision_id: str
    manifest_path: Path
    state: dict[str, Any] | None
    targets: list[dict[str, Any]]


@dataclass(frozen=True)
class RestoreResult:
    revision_id: str
    restored: int


@dataclass(frozen=True)
class StagedAction:
    action: Action
    staged_path: Path | None = None


def _write_text_utf8(path: Path, payload: str) -> None:
    path.write_text(payload, encoding="utf-8", newline="")


def _remove_tree(root: Path) -> None:
    for child in sorted(
        root.rglob("*"),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    root.rmdir()


def _symlink_target_path(path: Path, target: str) -> Path:
    target_path = Path(target)
    if target_path.is_absolute():
        return target_path
    return path.parent / target_path


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
        if action.status == ActionStatus.CONFLICT:
            return False, None
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
        if action.status == ActionStatus.CONFLICT:
            return False, None
        if not isinstance(action.payload, str):
            return False, f"Missing text payload for write action: {action.path}"

        action.path.parent.mkdir(parents=True, exist_ok=True)
        _write_text_utf8(action.path, action.payload)
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


class RemoveFileHandler:
    def handle(
        self, action: Action, context: ExecutionContext
    ) -> tuple[bool, str | None]:
        if action.status == ActionStatus.NOOP:
            return False, None
        if action.status == ActionStatus.CONFLICT:
            return False, f"Stale cleanup conflict (not file): {action.path}"
        if action.path.is_file() or action.path.is_symlink():
            action.path.unlink()
            return True, None
        if action.path.is_dir():
            _remove_tree(action.path)
            return True, None
        return False, None


class WriteRuleHandler:
    def handle(
        self, action: Action, context: ExecutionContext
    ) -> tuple[bool, str | None]:
        if action.status == ActionStatus.NOOP:
            return False, None
        if action.status == ActionStatus.CONFLICT:
            return False, None
        if not isinstance(action.payload, str):
            return False, f"Missing rule payload for write action: {action.path}"

        action.path.parent.mkdir(parents=True, exist_ok=True)
        _write_text_utf8(action.path, action.payload)
        return True, None


class SyncExecutor:
    def __init__(self, core: CoreRepository) -> None:
        self.context = ExecutionContext(core=core)
        self.handlers: dict[ActionKind, ActionHandler] = {
            ActionKind.WRITE_JSON: WriteJsonHandler(),
            ActionKind.WRITE_TEXT: WriteTextHandler(),
            ActionKind.WRITE_RULE: WriteRuleHandler(),
            ActionKind.SYMLINK: SymlinkHandler(),
            ActionKind.REMOVE_SYMLINK: RemoveSymlinkHandler(),
            ActionKind.REMOVE_FILE: RemoveFileHandler(),
        }

    def execute(
        self, plan: SyncPlan, persist_state: bool = True
    ) -> tuple[int, int, list[str]]:
        if not persist_state:
            return self._execute(plan, persist_state=persist_state)
        # Serialize concurrent applies so they can't race on shared sync state.
        lock_path = self.context.core.root / SYNC_LOCK_FILENAME
        with file_lock(lock_path):
            return self._execute(plan, persist_state=persist_state)

    def _execute(
        self, plan: SyncPlan, persist_state: bool = True
    ) -> tuple[int, int, list[str]]:
        applied = 0
        failed = 0
        failures: list[str] = []
        revision_records = self._prepare_revision_records(plan, persist_state)
        try:
            self._repair_pending_revisions(revision_records)
        except Exception as exc:
            return 0, 1, [f"pending revision repair failed: {exc}"]
        conflict_failures = self._planned_conflict_failures(plan)
        if conflict_failures:
            return 0, len(conflict_failures), conflict_failures
        previous_revisions = self._load_previous_revisions(revision_records)
        snapshots = self._capture_snapshots(
            plan=plan,
            persist_state=persist_state,
            revision_records=revision_records,
        )
        staging_id = (
            revision_records[0].revision_id
            if revision_records
            else datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        )
        staging_dirs: set[Path] = set()

        try:
            if persist_state:
                self._mark_pending_revisions(revision_records)
            staged_actions, failure = self._stage_actions(
                plan=plan,
                revision_records=revision_records,
                staging_id=staging_id,
                staging_dirs=staging_dirs,
            )
            if failure is not None:
                self._rollback(snapshots, previous_revisions)
                self._clear_pending_revisions(revision_records)
                return 0, 1, [failure]

            for staged_action in self._ordered_staged_actions(staged_actions):
                action = staged_action.action
                try:
                    changed, failure = self._apply_staged_action(staged_action)
                    if failure is not None:
                        self._rollback(snapshots, previous_revisions)
                        self._clear_pending_revisions(revision_records)
                        return 0, 1, [failure]
                    if changed:
                        applied += 1
                except Exception as exc:
                    self._rollback(snapshots, previous_revisions)
                    self._clear_pending_revisions(revision_records)
                    return (
                        0,
                        1,
                        [f"{action.kind.value} failed for {action.path}: {exc}"],
                    )

            if persist_state:
                try:
                    self._persist_state(
                        plan=plan,
                        revision_records=revision_records,
                        staging_id=staging_id,
                        staging_dirs=staging_dirs,
                    )
                except Exception as exc:
                    self._rollback(snapshots, previous_revisions)
                    self._clear_pending_revisions(revision_records)
                    return 0, 1, [f"persist_state failed: {exc}"]
            self._clear_pending_revisions(revision_records)
            return applied, failed, failures
        finally:
            self._cleanup_staging_dirs(staging_dirs)

    def _planned_conflict_failures(self, plan: SyncPlan) -> list[str]:
        return [
            f"Conflict (not overwritten): {action.path} ({action.detail})"
            for action in plan.actions
            if action.status == ActionStatus.CONFLICT
        ]

    def _ordered_staged_actions(
        self, staged_actions: list[StagedAction]
    ) -> list[StagedAction]:
        removals = [
            action
            for action in staged_actions
            if action.action.kind in {ActionKind.REMOVE_FILE, ActionKind.REMOVE_SYMLINK}
        ]
        others = [
            action
            for action in staged_actions
            if action.action.kind
            not in {ActionKind.REMOVE_FILE, ActionKind.REMOVE_SYMLINK}
        ]
        return removals + others

    def _prepare_revision_records(
        self, plan: SyncPlan, persist_state: bool
    ) -> list[RevisionRecord]:
        if not persist_state:
            return []

        records: list[RevisionRecord] = []
        revision_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        if any(
            action.workspace is None and action.project is None
            for action in plan.actions
        ):
            records.append(
                self._build_revision_record(
                    root=self.context.core.root,
                    workspace=None,
                    project=None,
                    revision_id=revision_id,
                )
            )

        for workspace_name in sorted(
            {
                action.workspace
                for action in plan.actions
                if action.workspace is not None
            }
        ):
            workspace_root = self.context.core.workspace_config_dir(workspace_name)
            records.append(
                self._build_revision_record(
                    root=workspace_root,
                    workspace=workspace_name,
                    project=None,
                    revision_id=revision_id,
                )
            )

        for project_name in sorted(
            {action.project for action in plan.actions if action.project is not None}
        ):
            project_root = self.context.core.project_config_dir(project_name)
            records.append(
                self._build_revision_record(
                    root=project_root,
                    workspace=None,
                    project=project_name,
                    revision_id=revision_id,
                )
            )

        return records

    def _build_revision_record(
        self,
        *,
        root: Path,
        workspace: str | None,
        project: str | None,
        revision_id: str,
    ) -> RevisionRecord:
        revisions_root = root / SYNC_REVISIONS_DIRNAME
        return RevisionRecord(
            root=root,
            workspace=workspace,
            project=project,
            revision_id=revision_id,
            manifest_path=revisions_root / f"{revision_id}.json",
            active_path=revisions_root / "active.json",
            pending_path=revisions_root / "pending.json",
            artifacts_root=revisions_root / revision_id,
        )

    def _load_previous_revisions(
        self, revision_records: list[RevisionRecord]
    ) -> list[StoredRevision]:
        stored: list[StoredRevision] = []
        for record in revision_records:
            if not record.active_path.exists():
                continue
            try:
                active_payload = json.loads(
                    record.active_path.read_text(encoding="utf-8")
                )
            except Exception:
                continue
            manifest_path_text = active_payload.get("manifest_path")
            if not isinstance(manifest_path_text, str):
                continue
            manifest_path = Path(manifest_path_text)
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            targets = manifest.get("targets")
            if not isinstance(targets, list):
                continue
            state = manifest.get("state")
            if state is not None and not isinstance(state, dict):
                state = None
            revision_id = manifest.get("revision_id")
            if not isinstance(revision_id, str):
                continue
            stored.append(
                StoredRevision(
                    revision_id=revision_id,
                    manifest_path=manifest_path,
                    state=state,
                    targets=targets,
                )
            )
        return stored

    def restore_active_revision(
        self, workspace: str | None = None, project: str | None = None
    ) -> RestoreResult:
        if workspace is not None and project is not None:
            raise ValueError("Choose only one scope: workspace or project.")

        if workspace is not None:
            root = self.context.core.workspace_config_dir(workspace)
        elif project is not None:
            root = self.context.core.project_config_dir(project)
        else:
            root = self.context.core.root

        revision_record = self._build_revision_record(
            root=root, workspace=workspace, project=project, revision_id="restore"
        )
        self._repair_pending_revisions([revision_record])
        records = self._load_previous_revisions([revision_record])
        if not records:
            if workspace is not None:
                label = f"workspace {workspace}"
            elif project is not None:
                label = f"project {project}"
            else:
                label = "global root"
            raise FileNotFoundError(f"No active revision found for {label}.")

        record = records[0]
        self._preflight_stored_revision_artifacts(record)
        snapshots: dict[Path, PathSnapshot] = {}
        for target in record.targets:
            if isinstance(target, dict) and isinstance(target.get("path"), str):
                self._capture_path_and_symlink_target(snapshots, Path(target["path"]))
        if record.state is not None and isinstance(record.state.get("path"), str):
            state_path = Path(record.state["path"])
            self._capture_path_and_symlink_target(snapshots, state_path)

        restored = 0
        try:
            if record.state is not None and self._restore_manifest_file(record.state):
                restored += 1
            for target in record.targets:
                if self._restore_manifest_file(target):
                    restored += 1
        except Exception:
            self._rollback(snapshots, [])
            raise

        return RestoreResult(revision_id=record.revision_id, restored=restored)

    def _repair_pending_revisions(self, revision_records: list[RevisionRecord]) -> None:
        for record in revision_records:
            if not record.pending_path.exists():
                continue
            records = self._load_previous_revisions([record])
            if records:
                stored = records[0]
                self._preflight_stored_revision_artifacts(stored)
                if stored.state is not None:
                    self._restore_manifest_file(stored.state)
                for target in stored.targets:
                    self._restore_manifest_file(target)
            self._clear_pending_revisions([record])
            sync_staging_root = record.root / SYNC_STAGING_DIRNAME
            if sync_staging_root.exists():
                self._remove_tree(sync_staging_root)

    def _preflight_stored_revision_artifacts(self, record: StoredRevision) -> None:
        if record.state is not None:
            self._require_manifest_artifacts(record.state)
        for target in record.targets:
            self._require_manifest_artifacts(target)

    def _require_manifest_artifacts(self, target: dict[str, Any]) -> None:
        path_text = target.get("path")
        if not isinstance(path_text, str):
            return
        if target.get("exists") is not True:
            return

        artifact_path_text = target.get("artifact_path")
        if not isinstance(artifact_path_text, str):
            raise FileNotFoundError(
                f"Missing revision artifact for {path_text}: artifact_path"
            )
        artifact_path = Path(artifact_path_text)
        if not artifact_path.exists():
            raise FileNotFoundError(
                f"Missing revision artifact for {path_text}: {artifact_path}"
            )

        target_artifact_path_text = target.get("target_artifact_path")
        if not isinstance(target_artifact_path_text, str):
            return
        target_artifact_path = Path(target_artifact_path_text)
        if not target_artifact_path.exists():
            raise FileNotFoundError(
                "Missing symlink target revision artifact for "
                f"{path_text}: {target_artifact_path}"
            )

    def _mark_pending_revisions(self, revision_records: list[RevisionRecord]) -> None:
        for record in revision_records:
            write_json(
                record.pending_path,
                {
                    "revision_id": record.revision_id,
                    "started_at": datetime.now().isoformat(timespec="seconds"),
                },
            )

    def _clear_pending_revisions(self, revision_records: list[RevisionRecord]) -> None:
        for record in revision_records:
            if record.pending_path.exists() or record.pending_path.is_symlink():
                record.pending_path.unlink()

    def _stage_actions(
        self,
        *,
        plan: SyncPlan,
        revision_records: list[RevisionRecord],
        staging_id: str,
        staging_dirs: set[Path],
    ) -> tuple[list[StagedAction], str | None]:
        staged_actions: list[StagedAction] = []
        for index, action in enumerate(plan.actions):
            staged_path: Path | None = None
            if action.kind in {
                ActionKind.WRITE_JSON,
                ActionKind.WRITE_TEXT,
                ActionKind.WRITE_RULE,
            }:
                staged_path, failure = self._stage_write_action(
                    action=action,
                    revision_records=revision_records,
                    staging_id=staging_id,
                    staging_dirs=staging_dirs,
                    index=index,
                )
                if failure is not None:
                    return [], failure
            staged_actions.append(StagedAction(action=action, staged_path=staged_path))
        return staged_actions, None

    def _stage_write_action(
        self,
        *,
        action: Action,
        revision_records: list[RevisionRecord],
        staging_id: str,
        staging_dirs: set[Path],
        index: int,
    ) -> tuple[Path | None, str | None]:
        if action.status in (ActionStatus.NOOP, ActionStatus.CONFLICT):
            return None, None

        staging_root = self._staging_root_for_action(
            action=action,
            revision_records=revision_records,
            staging_id=staging_id,
        )
        staging_root.mkdir(parents=True, exist_ok=True)
        staging_dirs.add(staging_root)
        suffix = action.path.suffix or ".tmp"
        staged_path = staging_root / f"{index}{suffix}"

        if action.kind in {ActionKind.WRITE_TEXT, ActionKind.WRITE_RULE}:
            if not isinstance(action.payload, str):
                if action.kind == ActionKind.WRITE_RULE:
                    return None, f"Missing rule payload for write action: {action.path}"
                return None, f"Missing text payload for write action: {action.path}"
            try:
                _write_text_utf8(staged_path, action.payload)
            except Exception as exc:
                return None, f"{action.kind.value} failed for {action.path}: {exc}"
            return staged_path, None

        try:
            write_json(staged_path, action.payload)
        except Exception as exc:
            return None, f"{action.kind.value} failed for {action.path}: {exc}"
        return staged_path, None

    def _staging_root_for_action(
        self,
        *,
        action: Action,
        revision_records: list[RevisionRecord],
        staging_id: str,
    ) -> Path:
        for record in revision_records:
            if (
                record.workspace == action.workspace
                and record.project == action.project
            ):
                return record.root / SYNC_STAGING_DIRNAME / record.revision_id

        if action.project is not None:
            return (
                self.context.core.project_config_dir(action.project)
                / SYNC_STAGING_DIRNAME
                / staging_id
            )
        if action.workspace is not None:
            return (
                self.context.core.workspace_config_dir(action.workspace)
                / SYNC_STAGING_DIRNAME
                / staging_id
            )
        return self.context.core.root / SYNC_STAGING_DIRNAME / staging_id

    def _apply_staged_action(
        self, staged_action: StagedAction
    ) -> tuple[bool, str | None]:
        action = staged_action.action
        if action.kind in {
            ActionKind.WRITE_JSON,
            ActionKind.WRITE_TEXT,
            ActionKind.WRITE_RULE,
        }:
            if action.status in (ActionStatus.NOOP, ActionStatus.CONFLICT):
                return False, None
            if staged_action.staged_path is None:
                return False, f"Missing staged payload for write action: {action.path}"
            self._replace_staged_path(staged_action.staged_path, action.path)
            return True, None

        handler = self.handlers.get(action.kind)
        if handler is None:
            return False, f"Unknown action kind: {action.kind.value}"
        return handler.handle(action, self.context)

    def _cleanup_staging_dirs(self, staging_dirs: set[Path]) -> None:
        for staging_root in sorted(
            staging_dirs, key=lambda path: len(path.parts), reverse=True
        ):
            if staging_root.exists():
                self._remove_tree(staging_root)

            sync_staging_root = staging_root.parent
            if (
                sync_staging_root.name == SYNC_STAGING_DIRNAME
                and sync_staging_root.exists()
            ):
                try:
                    sync_staging_root.rmdir()
                except OSError:
                    pass

    def _remove_tree(self, root: Path) -> None:
        _remove_tree(root)

    def _remove_existing_path(self, path: Path) -> None:
        if path.is_symlink() or path.is_file():
            path.unlink()
            return
        if path.is_dir():
            self._remove_tree(path)

    def _capture_snapshots(
        self,
        *,
        plan: SyncPlan,
        persist_state: bool,
        revision_records: list[RevisionRecord],
    ) -> dict[Path, PathSnapshot]:
        paths: dict[Path, PathSnapshot] = {}
        for action in plan.actions:
            self._capture_path_and_symlink_target(paths, action.path)

        if persist_state:
            for record in revision_records:
                self._capture_path_and_symlink_target(
                    paths, record.root / SYNC_STATE_FILENAME
                )
                self._capture_path_and_symlink_target(paths, record.active_path)
                self._capture_path_and_symlink_target(paths, record.manifest_path)
                self._capture_path_and_symlink_target(paths, record.pending_path)
        return paths

    def _capture_path_and_symlink_target(
        self, snapshots: dict[Path, PathSnapshot], path: Path
    ) -> None:
        snapshot = self._snapshot_path(path)
        snapshots[path] = snapshot
        if snapshot.is_symlink and snapshot.symlink_target is not None:
            target_path = _symlink_target_path(path, snapshot.symlink_target)
            snapshots.setdefault(target_path, self._snapshot_path(target_path))

    def _snapshot_path(self, path: Path) -> PathSnapshot:
        if path.is_symlink():
            return PathSnapshot(
                path=path,
                existed=True,
                is_symlink=True,
                symlink_target=os.readlink(path),
            )
        if path.exists() and path.is_file():
            return PathSnapshot(
                path=path,
                existed=True,
                is_symlink=False,
                content=path.read_bytes(),
            )
        return PathSnapshot(path=path, existed=False, is_symlink=False)

    def _rollback(
        self,
        snapshots: dict[Path, PathSnapshot],
        previous_revisions: list[StoredRevision],
    ) -> None:
        for path, snapshot in sorted(
            snapshots.items(),
            key=lambda item: len(item[0].parts),
            reverse=True,
        ):
            self._remove_existing_path(path)

            if snapshot.existed:
                path.parent.mkdir(parents=True, exist_ok=True)
                if snapshot.is_symlink:
                    if snapshot.symlink_target is not None:
                        path.symlink_to(snapshot.symlink_target)
                elif snapshot.content is not None:
                    path.write_bytes(snapshot.content)

        for stored_revision in previous_revisions:
            if stored_revision.state is not None:
                self._restore_manifest_file(stored_revision.state)
            for target in stored_revision.targets:
                self._restore_manifest_file(target)

    def _persist_state(
        self,
        plan: SyncPlan,
        revision_records: list[RevisionRecord],
        staging_id: str,
        staging_dirs: set[Path],
    ) -> None:
        global_links: dict[str, list[str]] = {}
        global_paths: dict[str, list[str]] = {}
        global_mcp: dict[str, list[str]] = {}
        global_touched_scopes: set[str] = set()
        global_mcp_touched: set[str] = set()
        global_values: dict[str, dict[str, str]] = {}
        global_values_touched: set[str] = set()
        workspace_links: dict[str, dict[str, list[str]]] = {}
        workspace_paths: dict[str, dict[str, list[str]]] = {}
        workspace_mcp: dict[str, dict[str, list[str]]] = {}
        workspace_mcp_touched: dict[str, set[str]] = {}
        workspace_values: dict[str, dict[str, dict[str, str]]] = {}
        workspace_values_touched: dict[str, set[str]] = {}
        workspace_touched_scopes: dict[str, set[str]] = {}
        project_links: dict[str, dict[str, list[str]]] = {}
        project_paths: dict[str, dict[str, list[str]]] = {}
        project_mcp: dict[str, dict[str, list[str]]] = {}
        project_mcp_touched: dict[str, set[str]] = {}
        project_values: dict[str, dict[str, dict[str, str]]] = {}
        project_values_touched: dict[str, set[str]] = {}
        project_touched_scopes: dict[str, set[str]] = {}

        for action in plan.actions:
            if action.scope is None:
                continue

            ownership_tracked = (
                action.managed_entries is not None or action.managed_values is not None
            )
            owns_entries = bool(
                action.managed_entries and any(action.managed_entries.values())
            )
            if action.workspace is not None:
                ws_name = action.workspace
                if ownership_tracked:
                    workspace_touched_scopes.setdefault(ws_name, set()).add(
                        action.scope
                    )
                    if (
                        action.kind in (ActionKind.WRITE_TEXT, ActionKind.WRITE_JSON)
                        and action.status != ActionStatus.CONFLICT
                        and action.path.exists()
                        and owns_entries
                    ):
                        workspace_paths.setdefault(ws_name, {}).setdefault(
                            action.scope, []
                        ).append(str(action.path))
                if action.managed_entries is not None:
                    for entry_scope, names in action.managed_entries.items():
                        workspace_mcp_touched.setdefault(ws_name, set()).add(
                            entry_scope
                        )
                        if names:
                            workspace_mcp.setdefault(ws_name, {})[entry_scope] = sorted(
                                set(names)
                            )
                if action.managed_values is not None:
                    for value_scope, values in action.managed_values.items():
                        workspace_values_touched.setdefault(ws_name, set()).add(
                            value_scope
                        )
                        if values:
                            workspace_values.setdefault(ws_name, {})[value_scope] = (
                                dict(values)
                            )
            elif action.project is not None:
                project_name = action.project
                if ownership_tracked:
                    project_touched_scopes.setdefault(project_name, set()).add(
                        action.scope
                    )
                    if (
                        action.kind in (ActionKind.WRITE_TEXT, ActionKind.WRITE_JSON)
                        and action.status != ActionStatus.CONFLICT
                        and action.path.exists()
                        and owns_entries
                    ):
                        project_paths.setdefault(project_name, {}).setdefault(
                            action.scope, []
                        ).append(str(action.path))
                if action.managed_entries is not None:
                    for entry_scope, names in action.managed_entries.items():
                        project_mcp_touched.setdefault(project_name, set()).add(
                            entry_scope
                        )
                        if names:
                            project_mcp.setdefault(project_name, {})[entry_scope] = (
                                sorted(set(names))
                            )
                if action.managed_values is not None:
                    for value_scope, values in action.managed_values.items():
                        project_values_touched.setdefault(project_name, set()).add(
                            value_scope
                        )
                        if values:
                            project_values.setdefault(project_name, {})[value_scope] = (
                                dict(values)
                            )
            else:
                if action.managed_entries is not None:
                    # User-shared config: track the named entries we own (MCP
                    # servers, agent-registry names, …) by scope — never the shared
                    # config file itself, so cleanup prunes only what we wrote.
                    for entry_scope, names in action.managed_entries.items():
                        global_mcp_touched.add(entry_scope)
                        if names:
                            global_mcp[entry_scope] = sorted(set(names))
                if action.managed_values is not None:
                    for value_scope, values in action.managed_values.items():
                        global_values_touched.add(value_scope)
                        if values:
                            global_values[value_scope] = dict(values)

            if ownership_tracked:
                continue

            if action.workspace is not None:
                ws_name = action.workspace
                workspace_touched_scopes.setdefault(ws_name, set()).add(action.scope)
                if action.kind == ActionKind.SYMLINK and action.path.is_symlink():
                    workspace_links.setdefault(ws_name, {}).setdefault(
                        action.scope, []
                    ).append(str(action.path))
                if (
                    action.kind in (ActionKind.WRITE_TEXT, ActionKind.WRITE_JSON)
                    and action.status != ActionStatus.CONFLICT
                    and action.path.exists()
                ):
                    workspace_paths.setdefault(ws_name, {}).setdefault(
                        action.scope, []
                    ).append(str(action.path))
            elif action.project is not None:
                project_name = action.project
                project_touched_scopes.setdefault(project_name, set()).add(action.scope)
                if action.kind == ActionKind.SYMLINK and action.path.is_symlink():
                    project_links.setdefault(project_name, {}).setdefault(
                        action.scope, []
                    ).append(str(action.path))
                if (
                    action.kind in (ActionKind.WRITE_TEXT, ActionKind.WRITE_JSON)
                    and action.status != ActionStatus.CONFLICT
                    and action.path.exists()
                ):
                    project_paths.setdefault(project_name, {}).setdefault(
                        action.scope, []
                    ).append(str(action.path))
            else:
                global_touched_scopes.add(action.scope)
                if action.kind == ActionKind.SYMLINK and action.path.is_symlink():
                    global_links.setdefault(action.scope, []).append(str(action.path))
                if (
                    action.kind in (ActionKind.WRITE_TEXT, ActionKind.WRITE_JSON)
                    and action.status != ActionStatus.CONFLICT
                    and action.path.exists()
                ):
                    global_paths.setdefault(action.scope, []).append(str(action.path))

        updated_at = datetime.now().isoformat(timespec="seconds")

        # Persist global state
        core = self.context.core
        if global_touched_scopes or global_mcp_touched or global_values_touched:
            existing_global_state = core.load_state()
            global_state = {
                "updated_at": updated_at,
                "managed_links": self._merge_managed_links(
                    existing=existing_global_state.managed_links,
                    touched_scopes=global_touched_scopes,
                    current_links=global_links,
                ),
                "managed_paths": self._merge_managed_links(
                    existing=existing_global_state.managed_paths,
                    touched_scopes=global_touched_scopes,
                    current_links=global_paths,
                ),
                "managed_mcp": self._merge_managed_links(
                    existing=existing_global_state.managed_mcp,
                    touched_scopes=global_mcp_touched,
                    current_links=global_mcp,
                ),
                "managed_values": self._merge_managed_values(
                    existing=existing_global_state.managed_values,
                    touched_scopes=global_values_touched,
                    current_values=global_values,
                ),
                "skipped": plan.skipped,
            }
            self._place_json_via_staging(
                target=core.root / SYNC_STATE_FILENAME,
                payload=global_state,
                staging_root=(
                    core.root / SYNC_STAGING_DIRNAME / staging_id / "metadata"
                ),
                staging_dirs=staging_dirs,
                stage_name="global-state.json",
            )

        # Persist workspace state
        for ws_name in workspace_touched_scopes:
            ws_repo = WorkspaceConfigRepository(root=core.workspace_config_dir(ws_name))
            existing_workspace_state = ws_repo.load_state()
            workspace_scopes = workspace_touched_scopes[ws_name]
            ws_state = {
                "updated_at": updated_at,
                "managed_links": self._merge_managed_links(
                    existing=existing_workspace_state.managed_links,
                    touched_scopes=workspace_scopes,
                    current_links=workspace_links.get(ws_name, {}),
                ),
                "managed_paths": self._merge_managed_links(
                    existing=existing_workspace_state.managed_paths,
                    touched_scopes=workspace_scopes,
                    current_links=workspace_paths.get(ws_name, {}),
                ),
                "managed_mcp": self._merge_managed_links(
                    existing=existing_workspace_state.managed_mcp,
                    touched_scopes=workspace_mcp_touched.get(ws_name, set()),
                    current_links=workspace_mcp.get(ws_name, {}),
                ),
                "managed_values": self._merge_managed_values(
                    existing=existing_workspace_state.managed_values,
                    touched_scopes=workspace_values_touched.get(ws_name, set()),
                    current_values=workspace_values.get(ws_name, {}),
                ),
            }
            self._place_json_via_staging(
                target=ws_repo.state_json,
                payload=ws_state,
                staging_root=ws_repo.root
                / SYNC_STAGING_DIRNAME
                / staging_id
                / "metadata",
                staging_dirs=staging_dirs,
                stage_name="workspace-state.json",
            )

        # Persist project state
        for project_name in project_touched_scopes:
            project_repo = ProjectConfigRepository(
                root=core.project_config_dir(project_name)
            )
            existing_project_state = project_repo.load_state()
            project_scopes = project_touched_scopes[project_name]
            project_state = {
                "updated_at": updated_at,
                "managed_links": self._merge_managed_links(
                    existing=existing_project_state.managed_links,
                    touched_scopes=project_scopes,
                    current_links=project_links.get(project_name, {}),
                ),
                "managed_paths": self._merge_managed_links(
                    existing=existing_project_state.managed_paths,
                    touched_scopes=project_scopes,
                    current_links=project_paths.get(project_name, {}),
                ),
                "managed_mcp": self._merge_managed_links(
                    existing=existing_project_state.managed_mcp,
                    touched_scopes=project_mcp_touched.get(project_name, set()),
                    current_links=project_mcp.get(project_name, {}),
                ),
                "managed_values": self._merge_managed_values(
                    existing=existing_project_state.managed_values,
                    touched_scopes=project_values_touched.get(project_name, set()),
                    current_values=project_values.get(project_name, {}),
                ),
            }
            self._place_json_via_staging(
                target=project_repo.state_json,
                payload=project_state,
                staging_root=project_repo.root
                / SYNC_STAGING_DIRNAME
                / staging_id
                / "metadata",
                staging_dirs=staging_dirs,
                stage_name="project-state.json",
            )

        self._persist_revision_manifests(
            plan=plan,
            revision_records=revision_records,
            staging_dirs=staging_dirs,
        )

    def _persist_revision_manifests(
        self,
        *,
        plan: SyncPlan,
        revision_records: list[RevisionRecord],
        staging_dirs: set[Path],
    ) -> None:
        actions_by_scope: dict[tuple[str | None, str | None], list[Action]] = {}
        for action in plan.actions:
            actions_by_scope.setdefault((action.workspace, action.project), []).append(
                action
            )

        for record in revision_records:
            actions = sorted(
                actions_by_scope.get((record.workspace, record.project), []),
                key=lambda action: (
                    str(action.path),
                    action.kind.value,
                    action.scope or "",
                    action.app or "",
                ),
            )
            manifest = {
                "revision_id": record.revision_id,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "root": str(record.root),
                "workspace": record.workspace,
                "project": record.project,
                "state": self._serialize_manifest_file(
                    path=record.root / SYNC_STATE_FILENAME,
                    artifact_path=record.artifacts_root / "state.bin",
                ),
                "sources": self._serialize_manifest_sources(record.root),
                "targets": [
                    self._serialize_manifest_target(record, action, index)
                    for index, action in enumerate(actions)
                    if not self._skip_revision_target(action)
                ],
            }
            self._place_json_via_staging(
                target=record.manifest_path,
                payload=manifest,
                staging_root=record.root
                / SYNC_STAGING_DIRNAME
                / record.revision_id
                / "metadata",
                staging_dirs=staging_dirs,
                stage_name=record.manifest_path.name,
            )
            self._place_json_via_staging(
                target=record.active_path,
                payload={
                    "revision_id": record.revision_id,
                    "manifest_path": str(record.manifest_path),
                },
                staging_root=record.root
                / SYNC_STAGING_DIRNAME
                / record.revision_id
                / "metadata",
                staging_dirs=staging_dirs,
                stage_name=record.active_path.name,
            )

    def _place_json_via_staging(
        self,
        *,
        target: Path,
        payload: Any,
        staging_root: Path,
        staging_dirs: set[Path],
        stage_name: str,
    ) -> None:
        staging_root.mkdir(parents=True, exist_ok=True)
        staging_dirs.add(staging_root.parent)
        staged_path = staging_root / stage_name
        write_json(staged_path, payload)
        self._replace_staged_path(staged_path, target)

    def _replace_staged_path(self, staged_path: Path, target: Path) -> None:
        replacement_target = target
        if target.is_symlink():
            replacement_target = _symlink_target_path(target, os.readlink(target))
        replacement_target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staged_path, replacement_target)

    def _serialize_manifest_file(
        self, *, path: Path, artifact_path: Path
    ) -> dict[str, Any]:
        checksum: str | None = None
        serialized_artifact_path: str | None = None
        target_checksum: str | None = None
        target_artifact_path: str | None = None
        exists = path.exists() or path.is_symlink()
        if path.is_symlink():
            link_target = os.readlink(path)
            checksum = hashlib.sha256(link_target.encode("utf-8")).hexdigest()
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(link_target, encoding="utf-8")
            serialized_artifact_path = str(artifact_path.with_suffix(".symlink"))
            artifact_path.unlink()
            Path(serialized_artifact_path).write_text(link_target, encoding="utf-8")
            resolved_target = _symlink_target_path(path, link_target)
            if resolved_target.exists() and resolved_target.is_file():
                target_checksum = hashlib.sha256(
                    resolved_target.read_bytes()
                ).hexdigest()
                artifact_path.write_bytes(resolved_target.read_bytes())
                target_artifact_path = str(artifact_path)
        elif path.exists() and path.is_file():
            checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_bytes(path.read_bytes())
            serialized_artifact_path = str(artifact_path)

        return {
            "path": str(path),
            "exists": exists,
            "checksum": checksum,
            "artifact_path": serialized_artifact_path,
            "target_checksum": target_checksum,
            "target_artifact_path": target_artifact_path,
        }

    def _serialize_manifest_target(
        self, record: RevisionRecord, action: Action, index: int
    ) -> dict[str, Any]:
        payload = self._serialize_manifest_file(
            path=action.path,
            artifact_path=record.artifacts_root / f"{index}.bin",
        )
        return {
            "path": str(action.path),
            "kind": action.kind.value,
            "app": action.app,
            "scope": action.scope,
            "project": action.project,
            "exists": payload["exists"],
            "checksum": payload["checksum"],
            "artifact_path": payload["artifact_path"],
            "target_checksum": payload["target_checksum"],
            "target_artifact_path": payload["target_artifact_path"],
        }

    @staticmethod
    def _skip_revision_target(action: Action) -> bool:
        """Never persist bytes from ownership-tracked native configs."""
        return action.managed_entries is not None or action.managed_values is not None

    def _serialize_manifest_sources(self, root: Path) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        if not root.exists():
            return entries

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if any(part.startswith(".") for part in path.relative_to(root).parts):
                continue
            entries.append(
                {
                    "path": str(path),
                    "checksum": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
        return entries

    def _restore_manifest_file(self, target: dict[str, Any]) -> bool:
        path_text = target.get("path")
        if not isinstance(path_text, str):
            return False
        path = Path(path_text)
        existed_before = path.exists() or path.is_symlink()

        if target.get("exists") is not True:
            self._remove_existing_path(path)
            return existed_before

        artifact_path_text = target.get("artifact_path")
        if not isinstance(artifact_path_text, str):
            return False

        artifact_path = Path(artifact_path_text)
        if not artifact_path.exists():
            return False

        self._remove_existing_path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if artifact_path.suffix == ".symlink":
            link_target = artifact_path.read_text(encoding="utf-8")
            path.symlink_to(link_target)
            self._restore_symlink_target_file(path, link_target, target)
            return True
        path.write_bytes(artifact_path.read_bytes())
        return True

    def _restore_symlink_target_file(
        self, path: Path, link_target: str, target: dict[str, Any]
    ) -> None:
        artifact_path_text = target.get("target_artifact_path")
        if not isinstance(artifact_path_text, str):
            return
        artifact_path = Path(artifact_path_text)
        if not artifact_path.exists():
            return
        resolved_target = _symlink_target_path(path, link_target)
        resolved_target.parent.mkdir(parents=True, exist_ok=True)
        resolved_target.write_bytes(artifact_path.read_bytes())

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

    @staticmethod
    def _merge_managed_values(
        *,
        existing: Any,
        touched_scopes: set[str],
        current_values: dict[str, dict[str, str]],
    ) -> dict[str, dict[str, str]]:
        merged: dict[str, dict[str, str]] = {}

        if isinstance(existing, dict):
            for scope, values in existing.items():
                if scope in touched_scopes or not isinstance(scope, str):
                    continue
                if not isinstance(values, dict):
                    continue
                kept_values = {
                    key: value
                    for key, value in values.items()
                    if isinstance(key, str) and isinstance(value, str)
                }
                if kept_values:
                    merged[scope] = kept_values

        for scope, values in current_values.items():
            current = {
                key: value
                for key, value in values.items()
                if isinstance(key, str) and isinstance(value, str)
            }
            if current:
                merged[scope] = current

        return merged
