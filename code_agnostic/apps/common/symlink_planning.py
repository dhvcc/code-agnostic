from pathlib import Path

from code_agnostic.models import Action, ActionKind, ActionStatus


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
