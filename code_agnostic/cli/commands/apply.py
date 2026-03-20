"""Apply command."""

import click
from rich.console import Console

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.cli.options import app_option, verbose_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.tui import SyncConsoleUI


@click.command(help="Apply planned sync changes.")
@app_option()
@verbose_option()
@click.pass_obj
def apply(obj: dict[str, str], app: str, verbose: bool) -> None:
    target = app or "all"
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    apps = AppsService(core)

    try:
        scoped_plan = apps.plan_for_target(target)
    except Exception as exc:
        raise click.ClickException(f"Fatal: {exc}")

    ui.render_plan(scoped_plan, mode=f"apply:{target.lower()}", verbose=verbose)

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
