"""Restore command."""

import click

from code_agnostic.cli.helpers import require_workspace_entry
from code_agnostic.cli.options import workspace_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.executor import SyncExecutor


@click.command(
    help="Restore the active synced revision for the global root or a workspace."
)
@workspace_option()
@click.pass_obj
def restore(obj: dict[str, str], workspace: str | None) -> None:
    core = CoreRepository()

    if workspace is not None:
        require_workspace_entry(core, workspace)

    executor = SyncExecutor(core=core)
    try:
        result = executor.restore_active_revision(workspace=workspace)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc))

    click.echo(f"Restored revision {result.revision_id} ({result.restored} targets).")
