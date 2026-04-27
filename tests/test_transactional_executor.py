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
                kind=ActionKind.SYMLINK,
                path=tmp_path / "broken-link",
                status=ActionStatus.CREATE,
                detail="break apply",
                source=None,
                scope="app:test:link",
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
        f"Missing source for symlink action: {tmp_path / 'broken-link'}"
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


def test_execute_restores_symlink_snapshot_after_directory_is_recreated(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    symlink_target = tmp_path / "legacy-skill"
    symlink_target.mkdir()
    legacy_link = tmp_path / "skills" / "backend-coder-standards"
    legacy_link.parent.mkdir()
    legacy_link.symlink_to(symlink_target)

    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.REMOVE_SYMLINK,
                path=legacy_link,
                status=ActionStatus.REMOVE,
                detail="remove legacy symlink",
                scope="app:opencode:skills",
                app="opencode",
            ),
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=legacy_link / "SKILL.md",
                status=ActionStatus.CREATE,
                detail="write compiled skill",
                payload="compiled\n",
                scope="app:opencode:skills",
                app="opencode",
            ),
            Action(
                kind=ActionKind.SYMLINK,
                path=tmp_path / "broken-link",
                status=ActionStatus.CREATE,
                detail="break apply",
                source=None,
                scope="app:test:link",
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
        f"Missing source for symlink action: {tmp_path / 'broken-link'}"
    ]
    assert legacy_link.is_symlink()
    assert legacy_link.resolve() == symlink_target.resolve()


def test_execute_replaces_symlinked_skill_dir_with_compiled_file(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    source_skill_dir = tmp_path / "source-skill"
    source_skill_dir.mkdir()
    source_skill_file = source_skill_dir / "SKILL.md"
    source_skill_file.write_text("legacy\n", encoding="utf-8")

    legacy_link = tmp_path / "skills" / "backend-coder-standards"
    legacy_link.parent.mkdir()
    legacy_link.symlink_to(source_skill_dir)

    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.REMOVE_SYMLINK,
                path=legacy_link,
                status=ActionStatus.REMOVE,
                detail="replace legacy symlink",
                scope="app:codex:skills",
                app="codex",
            ),
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=legacy_link / "SKILL.md",
                status=ActionStatus.UPDATE,
                detail="write compiled skill",
                payload="compiled\n",
                scope="app:codex:skills",
                app="codex",
            ),
        ],
        errors=[],
        skipped=[],
    )

    applied, failed, failures = SyncExecutor(core=CoreRepository(core_root)).execute(
        plan
    )

    assert applied == 2
    assert failed == 0
    assert failures == []
    assert legacy_link.is_dir()
    assert not legacy_link.is_symlink()
    assert (legacy_link / "SKILL.md").read_text(encoding="utf-8") == "compiled\n"
    assert source_skill_file.read_text(encoding="utf-8") == "legacy\n"


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
    assert manifest["state"]["path"] == str(core_root / ".sync-state.json")
    assert Path(manifest["state"]["artifact_path"]).exists()
    source_paths = {entry["path"] for entry in manifest["sources"]}
    assert str(core_root / "config" / "mcp.base.json") in source_paths
    assert str(core_root / "config" / "opencode.base.json") in source_paths
    assert len(manifest["targets"]) == 1
    target_entry = manifest["targets"][0]
    assert target_entry["path"] == str(target)
    assert target_entry["kind"] == "write_text"
    assert target_entry["app"] == "opencode"
    assert target_entry["scope"] == "app:test:text"
    assert target_entry["exists"] is True
    assert (
        target_entry["checksum"] == hashlib.sha256(payload.encode("utf-8")).hexdigest()
    )
    artifact_path = Path(target_entry["artifact_path"])
    assert artifact_path.exists()
    assert artifact_path.read_text(encoding="utf-8") == payload


def test_execute_persists_workspace_revision_manifest_on_success(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    core = CoreRepository(core_root)
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    core.add_workspace("myws", workspace_root)
    ws_source = core_root / "workspaces" / "myws" / "rules"
    ws_source.mkdir(parents=True)
    (ws_source / "shared.md").write_text("workspace rules\n", encoding="utf-8")

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
    assert manifest["state"]["path"] == str(
        core_root / "workspaces" / "myws" / ".sync-state.json"
    )
    assert Path(manifest["state"]["artifact_path"]).exists()
    source_paths = {entry["path"] for entry in manifest["sources"]}
    assert str(ws_source / "shared.md") in source_paths
    assert len(manifest["targets"]) == 1
    target_entry = manifest["targets"][0]
    assert target_entry["path"] == str(target)
    assert target_entry["kind"] == "write_text"
    assert target_entry["app"] == "workspace"
    assert target_entry["scope"] == "rules"
    assert target_entry["exists"] is True
    assert (
        target_entry["checksum"] == hashlib.sha256(payload.encode("utf-8")).hexdigest()
    )
    artifact_path = Path(target_entry["artifact_path"])
    assert artifact_path.exists()
    assert artifact_path.read_text(encoding="utf-8") == payload


def test_execute_restores_last_successful_revision_from_manifest(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    core = CoreRepository(core_root)
    executor = SyncExecutor(core=core)
    primary = tmp_path / "primary.txt"
    sibling = tmp_path / "sibling.txt"

    first_plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=primary,
                status=ActionStatus.CREATE,
                detail="create primary",
                payload="v1\n",
                scope="app:test:text",
                app="opencode",
            ),
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=sibling,
                status=ActionStatus.CREATE,
                detail="create sibling",
                payload="sibling\n",
                scope="app:test:text",
                app="opencode",
            ),
        ],
        errors=[],
        skipped=[],
    )
    applied, failed, failures = executor.execute(first_plan)
    assert applied == 2
    assert failed == 0
    assert failures == []

    sibling.unlink()

    second_plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=primary,
                status=ActionStatus.UPDATE,
                detail="update primary",
                payload="v2\n",
                scope="app:test:text",
                app="opencode",
            ),
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=tmp_path / "broken.txt",
                status=ActionStatus.CREATE,
                detail="break apply",
                payload=None,
                scope="app:test:text",
                app="opencode",
            ),
        ],
        errors=[],
        skipped=[],
    )

    applied, failed, failures = executor.execute(second_plan)

    assert applied == 0
    assert failed == 1
    assert failures == [
        f"Missing text payload for write action: {tmp_path / 'broken.txt'}"
    ]
    assert primary.read_text(encoding="utf-8") == "v1\n"
    assert sibling.read_text(encoding="utf-8") == "sibling\n"


def test_execute_places_written_files_via_staging_replace(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "generated.txt"
    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=target,
                status=ActionStatus.CREATE,
                detail="create file",
                payload="hello\n",
                scope="app:test:text",
                app="opencode",
            )
        ],
        errors=[],
        skipped=[],
    )

    replace_calls: list[tuple[Path, Path]] = []
    original_replace = __import__("os").replace

    def recording_replace(src: str | Path, dst: str | Path) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        replace_calls.append((src_path, dst_path))
        original_replace(src_path, dst_path)

    monkeypatch.setattr("os.replace", recording_replace)

    applied, failed, failures = SyncExecutor(core=CoreRepository(core_root)).execute(
        plan
    )

    assert applied == 1
    assert failed == 0
    assert failures == []
    assert any(dst == target for _, dst in replace_calls)
    assert all(".sync-staging" in str(src) for src, _ in replace_calls)
    assert not (core_root / ".sync-staging").exists()


def test_execute_cleans_staging_dir_when_replace_fails(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "generated.txt"
    target.write_text("before\n", encoding="utf-8")
    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=target,
                status=ActionStatus.UPDATE,
                detail="update file",
                payload="after\n",
                scope="app:test:text",
                app="opencode",
            )
        ],
        errors=[],
        skipped=[],
    )

    def failing_replace(src: str | Path, dst: str | Path) -> None:
        raise OSError("boom")

    monkeypatch.setattr("os.replace", failing_replace)

    applied, failed, failures = SyncExecutor(core=CoreRepository(core_root)).execute(
        plan
    )

    assert applied == 0
    assert failed == 1
    assert len(failures) == 1
    assert "write_text failed" in failures[0]
    assert target.read_text(encoding="utf-8") == "before\n"
    assert not (core_root / ".sync-staging").exists()


def test_execute_places_global_state_and_revision_metadata_via_staging_replace(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    target = tmp_path / "generated.txt"
    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=target,
                status=ActionStatus.CREATE,
                detail="create file",
                payload="hello\n",
                scope="app:test:text",
                app="opencode",
            )
        ],
        errors=[],
        skipped=[],
    )

    replace_calls: list[tuple[Path, Path]] = []
    original_replace = __import__("os").replace

    def recording_replace(src: str | Path, dst: str | Path) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        replace_calls.append((src_path, dst_path))
        original_replace(src_path, dst_path)

    monkeypatch.setattr("os.replace", recording_replace)

    applied, failed, failures = SyncExecutor(core=CoreRepository(core_root)).execute(
        plan
    )

    assert applied == 1
    assert failed == 0
    assert failures == []

    active_path = core_root / ".sync-revisions" / "active.json"
    active_payload = json.loads(active_path.read_text(encoding="utf-8"))
    manifest_path = Path(active_payload["manifest_path"])
    destination_paths = {dst for _, dst in replace_calls}
    assert target in destination_paths
    assert core_root / ".sync-state.json" in destination_paths
    assert active_path in destination_paths
    assert manifest_path in destination_paths
    assert all(".sync-staging" in str(src) for src, _ in replace_calls)


def test_execute_places_workspace_state_and_revision_metadata_via_staging_replace(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    core = CoreRepository(core_root)
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    core.add_workspace("myws", workspace_root)
    target = workspace_root / "AGENTS.md"
    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=target,
                status=ActionStatus.CREATE,
                detail="create workspace file",
                payload="workspace\n",
                scope="rules",
                app="workspace",
                workspace="myws",
            )
        ],
        errors=[],
        skipped=[],
    )

    replace_calls: list[tuple[Path, Path]] = []
    original_replace = __import__("os").replace

    def recording_replace(src: str | Path, dst: str | Path) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        replace_calls.append((src_path, dst_path))
        original_replace(src_path, dst_path)

    monkeypatch.setattr("os.replace", recording_replace)

    applied, failed, failures = SyncExecutor(core=core).execute(plan)

    assert applied == 1
    assert failed == 0
    assert failures == []

    workspace_config_root = core_root / "workspaces" / "myws"
    active_path = workspace_config_root / ".sync-revisions" / "active.json"
    active_payload = json.loads(active_path.read_text(encoding="utf-8"))
    manifest_path = Path(active_payload["manifest_path"])
    destination_paths = {dst for _, dst in replace_calls}
    assert target in destination_paths
    assert workspace_config_root / ".sync-state.json" in destination_paths
    assert active_path in destination_paths
    assert manifest_path in destination_paths
    assert all(".sync-staging" in str(src) for src, _ in replace_calls)


def test_execute_repairs_pending_revision_before_new_apply(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
) -> None:
    executor = SyncExecutor(core=CoreRepository(core_root))
    primary = tmp_path / "primary.txt"
    sibling = tmp_path / "sibling.txt"

    first_plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=primary,
                status=ActionStatus.CREATE,
                detail="create primary",
                payload="v1\n",
                scope="app:test:text",
                app="opencode",
            ),
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=sibling,
                status=ActionStatus.CREATE,
                detail="create sibling",
                payload="sibling\n",
                scope="app:test:text",
                app="opencode",
            ),
        ],
        errors=[],
        skipped=[],
    )
    applied, failed, failures = executor.execute(first_plan)
    assert applied == 2
    assert failed == 0
    assert failures == []

    sibling.unlink()
    pending_path = core_root / ".sync-revisions" / "pending.json"
    pending_path.write_text('{"revision_id": "pending"}\n', encoding="utf-8")

    broken_plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=primary,
                status=ActionStatus.UPDATE,
                detail="break apply",
                payload=None,
                scope="app:test:text",
                app="opencode",
            )
        ],
        errors=[],
        skipped=[],
    )

    applied, failed, failures = executor.execute(broken_plan)

    assert applied == 0
    assert failed == 1
    assert failures == [f"Missing text payload for write action: {primary}"]
    assert primary.read_text(encoding="utf-8") == "v1\n"
    assert sibling.read_text(encoding="utf-8") == "sibling\n"
    assert not pending_path.exists()
