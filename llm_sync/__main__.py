from pathlib import Path
from typing import Dict

import click
from rich.console import Console

from llm_sync.apps import AppsService
from llm_sync.executor import SyncExecutor
from llm_sync.models import AppId, EditorStatusRow, EditorSyncStatus, SyncPlan, SyncTarget
from llm_sync.planner import SyncPlanner
from llm_sync.repositories.common import CommonRepository
from llm_sync.repositories.opencode import OpenCodeRepository
from llm_sync.status import StatusService
from llm_sync.tui import SyncConsoleUI
from llm_sync.workspaces import WorkspaceService


def _repos_from_obj(_obj: Dict[str, str]) -> tuple[CommonRepository, OpenCodeRepository]:
    common = CommonRepository()
    opencode = OpenCodeRepository()
    return common, opencode


def _empty_plan(skipped_reason: str) -> SyncPlan:
    return SyncPlan(actions=[], errors=[], skipped=[skipped_reason])


def _cursor_status_row(apps: AppsService) -> EditorStatusRow:
    if apps.is_enabled(AppId.CURSOR):
        return EditorStatusRow(
            name="cursor",
            status=EditorSyncStatus.ERROR,
            detail="enabled but sync is not implemented yet",
        )
    return EditorStatusRow(
        name="cursor",
        status=EditorSyncStatus.DISABLED,
        detail="disabled by apps config",
    )


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(ctx: click.Context) -> None:
    """OpenCode-first config sync."""
    ctx.obj = {}


@cli.command(help="Build and print a dry-run plan.")
@click.pass_obj
def plan(obj: Dict[str, str]) -> None:
    ui = SyncConsoleUI(Console())
    common, opencode = _repos_from_obj(obj)
    apps = AppsService(common)

    if not apps.is_enabled(AppId.OPENCODE):
        enabled = apps.enabled_apps()
        if enabled:
            names = ", ".join([app.value for app in enabled])
            plan_result = _empty_plan(f"Enabled apps not implemented for planning yet: {names}")
        else:
            plan_result = _empty_plan("No apps enabled for plan (enable 'opencode' first).")
    else:
        try:
            plan_result = SyncPlanner(common=common, opencode=opencode).build()
        except Exception as exc:
            raise click.ClickException(f"Fatal: {exc}")

    ui.render_plan(plan_result, mode="plan")

    if plan_result.errors:
        raise click.exceptions.Exit(1)


@cli.command(help="Apply planned sync changes.")
@click.argument(
    "target",
    required=False,
    type=click.Choice([SyncTarget.ALL.value, SyncTarget.OPENCODE.value], case_sensitive=False),
    default=SyncTarget.ALL.value,
)
@click.pass_obj
def apply(obj: Dict[str, str], target: str) -> None:
    ui = SyncConsoleUI(Console())
    common, opencode = _repos_from_obj(obj)
    apps = AppsService(common)

    if not apps.is_enabled(AppId.OPENCODE):
        enabled = apps.enabled_apps()
        if enabled:
            names = ", ".join([app.value for app in enabled])
            plan_result = _empty_plan(f"Enabled apps not implemented for apply yet: {names}")
        else:
            plan_result = _empty_plan("No apps enabled for apply (enable 'opencode' first).")
        ui.render_plan(plan_result, mode=f"apply:{target.lower()}")
        ui.render_apply_result(applied=0, failed=0, failures=[])
        return

    try:
        plan_result = SyncPlanner(common=common, opencode=opencode).build()
    except Exception as exc:
        raise click.ClickException(f"Fatal: {exc}")

    normalized_target = SyncTarget(target.lower())
    scoped_plan = plan_result.filter_for_target(
        target=normalized_target,
        config_path=opencode.config_path,
        skills_root=opencode.skills_dir,
        agents_root=opencode.agents_dir,
    )

    ui.render_plan(scoped_plan, mode=f"apply:{normalized_target.value}")

    if scoped_plan.errors:
        raise click.ClickException("Apply aborted due to planning/parsing errors above.")

    applied, failed, failures = SyncExecutor(common=common, opencode=opencode).execute(scoped_plan)
    ui.render_apply_result(applied, failed, failures)

    if failed:
        raise click.exceptions.Exit(1)


@cli.command(help="Show sync status for editors and workspaces.")
@click.pass_obj
def status(obj: Dict[str, str]) -> None:
    ui = SyncConsoleUI(Console())
    common, opencode = _repos_from_obj(obj)
    apps = AppsService(common)
    status_service = StatusService()

    if apps.is_enabled(AppId.OPENCODE):
        try:
            plan_result = SyncPlanner(common=common, opencode=opencode).build()
            editor_rows = status_service.build_editor_status(plan_result, opencode)
            editor_rows = [row for row in editor_rows if row.name != "cursor"]
            editor_rows.append(_cursor_status_row(apps))
        except Exception as exc:
            editor_rows = [
                EditorStatusRow(
                    name="opencode",
                    status=EditorSyncStatus.ERROR,
                    detail=f"cannot evaluate ({exc})",
                ),
                _cursor_status_row(apps),
            ]
        workspace_rows = status_service.build_workspace_status(common)
    else:
        editor_rows = [
            EditorStatusRow(
                name="opencode",
                status=EditorSyncStatus.DISABLED,
                detail="disabled by apps config",
            ),
            _cursor_status_row(apps),
        ]
        workspace_rows = []

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
@click.argument("name", type=click.Choice([app.value for app in AppId], case_sensitive=False))
@click.pass_obj
def apps_enable(obj: Dict[str, str], name: str) -> None:
    ui = SyncConsoleUI(Console())
    common, _ = _repos_from_obj(obj)
    service = AppsService(common)
    app_id = AppId(name.lower())
    service.enable(app_id)
    ui.render_apps([row.as_dict() for row in service.list_status_rows()])


@apps.command("disable", help="Disable app sync target.")
@click.argument("name", type=click.Choice([app.value for app in AppId], case_sensitive=False))
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
