from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from code_agnostic.models import Action, ActionKind, ActionStatus


class ArtifactKind(str, Enum):
    TEXT = "text"


class OwnershipPolicy(str, Enum):
    OWNED_ONLY = "owned_only"
    MANAGED_REPLACE = "managed_replace"
    MERGE_NATIVE_CONFIG = "merge_native_config"


@dataclass(frozen=True)
class GeneratedArtifact:
    path: Path
    kind: ArtifactKind
    payload: Any
    ownership: OwnershipPolicy
    scope: str
    app: str
    create_detail: str
    noop_detail: str
    update_detail: str
    conflict_detail: str = "non-managed path exists"
    managed_root: Path | None = None


def plan_generated_artifact(
    artifact: GeneratedArtifact,
    *,
    managed_paths: set[Path],
    removable_link_paths: set[Path] | None = None,
) -> Action:
    if artifact.kind != ArtifactKind.TEXT:
        raise NotImplementedError(
            f"Unsupported generated artifact kind: {artifact.kind}"
        )
    if not isinstance(artifact.payload, str):
        raise TypeError("Text generated artifacts require a string payload")

    managed_path_set = {path.resolve(strict=False) for path in managed_paths}
    removable = {path.resolve(strict=False) for path in (removable_link_paths or set())}
    has_symlink_ancestor, is_removable_ancestor = _symlink_ancestor_state(
        artifact.path, removable, artifact.managed_root
    )

    if artifact.ownership == OwnershipPolicy.OWNED_ONLY:
        target_key = artifact.path.resolve(strict=False)
        is_managed_target = target_key in managed_path_set or _is_under_any(
            target_key, removable
        )
        if not is_managed_target and not is_removable_ancestor:
            if (
                not artifact.path.exists()
                and not artifact.path.is_symlink()
                and not has_symlink_ancestor
            ):
                return _action(artifact, ActionStatus.CREATE, artifact.create_detail)
            return _action(artifact, ActionStatus.CONFLICT, artifact.conflict_detail)

    return _plan_replace_text_artifact(
        artifact,
        has_symlink_ancestor=has_symlink_ancestor,
        is_removable_ancestor=is_removable_ancestor,
    )


def _is_under_any(path: Path, ancestors: set[Path]) -> bool:
    return any(
        path == ancestor or path.is_relative_to(ancestor) for ancestor in ancestors
    )


def _symlink_ancestor_state(
    target: Path, removable_link_paths: set[Path], managed_root: Path | None
) -> tuple[bool, bool]:
    current = target
    found_symlink = False
    while True:
        in_managed_root = managed_root is None or (
            current == managed_root or current.is_relative_to(managed_root)
        )
        if current.is_symlink() and in_managed_root:
            found_symlink = True
            if current.resolve(strict=False) in removable_link_paths:
                return True, True
        if current.parent == current:
            return found_symlink, False
        current = current.parent


def _plan_replace_text_artifact(
    artifact: GeneratedArtifact,
    *,
    has_symlink_ancestor: bool,
    is_removable_ancestor: bool,
) -> Action:
    if has_symlink_ancestor and not is_removable_ancestor:
        return _action(artifact, ActionStatus.CONFLICT, artifact.conflict_detail)

    if not artifact.path.exists() and not artifact.path.is_symlink():
        return _action(artifact, ActionStatus.CREATE, artifact.create_detail)

    if artifact.path.is_file():
        existing = artifact.path.read_text(encoding="utf-8")
        if existing == artifact.payload:
            return _action(artifact, ActionStatus.NOOP, artifact.noop_detail)
        return _action(artifact, ActionStatus.UPDATE, artifact.update_detail)

    return _action(artifact, ActionStatus.CONFLICT, artifact.conflict_detail)


def _action(
    artifact: GeneratedArtifact,
    status: ActionStatus,
    detail: str,
) -> Action:
    return Action(
        kind=ActionKind.WRITE_TEXT,
        path=artifact.path,
        status=status,
        detail=detail,
        payload=artifact.payload,
        app=artifact.app,
        scope=artifact.scope,
    )
