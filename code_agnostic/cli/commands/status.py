"""Status command."""

import click
from rich.console import Console

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.cli.helpers import status_row_for_app
from code_agnostic.cli.options import app_option, verbose_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.models import EditorStatusRow, EditorSyncStatus, WorkspaceSyncStatus
from code_agnostic.status import StatusService
from code_agnostic.tui import SyncConsoleUI


def _status_row_for_app(app_name: str, apps: AppsService) -> EditorStatusRow:
    if not apps.is_enabled(app_name):
        return EditorStatusRow(
            name=app_name,
            status=EditorSyncStatus.DISABLED,
            detail="disabled by apps config",
        )

    try:
        return status_row_for_app(app_name, apps.plan_for_target(app_name), apps)
    except Exception as exc:
        return EditorStatusRow(
            name=app_name,
            status=EditorSyncStatus.ERROR,
            detail=f"cannot evaluate ({exc})",
        )


@click.command(help="Show sync status for editors and workspaces.")
@app_option()
@verbose_option()
@click.pass_obj
def status(obj: dict[str, str], app: str, verbose: bool) -> None:
    target = app or "all"
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    apps = AppsService(core)

    normalized_target = target.lower()
    if normalized_target != "all":
        app_names = [normalized_target]
    else:
        app_names = apps.available_apps()

    editor_rows = [_status_row_for_app(app_name, apps) for app_name in app_names]

    status_service = StatusService()
    enabled_services = apps._resolve_services_for_target(normalized_target)
    workspace_rows = status_service.build_workspace_status(
        core, app_services=enabled_services
    )
    ui.render_status(
        editor_rows,
        workspace_rows,
    )

    if any(row.status == EditorSyncStatus.ERROR for row in editor_rows) or any(
        row.status == WorkspaceSyncStatus.ERROR for row in workspace_rows
    ):
        raise click.exceptions.Exit(1)
