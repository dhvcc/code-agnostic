"""Skills group commands."""

import shutil

import click
from rich.console import Console

from code_agnostic.cli.helpers import workspace_config_root
from code_agnostic.cli.options import workspace_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.tui import SyncConsoleUI
from code_agnostic.utils import compact_home_path


@click.group(
    help=(
        "Manage source skill definitions. Commands use global source by default; "
        "pass -w/--workspace for workspace source. Repo-local skill folders are "
        "unmanaged until project-scoped installs are supported."
    )
)
def skills() -> None:
    pass


@skills.command("list", help="List global skills, or workspace skills with -w.")
@workspace_option()
@click.pass_obj
def skills_list(obj: dict[str, str], workspace: str | None) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    root = workspace_config_root(core, workspace)
    skill_sources = CoreRepository(root).list_skill_sources()
    scope = f"workspace:{workspace}" if workspace else "global"
    rows = [
        [
            source.name,
            scope,
            "bundle" if (source / "meta.yaml").exists() else "legacy",
            compact_home_path(source),
        ]
        for source in skill_sources
    ]
    empty_message = (
        f"No workspace skills configured for {workspace} in "
        f"{compact_home_path(root / 'skills')}."
        if workspace
        else f"No global skills configured in {compact_home_path(root / 'skills')}."
    )
    ui.render_list(
        "skills",
        ["Skill", "Scope", "Format", "Source"],
        rows,
        empty_message,
    )


@skills.command("remove", help="Remove a global skill, or a workspace skill with -w.")
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
    scope = f"workspace:{workspace}" if workspace else "global"
    click.echo(f"Removed {scope} skill: {name}")
