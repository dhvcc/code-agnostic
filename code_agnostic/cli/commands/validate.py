"""Validate command."""

import click

from code_agnostic.cli.helpers import workspace_config_root
from code_agnostic.cli.options import workspace_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.validation import ConfigValidator


@click.command(help="Validate canonical config files without applying.")
@workspace_option()
@click.pass_obj
def validate(obj: dict[str, str], workspace: str | None) -> None:
    core = CoreRepository()
    validator = ConfigValidator()

    if workspace is not None:
        result = validator.validate_workspace_root(
            workspace_config_root(core, workspace)
        )
    else:
        result = validator.validate_core_root(core.root)

    if result.issues:
        for issue in result.issues:
            click.echo(f"{issue.path}: {issue.message}")
        raise click.exceptions.Exit(1)

    click.echo(f"Validated {result.validated} resources.")
