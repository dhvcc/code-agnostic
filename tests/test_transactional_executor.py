import hashlib
import json
from pathlib import Path

from code_agnostic.core.repository import CoreRepository
from code_agnostic.executor import SyncExecutor
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan


def test_execute_rolls_back_partial_writes_and_skips_state_persist(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    existing = tmp_path / "existing.txt"
    existing.write_text("before\n", encoding="utf-8")
    created = tmp_path / "created.txt"

    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=existing,
                status=ActionStatus.UPDATE,
                detail="update existing file",
                payload="after\n",
                scope="app:test:text",
            ),
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=created,
                status=ActionStatus.CREATE,
                detail="create new file",
                payload="created\n",
                scope="app:test:text",
            ),
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=tmp_path / "broken.txt",
                status=ActionStatus.CREATE,
                detail="break apply",
                payload=None,
                scope="app:test:text",
            ),
        ],
        errors=[],
        skipped=[],
    )

    applied, failed, failures = SyncExecutor(core=CoreRepository(core_root)).execute(
        plan
    )

    assert applied == 0
    assert failed == 1
    assert failures == [
        f"Missing text payload for write action: {tmp_path / 'broken.txt'}"
    ]
    assert existing.read_text(encoding="utf-8") == "before\n"
    assert not created.exists()
    assert not (core_root / ".sync-state.json").exists()


def test_execute_restores_removed_file_when_later_action_fails(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    existing = tmp_path / "managed.txt"
    existing.write_text("keep me\n", encoding="utf-8")

    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.REMOVE_FILE,
                path=existing,
                status=ActionStatus.REMOVE,
                detail="remove stale file",
                scope="app:test:text",
            ),
            Action(
                kind=ActionKind.WRITE_JSON,
                path=tmp_path / "broken.json",
                status=ActionStatus.CREATE,
                detail="break apply",
                payload={"broken": {1, 2, 3}},
                scope="app:test:json",
            ),
        ],
        errors=[],
        skipped=[],
    )

    applied, failed, failures = SyncExecutor(core=CoreRepository(core_root)).execute(
        plan
    )

    assert applied == 0
    assert failed == 1
    assert len(failures) == 1
    assert "write_json failed" in failures[0]
    assert existing.read_text(encoding="utf-8") == "keep me\n"
    assert not (core_root / ".sync-state.json").exists()


def test_execute_persists_global_revision_manifest_on_success(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    target = tmp_path / "generated.txt"
    payload = "hello\n"
    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=target,
                status=ActionStatus.CREATE,
                detail="create file",
                payload=payload,
                scope="app:test:text",
                app="opencode",
            )
        ],
        errors=[],
        skipped=[],
    )

    applied, failed, failures = SyncExecutor(core=CoreRepository(core_root)).execute(
        plan
    )

    assert applied == 1
    assert failed == 0
    assert failures == []

    active_revision_path = core_root / ".sync-revisions" / "active.json"
    assert active_revision_path.exists()
    active_revision = json.loads(active_revision_path.read_text(encoding="utf-8"))
    manifest_path = (
        core_root / ".sync-revisions" / f"{active_revision['revision_id']}.json"
    )
    assert active_revision == {
        "revision_id": active_revision["revision_id"],
        "manifest_path": str(manifest_path),
    }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["revision_id"] == active_revision["revision_id"]
    assert manifest["root"] == str(core_root)
    assert manifest["workspace"] is None
    assert manifest["targets"] == [
        {
            "path": str(target),
            "kind": "write_text",
            "app": "opencode",
            "scope": "app:test:text",
            "exists": True,
            "checksum": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        }
    ]


def test_execute_persists_workspace_revision_manifest_on_success(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    core = CoreRepository(core_root)
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    core.add_workspace("myws", workspace_root)

    target = workspace_root / "AGENTS.md"
    payload = "workspace\n"
    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=target,
                status=ActionStatus.CREATE,
                detail="create workspace file",
                payload=payload,
                scope="rules",
                app="workspace",
                workspace="myws",
            )
        ],
        errors=[],
        skipped=[],
    )

    applied, failed, failures = SyncExecutor(core=core).execute(plan)

    assert applied == 1
    assert failed == 0
    assert failures == []

    revisions_root = core_root / "workspaces" / "myws" / ".sync-revisions"
    active_revision_path = revisions_root / "active.json"
    assert active_revision_path.exists()
    active_revision = json.loads(active_revision_path.read_text(encoding="utf-8"))
    manifest_path = revisions_root / f"{active_revision['revision_id']}.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["revision_id"] == active_revision["revision_id"]
    assert manifest["root"] == str(core_root / "workspaces" / "myws")
    assert manifest["workspace"] == "myws"
    assert manifest["targets"] == [
        {
            "path": str(target),
            "kind": "write_text",
            "app": "workspace",
            "scope": "rules",
            "exists": True,
            "checksum": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        }
    ]
