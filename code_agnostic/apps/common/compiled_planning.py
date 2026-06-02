from pathlib import Path

from code_agnostic.generated_artifacts import (
    ArtifactKind,
    GeneratedArtifact,
    OwnershipPolicy,
    plan_generated_artifact,
)
from code_agnostic.models import Action


def find_replaceable_symlink_ancestor(target: Path, managed_root: Path) -> Path | None:
    current = target
    while True:
        if current.is_symlink() and (
            current == managed_root or current.is_relative_to(managed_root)
        ):
            return current
        if current.parent == current:
            return None
        current = current.parent


def plan_compiled_text_action(
    *,
    target: Path,
    payload: str,
    managed_paths: set[Path],
    removable_link_paths: set[Path] | None = None,
    managed_root: Path | None = None,
    scope: str,
    app: str,
    create_detail: str,
    noop_detail: str,
    update_detail: str,
    conflict_detail: str = "non-managed path exists",
) -> Action:
    return _plan_text_action(
        ownership=OwnershipPolicy.MANAGED_REPLACE,
        target=target,
        payload=payload,
        managed_paths=managed_paths,
        removable_link_paths=removable_link_paths,
        managed_root=managed_root,
        scope=scope,
        app=app,
        create_detail=create_detail,
        noop_detail=noop_detail,
        update_detail=update_detail,
        conflict_detail=conflict_detail,
    )


def plan_owned_compiled_text_action(
    *,
    target: Path,
    payload: str,
    managed_paths: set[Path],
    removable_link_paths: set[Path] | None = None,
    managed_root: Path | None = None,
    scope: str,
    app: str,
    create_detail: str,
    noop_detail: str,
    update_detail: str,
    conflict_detail: str = "non-managed path exists",
) -> Action:
    return _plan_text_action(
        ownership=OwnershipPolicy.OWNED_ONLY,
        target=target,
        payload=payload,
        managed_paths=managed_paths,
        removable_link_paths=removable_link_paths,
        managed_root=managed_root,
        scope=scope,
        app=app,
        create_detail=create_detail,
        noop_detail=noop_detail,
        update_detail=update_detail,
        conflict_detail=conflict_detail,
    )


def _plan_text_action(
    *,
    ownership: OwnershipPolicy,
    target: Path,
    payload: str,
    managed_paths: set[Path],
    removable_link_paths: set[Path] | None,
    managed_root: Path | None,
    scope: str,
    app: str,
    create_detail: str,
    noop_detail: str,
    update_detail: str,
    conflict_detail: str,
) -> Action:
    return plan_generated_artifact(
        GeneratedArtifact(
            path=target,
            kind=ArtifactKind.TEXT,
            payload=payload,
            ownership=ownership,
            managed_root=managed_root,
            scope=scope,
            app=app,
            create_detail=create_detail,
            noop_detail=noop_detail,
            update_detail=update_detail,
            conflict_detail=conflict_detail,
        ),
        managed_paths=managed_paths,
        removable_link_paths=removable_link_paths,
    )
