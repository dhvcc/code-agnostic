"""Apps group commands."""

import click
from rich.console import Console

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.cli.options import manageable_app_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.tui import SyncConsoleUI


@click.group(help="Enable or disable app sync targets.")
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
@manageable_app_option()
@click.pass_obj
def apps_enable(obj: dict[str, str], app: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = AppsService(core)
    service.enable(app.lower())
    ui.render_apps(service.list_status_rows())


@apps.command("disable", help="Disable app sync target.")
@manageable_app_option()
@click.pass_obj
def apps_disable(obj: dict[str, str], app: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = AppsService(core)
    service.disable(app.lower())
    ui.render_apps(service.list_status_rows())
