"""Plan command."""

import click
from rich.console import Console

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.cli.options import app_option, verbose_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.tui import SyncConsoleUI


@click.command(help="Build and print a dry-run plan.")
@app_option()
@verbose_option()
@click.pass_obj
def plan(obj: dict[str, str], app: str, verbose: bool) -> None:
    target = app or "all"
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    apps = AppsService(core)

    try:
        scoped_plan = apps.plan_for_target(target)
    except Exception as exc:
        raise click.ClickException(f"Fatal: {exc}")

    ui.render_plan(scoped_plan, mode=f"plan:{target.lower()}", verbose=verbose)

    if scoped_plan.errors:
        raise click.exceptions.Exit(1)
