from pathlib import Path

from code_agnostic.models import Action, ActionKind, ActionStatus


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
            current_key = current.resolve(strict=False)
            if current_key in removable_link_paths:
                return True, True
        if current.parent == current:
            return found_symlink, False
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
    removable = removable_link_paths or set()
    has_symlink_ancestor, is_removable_ancestor = _symlink_ancestor_state(
        target, removable, managed_root
    )

    if has_symlink_ancestor and not is_removable_ancestor:
        return Action(
            kind=ActionKind.WRITE_TEXT,
            path=target,
            status=ActionStatus.CONFLICT,
            detail=conflict_detail,
            payload=payload,
            app=app,
            scope=scope,
        )

    if has_symlink_ancestor and is_removable_ancestor:
        if target.is_file():
            existing = target.read_text(encoding="utf-8")
            if existing == payload:
                return Action(
                    kind=ActionKind.WRITE_TEXT,
                    path=target,
                    status=ActionStatus.NOOP,
                    detail=noop_detail,
                    payload=payload,
                    app=app,
                    scope=scope,
                )
            return Action(
                kind=ActionKind.WRITE_TEXT,
                path=target,
                status=ActionStatus.UPDATE,
                detail=update_detail,
                payload=payload,
                app=app,
                scope=scope,
            )
        return Action(
            kind=ActionKind.WRITE_TEXT,
            path=target,
            status=ActionStatus.CREATE,
            detail=create_detail,
            payload=payload,
            app=app,
            scope=scope,
        )

    if not target.exists() and not target.is_symlink():
        return Action(
            kind=ActionKind.WRITE_TEXT,
            path=target,
            status=ActionStatus.CREATE,
            detail=create_detail,
            payload=payload,
            app=app,
            scope=scope,
        )

    if target.is_file():
        existing = target.read_text(encoding="utf-8")
        if existing == payload:
            return Action(
                kind=ActionKind.WRITE_TEXT,
                path=target,
                status=ActionStatus.NOOP,
                detail=noop_detail,
                payload=payload,
                app=app,
                scope=scope,
            )
        return Action(
            kind=ActionKind.WRITE_TEXT,
            path=target,
            status=ActionStatus.UPDATE,
            detail=update_detail,
            payload=payload,
            app=app,
            scope=scope,
        )

    return Action(
        kind=ActionKind.WRITE_TEXT,
        path=target,
        status=ActionStatus.CONFLICT,
        detail=conflict_detail,
        payload=payload,
        app=app,
        scope=scope,
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
    target_key = target.resolve(strict=False)
    removable = removable_link_paths or set()
    has_symlink_ancestor, is_removable_ancestor = _symlink_ancestor_state(
        target, removable, managed_root
    )

    if target_key in managed_paths or is_removable_ancestor:
        return plan_compiled_text_action(
            target=target,
            payload=payload,
            managed_paths=managed_paths,
            removable_link_paths=removable,
            managed_root=managed_root,
            scope=scope,
            app=app,
            create_detail=create_detail,
            noop_detail=noop_detail,
            update_detail=update_detail,
            conflict_detail=conflict_detail,
        )

    if not target.exists() and not target.is_symlink() and not has_symlink_ancestor:
        return Action(
            kind=ActionKind.WRITE_TEXT,
            path=target,
            status=ActionStatus.CREATE,
            detail=create_detail,
            payload=payload,
            app=app,
            scope=scope,
        )

    return Action(
        kind=ActionKind.WRITE_TEXT,
        path=target,
        status=ActionStatus.CONFLICT,
        detail=conflict_detail,
        payload=payload,
        app=app,
        scope=scope,
    )
