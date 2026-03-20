"""Rules group commands."""

import click
from rich.console import Console

from code_agnostic.cli.helpers import workspace_config_root
from code_agnostic.cli.options import workspace_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.rules.repository import RulesRepository
from code_agnostic.tui import SyncConsoleUI


@click.group(help="Manage rule definitions in the hub config.")
def rules() -> None:
    pass


@rules.command("list", help="List configured rules.")
@workspace_option()
@click.pass_obj
def rules_list(obj: dict[str, str], workspace: str | None) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    root = workspace_config_root(core, workspace)

    repo = RulesRepository(root)
    rule_list = repo.list_rules()
    rows = [
        [rule.name, rule.metadata.description or "(no description)"]
        for rule in rule_list
    ]
    ui.render_list("rules", ["Rule", "Description"], rows, "No rules configured.")


@rules.command("remove", help="Remove a rule by name.")
@click.option("--name", required=True, help="Rule name to remove.")
@workspace_option()
@click.pass_obj
def rules_remove(obj: dict[str, str], name: str, workspace: str | None) -> None:
    core = CoreRepository()
    root = workspace_config_root(core, workspace)

    repo = RulesRepository(root)
    if not repo.remove_rule(name):
        raise click.ClickException(f"Rule not found: {name}")
    click.echo(f"Removed: {name}")
