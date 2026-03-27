"""Shared option decorators for CLI commands."""

from collections.abc import Callable

import click

from code_agnostic.apps.app_id import app_ids_by_capability
from code_agnostic.apps.common.framework import list_registered_app_services


def _target_values() -> list[str]:
    registered = set(list_registered_app_services())
    targetable = set(app_ids_by_capability(targetable=True))
    return [
        "all",
        *[
            app.value
            for app in sorted(registered & targetable, key=lambda item: item.value)
        ],
    ]


def _manageable_app_values() -> list[str]:
    registered = set(list_registered_app_services())
    manageable = set(app_ids_by_capability(toggleable=True))
    return [
        app.value
        for app in sorted(registered & manageable, key=lambda item: item.value)
    ]


def _import_source_values() -> list[str]:
    registered = set(list_registered_app_services())
    importable = set(app_ids_by_capability(importable=True))
    return [
        app.value
        for app in sorted(registered & importable, key=lambda item: item.value)
    ]


def app_option(required: bool = False) -> Callable:
    return click.option(
        "-a",
        "--app",
        required=required,
        type=click.Choice(_target_values(), case_sensitive=False),
        default="all" if not required else None,
        help="Target app (default: all).",
    )


def manageable_app_option(required: bool = True) -> Callable:
    return click.option(
        "-a",
        "--app",
        required=required,
        type=click.Choice(_manageable_app_values(), case_sensitive=False),
        help="App to manage.",
    )


def import_app_option(required: bool = True) -> Callable:
    return click.option(
        "-a",
        "--app",
        required=required,
        type=click.Choice(_import_source_values(), case_sensitive=False),
        help="Source app to import from.",
    )


def workspace_option(required: bool = False) -> Callable:
    return click.option(
        "-w",
        "--workspace",
        required=required,
        default=None,
        help="Workspace name.",
    )


def verbose_option() -> Callable:
    return click.option("-v", "--verbose", is_flag=True, default=False)


def experimental_option() -> Callable:
    return click.option(
        "--experimental",
        is_flag=True,
        default=False,
        help=(
            "Enable experimental behavior: propagate Cursor workspace config into "
            "each git sub-repository (.cursor/), not only the workspace root."
        ),
    )
