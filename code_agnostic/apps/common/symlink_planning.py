from pathlib import Path
from typing import Any

from code_agnostic.models import Action, ActionKind, ActionStatus


def plan_resource_symlinks(
    sources: list[Path],
    target_dir: Path,
    scope: str,
    app: str,
) -> tuple[list[Action], list[Path], list[str]]:
    """Plan symlinks for a set of resources (skills or agents).
    Returns (actions, desired_link_paths, skipped_messages).
    """
    actions: list[Action] = []
    desired: list[Path] = []
    skipped: list[str] = []
    for source in sources:
        target = target_dir / source.name
        desired.append(target)
        action = plan_symlink(target, source, scope=scope, app=app)
        actions.append(action)
        if action.status == ActionStatus.CONFLICT:
            skipped.append(f"Link skipped (conflict): {action.path}")
    return actions, desired, skipped


def load_state_links(managed_links: dict[str, Any], scope: str) -> list[Path]:
    raw = managed_links.get(scope, [])
    if not isinstance(raw, list):
        return []
    return [Path(item) for item in raw if isinstance(item, str)]


def plan_symlink(
    target: Path, source: Path, scope: str, app: str | None = None
) -> Action:
    desired = str(source.resolve())
    if target.exists() or target.is_symlink():
        if target.is_symlink():
            current = str(target.resolve())
            if current == desired:
                return Action(
                    ActionKind.SYMLINK,
                    target,
                    ActionStatus.NOOP,
                    "already linked",
                    source=source,
                    app=app,
                    scope=scope,
                )
            return Action(
                ActionKind.SYMLINK,
                target,
                ActionStatus.FIX,
                "symlink points elsewhere",
                source=source,
                app=app,
                scope=scope,
            )
        return Action(
            ActionKind.SYMLINK,
            target,
            ActionStatus.CONFLICT,
            "non-symlink path exists",
            source=source,
            app=app,
            scope=scope,
        )
    return Action(
        ActionKind.SYMLINK,
        target,
        ActionStatus.CREATE,
        "create symlink",
        source=source,
        app=app,
        scope=scope,
    )


def plan_stale_group(
    old_links: list[Path],
    desired_links: list[Path],
    remove_detail: str,
    conflict_detail: str,
    noop_detail: str,
    app: str,
    scope: str,
    skipped: list[str],
    skipped_message: str,
) -> list[Action]:
    desired = {str(path) for path in desired_links}
    actions: list[Action] = []
    for old in old_links:
        if str(old) in desired:
            continue
        if old.is_symlink():
            actions.append(
                Action(
                    ActionKind.REMOVE_SYMLINK,
                    old,
                    ActionStatus.REMOVE,
                    remove_detail,
                    app=app,
                    scope=scope,
                )
            )
        elif old.exists():
            actions.append(
                Action(
                    ActionKind.REMOVE_SYMLINK,
                    old,
                    ActionStatus.CONFLICT,
                    conflict_detail,
                    app=app,
                    scope=scope,
                )
            )
            skipped.append(skipped_message.format(path=old))
        else:
            actions.append(
                Action(
                    ActionKind.REMOVE_SYMLINK,
                    old,
                    ActionStatus.NOOP,
                    noop_detail,
                    app=app,
                    scope=scope,
                )
            )
    return actions
