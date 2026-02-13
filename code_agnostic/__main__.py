from pathlib import Path
from typing import Callable, Dict

import click
from rich.console import Console

from code_agnostic.apps import AppsService
from code_agnostic.apps.sync.common import common_mcp_to_dto
from code_agnostic.apps.sync.framework import (
    RegisteredAppConfigService,
    create_registered_app_service,
)
from code_agnostic.errors import SyncAppError
from code_agnostic.executor import SyncExecutor
from code_agnostic.models import (
    Action,
    ActionKind,
    ActionStatus,
    AppId,
    EditorStatusRow,
    EditorSyncStatus,
    SyncPlan,
    SyncTarget,
)
from code_agnostic.planner import SyncPlanner
from code_agnostic.repositories.common import CommonRepository
from code_agnostic.repositories.opencode import OpenCodeRepository
from code_agnostic.status import StatusService
from code_agnostic.tui import SyncConsoleUI
from code_agnostic.workspaces import WorkspaceService


TARGET_VALUES = [target.value for target in SyncTarget]


def _target_argument(default: str = SyncTarget.ALL.value) -> Callable:
    return click.argument(
        "target",
        required=False,
        type=click.Choice(TARGET_VALUES, case_sensitive=False),
        default=default,
    )


def _normalize_target(value: str) -> SyncTarget:
    return SyncTarget(value.lower())


def _repos_from_obj(
    _obj: Dict[str, str],
) -> tuple[CommonRepository, OpenCodeRepository]:
    common = CommonRepository()
    opencode = OpenCodeRepository()
    return common, opencode


def _empty_plan(skipped_reason: str) -> SyncPlan:
    return SyncPlan(actions=[], errors=[], skipped=[skipped_reason])


def _merge_plans(*plans: SyncPlan) -> SyncPlan:
    actions: list[Action] = []
    errors: list[Exception] = []
    skipped: list[str] = []
    for plan in plans:
        actions.extend(plan.actions)
        errors.extend(plan.errors)
        skipped.extend(plan.skipped)
    return SyncPlan(actions=actions, errors=errors, skipped=skipped)


def _build_mcp_app_plan(common: CommonRepository, apps: AppsService) -> SyncPlan:
    enabled = set(apps.enabled_apps())
    if not ({AppId.CURSOR, AppId.CODEX} & enabled):
        return SyncPlan(actions=[], errors=[], skipped=[])

    try:
        mcp_base = common.load_mcp_base()
    except SyncAppError as exc:
        return SyncPlan(actions=[], errors=[exc], skipped=[])

    desired_common = common_mcp_to_dto(mcp_base.get("mcpServers", {}))
    actions: list[Action] = []
    errors: list[Exception] = []

    services: list[RegisteredAppConfigService] = []
    for app in sorted(enabled, key=lambda item: item.value):
        if app == AppId.OPENCODE:
            continue
        try:
            services.append(create_registered_app_service(app))
        except KeyError:
            continue

    for service in services:
        try:
            actions.append(service.build_action(desired_common))
        except SyncAppError as exc:
            errors.append(exc)

    return SyncPlan(actions=actions, errors=errors, skipped=[])


def _build_combined_plan(
    common: CommonRepository, opencode: OpenCodeRepository, apps: AppsService
) -> SyncPlan:
    enabled = set(apps.enabled_apps())

    workspace_plan = SyncPlanner(
        common=common,
        opencode=opencode,
        include_opencode=False,
        include_workspace=True,
    ).build()

    opencode_plan = SyncPlan(actions=[], errors=[], skipped=[])
    if AppId.OPENCODE in enabled:
        opencode_plan = SyncPlanner(
            common=common,
            opencode=opencode,
            include_opencode=True,
            include_workspace=False,
        ).build()
    mcp_apps_plan = _build_mcp_app_plan(common, apps)

    combined = _merge_plans(opencode_plan, mcp_apps_plan, workspace_plan)
    if (
        not enabled
        and not combined.actions
        and not combined.errors
        and not combined.skipped
    ):
        return _empty_plan("No apps enabled for sync.")
    return combined


def _scope_plan_for_target(
    plan: SyncPlan, target: SyncTarget, opencode: OpenCodeRepository
) -> SyncPlan:
    if target == SyncTarget.ALL:
        return plan
    return plan.filter_for_target(
        target=target,
        config_path=opencode.config_path,
        skills_root=opencode.skills_dir,
        agents_root=opencode.agents_dir,
    )


def _requires_state_persist(scoped_plan: SyncPlan) -> bool:
    for action in scoped_plan.actions:
        if action.kind in (ActionKind.SYMLINK, ActionKind.REMOVE_SYMLINK):
            return True
        if action.app in (None, AppId.OPENCODE.value):
            return True
    return False


def _status_row_for_app(
    app: AppId, plan: SyncPlan, apps: AppsService
) -> EditorStatusRow:
    if not apps.is_enabled(app):
        return EditorStatusRow(
            name=app.value,
            status=EditorSyncStatus.DISABLED,
            detail="disabled by apps config",
        )

    if app == AppId.OPENCODE:
        relevant = [
            action
            for action in plan.actions
            if action.app is None or action.app == AppId.OPENCODE.value
        ]
    else:
        relevant = [action for action in plan.actions if action.app == app.value]

    if plan.errors:
        for error in plan.errors:
            if app.value in str(error).lower():
                return EditorStatusRow(
                    name=app.value,
                    status=EditorSyncStatus.ERROR,
                    detail=f"cannot evaluate ({error})",
                )

    synced = (
        all(action.status == ActionStatus.NOOP for action in relevant)
        if relevant
        else True
    )
    return EditorStatusRow(
        name=app.value,
        status=EditorSyncStatus.SYNCED if synced else EditorSyncStatus.DRIFT,
        detail="in sync" if synced else "out of sync",
    )


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(ctx: click.Context) -> None:
    """OpenCode-first config sync."""
    ctx.obj = {}


@cli.command(help="Build and print a dry-run plan.")
@_target_argument()
@click.pass_obj
def plan(obj: Dict[str, str], target: str) -> None:
    ui = SyncConsoleUI(Console())
    common, opencode = _repos_from_obj(obj)
    apps = AppsService(common)

    try:
        plan_result = _build_combined_plan(common=common, opencode=opencode, apps=apps)
    except Exception as exc:
        raise click.ClickException(f"Fatal: {exc}")

    normalized_target = _normalize_target(target)
    scoped_plan = _scope_plan_for_target(plan_result, normalized_target, opencode)

    ui.render_plan(scoped_plan, mode=f"plan:{normalized_target.value}")

    if scoped_plan.errors:
        raise click.exceptions.Exit(1)


@cli.command(help="Apply planned sync changes.")
@_target_argument()
@click.pass_obj
def apply(obj: Dict[str, str], target: str) -> None:
    ui = SyncConsoleUI(Console())
    common, opencode = _repos_from_obj(obj)
    apps = AppsService(common)

    try:
        plan_result = _build_combined_plan(common=common, opencode=opencode, apps=apps)
    except Exception as exc:
        raise click.ClickException(f"Fatal: {exc}")

    normalized_target = _normalize_target(target)
    scoped_plan = _scope_plan_for_target(plan_result, normalized_target, opencode)

    ui.render_plan(scoped_plan, mode=f"apply:{normalized_target.value}")

    if not scoped_plan.actions and not scoped_plan.errors:
        ui.render_apply_result(applied=0, failed=0, failures=[])
        return

    if scoped_plan.errors:
        raise click.ClickException(
            "Apply aborted due to planning/parsing errors above."
        )

    persist_state = _requires_state_persist(scoped_plan)
    applied, failed, failures = SyncExecutor(common=common, opencode=opencode).execute(
        scoped_plan, persist_state=persist_state
    )
    ui.render_apply_result(applied, failed, failures)

    if failed:
        raise click.exceptions.Exit(1)


@cli.command(help="Show sync status for editors and workspaces.")
@_target_argument()
@click.pass_obj
def status(obj: Dict[str, str], target: str) -> None:
    ui = SyncConsoleUI(Console())
    common, opencode = _repos_from_obj(obj)
    apps = AppsService(common)
    status_service = StatusService()

    try:
        plan_result = _build_combined_plan(common=common, opencode=opencode, apps=apps)
        editor_rows = [_status_row_for_app(app, plan_result, apps) for app in AppId]
    except Exception as exc:
        editor_rows = [
            EditorStatusRow(
                name=app.value,
                status=EditorSyncStatus.ERROR,
                detail=f"cannot evaluate ({exc})",
            )
            for app in AppId
        ]

    normalized_target = _normalize_target(target)
    if normalized_target != SyncTarget.ALL:
        editor_rows = [
            row for row in editor_rows if row.name == normalized_target.value
        ]

    workspace_rows = status_service.build_workspace_status(common)

    ui.render_status(
        [item.as_dict() for item in editor_rows],
        [item.as_dict() for item in workspace_rows],
    )


@cli.group(help="Enable or disable app sync targets.")
def apps() -> None:
    pass


@apps.command("list", help="List app sync target status.")
@click.pass_obj
def apps_list(obj: Dict[str, str]) -> None:
    ui = SyncConsoleUI(Console())
    common, _ = _repos_from_obj(obj)
    service = AppsService(common)
    ui.render_apps([row.as_dict() for row in service.list_status_rows()])


@apps.command("enable", help="Enable app sync target.")
@click.argument(
    "name", type=click.Choice([app.value for app in AppId], case_sensitive=False)
)
@click.pass_obj
def apps_enable(obj: Dict[str, str], name: str) -> None:
    ui = SyncConsoleUI(Console())
    common, _ = _repos_from_obj(obj)
    service = AppsService(common)
    app_id = AppId(name.lower())
    service.enable(app_id)
    ui.render_apps([row.as_dict() for row in service.list_status_rows()])


@apps.command("disable", help="Disable app sync target.")
@click.argument(
    "name", type=click.Choice([app.value for app in AppId], case_sensitive=False)
)
@click.pass_obj
def apps_disable(obj: Dict[str, str], name: str) -> None:
    ui = SyncConsoleUI(Console())
    common, _ = _repos_from_obj(obj)
    service = AppsService(common)
    app_id = AppId(name.lower())
    service.disable(app_id)
    ui.render_apps([row.as_dict() for row in service.list_status_rows()])


@cli.group(help="Manage workspace roots for repo rule propagation.")
def workspaces() -> None:
    pass


@workspaces.command("add", help="Add a workspace by name and path.")
@click.argument("name")
@click.argument("path", type=click.Path(path_type=Path))
@click.pass_obj
def workspaces_add(obj: Dict[str, str], name: str, path: Path) -> None:
    ui = SyncConsoleUI(Console())
    common, _ = _repos_from_obj(obj)
    try:
        common.add_workspace(name, path)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    ui.render_workspace_saved(name, str(path.expanduser().resolve()))


@workspaces.command("remove", help="Remove a workspace from config by name.")
@click.argument("name")
@click.pass_obj
def workspaces_remove(obj: Dict[str, str], name: str) -> None:
    ui = SyncConsoleUI(Console())
    common, _ = _repos_from_obj(obj)
    existing = {item["name"]: item["path"] for item in common.load_workspaces()}
    removed = common.remove_workspace(name)
    if not removed:
        raise click.ClickException(f"Workspace not found: {name}")
    ui.render_workspace_saved(name, existing.get(name, ""), removed=True)


@workspaces.command("list", help="List configured workspaces and detected repos.")
@click.pass_obj
def workspaces_list(obj: Dict[str, str]) -> None:
    ui = SyncConsoleUI(Console())
    common, _ = _repos_from_obj(obj)
    workspace_service = WorkspaceService()

    overview: list[dict] = []
    for item in common.load_workspaces():
        workspace_path = Path(item["path"])
        repos: list[str] = []
        if workspace_path.exists() and workspace_path.is_dir():
            repos = [
                str(path.relative_to(workspace_path))
                for path in workspace_service.discover_git_repos(workspace_path)
            ]
        overview.append(
            {
                "name": item["name"],
                "path": item["path"],
                "repos": repos,
            }
        )

    ui.render_workspaces_overview(overview)


def main() -> int:
    try:
        cli(standalone_mode=False)
    except click.exceptions.Exit as exc:
        code = exc.exit_code
        return code if isinstance(code, int) else 1
    except click.ClickException as exc:
        exc.show()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
