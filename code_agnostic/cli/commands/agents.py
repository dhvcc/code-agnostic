"""Agents group commands."""

import shutil

import click
from rich.console import Console

from code_agnostic.cli.helpers import workspace_config_root
from code_agnostic.cli.options import workspace_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.tui import SyncConsoleUI


@click.group(name="agents", help="Manage agent definitions in the hub config.")
def agents_group() -> None:
    pass


@agents_group.command("list", help="List configured agents.")
@workspace_option()
@click.pass_obj
def agents_list(obj: dict[str, str], workspace: str | None) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    root = workspace_config_root(core, workspace)
    agent_files = CoreRepository(root).list_agent_sources()
    rows = [[f.stem if f.is_file() else f.name] for f in agent_files]
    ui.render_list("agents", ["Agent"], rows, "No agents configured.")


@agents_group.command("remove", help="Remove an agent by name.")
@click.option("--name", required=True, help="Agent name to remove.")
@workspace_option()
@click.pass_obj
def agents_remove(obj: dict[str, str], name: str, workspace: str | None) -> None:
    core = CoreRepository()
    root = workspace_config_root(core, workspace)
    agent_dir = root / "agents" / name
    if agent_dir.is_dir():
        shutil.rmtree(agent_dir)
        click.echo(f"Removed: {name}")
        return
    agent_path = root / "agents" / f"{name}.md"
    if not agent_path.exists():
        raise click.ClickException(f"Agent not found: {name}")
    agent_path.unlink()
    click.echo(f"Removed: {name}")
