"""Skills group commands."""

import shutil

import click
from rich.console import Console

from code_agnostic.cli.helpers import workspace_config_root
from code_agnostic.cli.options import workspace_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.tui import SyncConsoleUI


@click.group(help="Manage skill definitions in the hub config.")
def skills() -> None:
    pass


@skills.command("list", help="List configured skills.")
@workspace_option()
@click.pass_obj
def skills_list(obj: dict[str, str], workspace: str | None) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    root = workspace_config_root(core, workspace)
    skill_sources = CoreRepository(root).list_skill_sources()
    rows = [[source.name] for source in skill_sources]
    ui.render_list("skills", ["Skill"], rows, "No skills configured.")


@skills.command("remove", help="Remove a skill by name.")
@click.option("--name", required=True, help="Skill name to remove.")
@workspace_option()
@click.pass_obj
def skills_remove(obj: dict[str, str], name: str, workspace: str | None) -> None:
    core = CoreRepository()
    root = workspace_config_root(core, workspace)
    skill_dir = root / "skills" / name
    if not skill_dir.exists():
        raise click.ClickException(f"Skill not found: {name}")
    shutil.rmtree(skill_dir)
    click.echo(f"Removed: {name}")
