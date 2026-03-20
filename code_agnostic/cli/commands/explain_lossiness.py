"""Explain-lossiness command."""

import click

from code_agnostic.cli.helpers import workspace_config_root
from code_agnostic.cli.options import app_option, workspace_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.lossiness import LossinessExplainer


@click.command(help="Explain documented lossy mappings without applying.")
@app_option()
@workspace_option()
@click.pass_obj
def explain_lossiness(obj: dict[str, str], app: str, workspace: str | None) -> None:
    target = app or "all"
    core = CoreRepository()
    explainer = LossinessExplainer()

    if workspace is not None:
        findings = explainer.explain_workspace_root(
            workspace_config_root(core, workspace),
            workspace=workspace,
            app=target,
        )
    else:
        findings = explainer.explain_core_root(core.root, app=target)

    if not findings:
        click.echo("No lossy mappings found.")
        return

    click.echo("resource_path\tapp\tproperty\tstatus\treason")
    for finding in findings:
        click.echo(
            "\t".join(
                [
                    finding.resource_path,
                    finding.app,
                    finding.property,
                    finding.status,
                    finding.reason,
                ]
            )
        )
