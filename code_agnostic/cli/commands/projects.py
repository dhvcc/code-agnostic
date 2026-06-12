"""Projects group commands."""

from pathlib import Path

import click

from code_agnostic.core.project_repository import ProjectConfigRepository
from code_agnostic.core.repository import CoreRepository
from code_agnostic.errors import SyncAppError


@click.group(help="Manage project roots for project-local source config.")
def projects() -> None:
    pass


@projects.command("add", help="Add a project by name and path.")
@click.option("--name", required=True, help="Project name.")
@click.option(
    "--path",
    required=True,
    type=click.Path(path_type=Path),
    help="Project root path.",
)
@click.pass_obj
def projects_add(obj: dict[str, str], name: str, path: Path) -> None:
    core = CoreRepository()
    try:
        core.add_project(name, path)
    except (ValueError, SyncAppError) as exc:
        raise click.ClickException(str(exc))
    click.echo(f"Project added: {name.strip()}")
    click.echo(str(path.expanduser().resolve()))


@projects.command("remove", help="Unregister a project by name.")
@click.option("--name", required=True, help="Project name to unregister.")
@click.pass_obj
def projects_remove(obj: dict[str, str], name: str) -> None:
    core = CoreRepository()
    try:
        removed = core.remove_project(name)
    except SyncAppError as exc:
        raise click.ClickException(str(exc))
    if not removed:
        raise click.ClickException(f"Project not found: {name}")
    click.echo(f"Project unregistered: {name}")


@projects.command("list", help="List configured projects.")
@click.pass_obj
def projects_list(obj: dict[str, str]) -> None:
    core = CoreRepository()
    try:
        items = core.load_projects()
    except SyncAppError as exc:
        raise click.ClickException(str(exc))

    if not items:
        click.echo("No projects configured.")
        click.echo("code-agnostic projects add --name <name> --path <path>")
        return

    for item in items:
        project_source = ProjectConfigRepository(
            root=core.project_config_dir(item["name"])
        )
        markers = []
        if project_source.has_mcp():
            markers.append("mcp")
        if project_source.has_rules():
            markers.append("rules")
        if project_source.has_skills():
            markers.append("skills")
        if project_source.has_agents():
            markers.append("agents")
        suffix = f" [{', '.join(markers)}]" if markers else ""
        click.echo(f"{item['name']}: {item['path']}{suffix}")
