from pathlib import Path
from collections.abc import Callable

import click
from rich.console import Console

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.apps.common.framework import list_registered_app_services
from code_agnostic.core.repository import CoreRepository
from code_agnostic.models import ActionStatus, EditorStatusRow, EditorSyncStatus
from code_agnostic.status import StatusService
from code_agnostic.tui import SyncConsoleUI
from code_agnostic.workspaces import WorkspaceService


def _target_values() -> list[str]:
    return ["all", *[app.value for app in list_registered_app_services()]]


def _target_argument(default: str = "all") -> Callable:
    return click.argument(
        "target",
        required=False,
        type=click.Choice(_target_values(), case_sensitive=False),
        default=default,
    )


def _status_row_for_app(app_name: str, plan, apps: AppsService) -> EditorStatusRow:
    if not apps.is_enabled(app_name):
        return EditorStatusRow(
            name=app_name,
            status=EditorSyncStatus.DISABLED,
            detail="disabled by apps config",
        )

    relevant = [action for action in plan.actions if action.app == app_name]

    for error in plan.errors:
        if app_name in str(error).lower():
            return EditorStatusRow(
                name=app_name,
                status=EditorSyncStatus.ERROR,
                detail=f"cannot evaluate ({error})",
            )

    synced = (
        all(action.status == ActionStatus.NOOP for action in relevant)
        if relevant
        else True
    )
    return EditorStatusRow(
        name=app_name,
        status=EditorSyncStatus.SYNCED if synced else EditorSyncStatus.DRIFT,
        detail="in sync" if synced else "out of sync",
    )


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(ctx: click.Context) -> None:
    """App-based config sync."""
    ctx.obj = {}


@cli.command(help="Build and print a dry-run plan.")
@_target_argument()
@click.pass_obj
def plan(obj: dict[str, str], target: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    apps = AppsService(core)

    try:
        scoped_plan = apps.plan_for_target(target)
    except Exception as exc:
        raise click.ClickException(f"Fatal: {exc}")

    ui.render_plan(scoped_plan, mode=f"plan:{target.lower()}")

    if scoped_plan.errors:
        raise click.exceptions.Exit(1)


@cli.command(help="Apply planned sync changes.")
@_target_argument()
@click.pass_obj
def apply(obj: dict[str, str], target: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    apps = AppsService(core)

    try:
        scoped_plan = apps.plan_for_target(target)
    except Exception as exc:
        raise click.ClickException(f"Fatal: {exc}")

    ui.render_plan(scoped_plan, mode=f"apply:{target.lower()}")

    if not scoped_plan.actions and not scoped_plan.errors:
        ui.render_apply_result(applied=0, failed=0, failures=[])
        return

    if scoped_plan.errors:
        raise click.ClickException(
            "Apply aborted due to planning/parsing errors above."
        )

    applied, failed, failures = apps.execute_plan(scoped_plan)
    ui.render_apply_result(applied, failed, failures)

    if failed:
        raise click.exceptions.Exit(1)


@cli.command(help="Show sync status for editors and workspaces.")
@_target_argument()
@click.pass_obj
def status(obj: dict[str, str], target: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    apps = AppsService(core)

    try:
        plan_result = apps.plan_for_target("all")
        editor_rows = [
            _status_row_for_app(app_name, plan_result, apps)
            for app_name in apps.available_apps()
        ]
    except Exception as exc:
        editor_rows = [
            EditorStatusRow(
                name=app_name,
                status=EditorSyncStatus.ERROR,
                detail=f"cannot evaluate ({exc})",
            )
            for app_name in apps.available_apps()
        ]

    normalized_target = target.lower()
    if normalized_target != "all":
        editor_rows = [row for row in editor_rows if row.name == normalized_target]

    status_service = StatusService()
    ui.render_status(
        editor_rows,
        status_service.build_workspace_status(core),
    )


@cli.group(help="Enable or disable app sync targets.")
def apps() -> None:
    pass


@apps.command("list", help="List app sync target status.")
@click.pass_obj
def apps_list(obj: dict[str, str]) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = AppsService(core)
    ui.render_apps(service.list_status_rows())


@apps.command("enable", help="Enable app sync target.")
@click.argument("name", type=click.Choice(_target_values()[1:], case_sensitive=False))
@click.pass_obj
def apps_enable(obj: dict[str, str], name: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = AppsService(core)
    service.enable(name.lower())
    ui.render_apps(service.list_status_rows())


@apps.command("disable", help="Disable app sync target.")
@click.argument("name", type=click.Choice(_target_values()[1:], case_sensitive=False))
@click.pass_obj
def apps_disable(obj: dict[str, str], name: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = AppsService(core)
    service.disable(name.lower())
    ui.render_apps(service.list_status_rows())


@cli.group(help="Manage workspace roots for repo rule propagation.")
def workspaces() -> None:
    pass


@workspaces.command("add", help="Add a workspace by name and path.")
@click.argument("name")
@click.argument("path", type=click.Path(path_type=Path))
@click.pass_obj
def workspaces_add(obj: dict[str, str], name: str, path: Path) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    try:
        core.add_workspace(name, path)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    ui.render_workspace_saved(name, str(path.expanduser().resolve()))


@workspaces.command("remove", help="Remove a workspace from config by name.")
@click.argument("name")
@click.pass_obj
def workspaces_remove(obj: dict[str, str], name: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    existing = {item["name"]: item["path"] for item in core.load_workspaces()}
    removed = core.remove_workspace(name)
    if not removed:
        raise click.ClickException(f"Workspace not found: {name}")
    ui.render_workspace_saved(name, existing.get(name, ""), removed=True)


@workspaces.command("list", help="List configured workspaces and detected repos.")
@click.pass_obj
def workspaces_list(obj: dict[str, str]) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    workspace_service = WorkspaceService()

    overview: list[dict] = []
    for item in core.load_workspaces():
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
