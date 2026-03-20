"""Status command."""

import click
from rich.console import Console

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.cli.helpers import status_row_for_app
from code_agnostic.cli.options import app_option, verbose_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.models import EditorSyncStatus
from code_agnostic.status import StatusService
from code_agnostic.tui import SyncConsoleUI


@click.command(help="Show sync status for editors and workspaces.")
@app_option()
@verbose_option()
@click.pass_obj
def status(obj: dict[str, str], app: str, verbose: bool) -> None:
    target = app or "all"
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    apps = AppsService(core)

    try:
        plan_result = apps.plan_for_target("all")
        editor_rows = [
            status_row_for_app(app_name, plan_result, apps)
            for app_name in apps.available_apps()
        ]
    except Exception as exc:
        from code_agnostic.models import EditorStatusRow

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
    enabled_services = apps._resolve_services_for_target("all")
    ui.render_status(
        editor_rows,
        status_service.build_workspace_status(core, app_services=enabled_services),
    )
