from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from typing import Protocol

from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan
from code_agnostic.utils import write_json


@dataclass
class ExecutionContext:
    core: ISourceRepository


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
    revision_id: str
    manifest_path: Path
    active_path: Path
    artifacts_root: Path


@dataclass(frozen=True)
class StoredRevision:
    manifest_path: Path
    targets: list[dict[str, Any]]


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
            ActionKind.REMOVE_FILE: RemoveFileHandler(),
        }

    def execute(
        self, plan: SyncPlan, persist_state: bool = True
    ) -> tuple[int, int, list[str]]:
        applied = 0
        failed = 0
        failures: list[str] = []
        revision_records = self._prepare_revision_records(plan, persist_state)
        previous_revisions = self._load_previous_revisions(revision_records)
        snapshots = self._capture_snapshots(
            plan=plan,
            persist_state=persist_state,
            revision_records=revision_records,
        )

        for action in plan.actions:
            try:
                handler = self.handlers.get(action.kind)
                if handler is None:
                    failure = f"Unknown action kind: {action.kind.value}"
                    self._rollback(snapshots, previous_revisions)
                    return 0, 1, [failure]

                changed, failure = handler.handle(action, self.context)
                if failure is not None:
                    self._rollback(snapshots, previous_revisions)
                    return 0, 1, [failure]
                if changed:
                    applied += 1
            except Exception as exc:
                self._rollback(snapshots, previous_revisions)
                return 0, 1, [f"{action.kind.value} failed for {action.path}: {exc}"]

        if persist_state:
            try:
                self._persist_state(plan=plan, revision_records=revision_records)
            except Exception as exc:
                self._rollback(snapshots, previous_revisions)
                return 0, 1, [f"persist_state failed: {exc}"]
        return applied, failed, failures

    def _prepare_revision_records(
        self, plan: SyncPlan, persist_state: bool
    ) -> list[RevisionRecord]:
        if not persist_state:
            return []

        records: list[RevisionRecord] = []
        revision_id = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        if any(action.workspace is None for action in plan.actions):
            records.append(
                self._build_revision_record(
                    root=self.context.core.root,
                    workspace=None,
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
                    revision_id=revision_id,
                )
            )

        return records

    def _build_revision_record(
        self, *, root: Path, workspace: str | None, revision_id: str
    ) -> RevisionRecord:
        revisions_root = root / ".sync-revisions"
        return RevisionRecord(
            root=root,
            workspace=workspace,
            revision_id=revision_id,
            manifest_path=revisions_root / f"{revision_id}.json",
            active_path=revisions_root / "active.json",
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
            stored.append(StoredRevision(manifest_path=manifest_path, targets=targets))
        return stored

    def _capture_snapshots(
        self,
        *,
        plan: SyncPlan,
        persist_state: bool,
        revision_records: list[RevisionRecord],
    ) -> dict[Path, PathSnapshot]:
        paths: dict[Path, PathSnapshot] = {}
        for action in plan.actions:
            paths[action.path] = self._snapshot_path(action.path)

        if persist_state:
            core = self.context.core
            core_state_path = core.root / ".sync-state.json"
            paths[core_state_path] = self._snapshot_path(core_state_path)
            for workspace_name in {
                action.workspace
                for action in plan.actions
                if action.workspace is not None
            }:
                workspace_state_path = WorkspaceConfigRepository(
                    root=core.workspace_config_dir(workspace_name)
                ).state_json
                paths[workspace_state_path] = self._snapshot_path(workspace_state_path)
            for record in revision_records:
                paths[record.active_path] = self._snapshot_path(record.active_path)
                paths[record.manifest_path] = self._snapshot_path(record.manifest_path)
        return paths

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
            if path.is_symlink() or path.is_file():
                path.unlink()

            if snapshot.existed:
                path.parent.mkdir(parents=True, exist_ok=True)
                if snapshot.is_symlink:
                    if snapshot.symlink_target is not None:
                        path.symlink_to(snapshot.symlink_target)
                elif snapshot.content is not None:
                    path.write_bytes(snapshot.content)

        for stored_revision in previous_revisions:
            for target in stored_revision.targets:
                self._restore_manifest_target(target)

    def _persist_state(
        self, plan: SyncPlan, revision_records: list[RevisionRecord]
    ) -> None:
        global_links: dict[str, list[str]] = {}
        global_paths: dict[str, list[str]] = {}
        global_touched_scopes: set[str] = set()
        workspace_links: dict[str, dict[str, list[str]]] = {}
        workspace_paths: dict[str, dict[str, list[str]]] = {}
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
                if (
                    action.kind in (ActionKind.WRITE_TEXT, ActionKind.WRITE_JSON)
                    and action.path.exists()
                ):
                    workspace_paths.setdefault(ws_name, {}).setdefault(
                        action.scope, []
                    ).append(str(action.path))
            else:
                global_touched_scopes.add(action.scope)
                if action.kind == ActionKind.SYMLINK and action.path.is_symlink():
                    global_links.setdefault(action.scope, []).append(str(action.path))
                if (
                    action.kind in (ActionKind.WRITE_TEXT, ActionKind.WRITE_JSON)
                    and action.path.exists()
                ):
                    global_paths.setdefault(action.scope, []).append(str(action.path))

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
            "managed_paths": self._merge_managed_links(
                existing=existing_global_state.get("managed_paths"),
                touched_scopes=global_touched_scopes,
                current_links=global_paths,
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
                "managed_paths": self._merge_managed_links(
                    existing=existing_workspace_state.get("managed_paths"),
                    touched_scopes=workspace_touched_scopes[ws_name],
                    current_links=workspace_paths.get(ws_name, {}),
                ),
            }
            ws_repo.root.mkdir(parents=True, exist_ok=True)
            ws_repo.save_state(ws_state)

        self._persist_revision_manifests(plan=plan, revision_records=revision_records)

    def _persist_revision_manifests(
        self, *, plan: SyncPlan, revision_records: list[RevisionRecord]
    ) -> None:
        actions_by_workspace: dict[str | None, list[Action]] = {}
        for action in plan.actions:
            actions_by_workspace.setdefault(action.workspace, []).append(action)

        for record in revision_records:
            actions = sorted(
                actions_by_workspace.get(record.workspace, []),
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
                "targets": [
                    self._serialize_manifest_target(record, action, index)
                    for index, action in enumerate(actions)
                ],
            }
            write_json(record.manifest_path, manifest)
            write_json(
                record.active_path,
                {
                    "revision_id": record.revision_id,
                    "manifest_path": str(record.manifest_path),
                },
            )

    def _serialize_manifest_target(
        self, record: RevisionRecord, action: Action, index: int
    ) -> dict[str, Any]:
        checksum: str | None = None
        exists = action.path.exists() or action.path.is_symlink()
        artifact_path: str | None = None
        if action.path.is_symlink():
            checksum = hashlib.sha256(
                os.readlink(action.path).encode("utf-8")
            ).hexdigest()
            artifact = record.artifacts_root / f"{index}.symlink"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text(os.readlink(action.path), encoding="utf-8")
            artifact_path = str(artifact)
        elif action.path.exists() and action.path.is_file():
            checksum = hashlib.sha256(action.path.read_bytes()).hexdigest()
            artifact = record.artifacts_root / f"{index}.bin"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(action.path.read_bytes())
            artifact_path = str(artifact)

        return {
            "path": str(action.path),
            "kind": action.kind.value,
            "app": action.app,
            "scope": action.scope,
            "exists": exists,
            "checksum": checksum,
            "artifact_path": artifact_path,
        }

    def _restore_manifest_target(self, target: dict[str, Any]) -> None:
        path_text = target.get("path")
        if not isinstance(path_text, str):
            return
        path = Path(path_text)
        if path.is_symlink() or path.is_file():
            path.unlink()

        if target.get("exists") is not True:
            return

        artifact_path_text = target.get("artifact_path")
        if not isinstance(artifact_path_text, str):
            return

        artifact_path = Path(artifact_path_text)
        if not artifact_path.exists():
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        if artifact_path.suffix == ".symlink":
            path.symlink_to(artifact_path.read_text(encoding="utf-8"))
            return
        path.write_bytes(artifact_path.read_bytes())

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
