"""Skills group commands."""

from pathlib import Path
import shutil

import click
from rich.console import Console

from code_agnostic.cli.helpers import validate_resource_name, workspace_config_root
from code_agnostic.cli.options import workspace_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.errors import SyncAppError
from code_agnostic.tui import SyncConsoleUI
from code_agnostic.utils import compact_home_path


def _is_skill_source(path: Path) -> bool:
    return path.is_dir() and (
        (path / "SKILL.md").exists()
        or ((path / "meta.yaml").exists() and (path / "prompt.md").exists())
    )


def _entries_containing_cwd(
    entries: list[dict[str, str]], cwd: Path
) -> list[dict[str, str]]:
    matches = []
    for entry in entries:
        root = Path(entry["path"]).expanduser().resolve()
        if cwd == root or cwd.is_relative_to(root):
            matches.append(entry)
    return matches


def _project_entries_by_name(core: CoreRepository) -> dict[str, dict[str, str]]:
    return {item["name"]: item for item in core.load_projects()}


def _install_root(
    core: CoreRepository,
    *,
    global_scope: bool,
    workspace: str | None,
    project: str | None,
) -> tuple[Path, str, str | None]:
    explicit_count = sum(
        [global_scope, workspace is not None, project is not None],
    )
    if explicit_count > 1:
        raise click.ClickException(
            "Choose only one scope: --global, --workspace, or --project."
        )

    try:
        if global_scope:
            return core.root, "global", None
        if workspace is not None:
            return (
                workspace_config_root(core, workspace),
                f"workspace:{workspace}",
                None,
            )
        if project is not None:
            projects = _project_entries_by_name(core)
            if project not in projects:
                raise click.ClickException(f"Project not found: {project}")
            return core.project_config_dir(project), f"project:{project}", None

        cwd = Path.cwd().resolve()
        project_matches = _entries_containing_cwd(core.load_projects(), cwd)
        if len(project_matches) == 1:
            name = project_matches[0]["name"]
            return core.project_config_dir(name), f"project:{name}", None

        workspace_matches = _entries_containing_cwd(core.load_workspaces(), cwd)
        if len(project_matches) == 0 and len(workspace_matches) == 1:
            name = workspace_matches[0]["name"]
            return core.workspace_config_dir(name), f"workspace:{name}", None
    except SyncAppError as exc:
        raise click.ClickException(str(exc)) from exc

    raise click.ClickException(
        "No unique project/workspace scope detected. Use --global, --project, "
        "or --workspace."
    )


@click.group(
    help=(
        "Manage source skill definitions. Commands use global source by default; "
        "pass -w/--workspace for workspace source."
    )
)
def skills() -> None:
    pass


@skills.command("install", help="Install a local skill directory into source config.")
@click.argument("source", type=click.Path(path_type=Path))
@click.option("--global", "global_scope", is_flag=True, help="Install globally.")
@workspace_option()
@click.option("--project", help="Install into a registered project source.")
@click.pass_obj
def skills_install(
    obj: dict[str, str],
    source: Path,
    global_scope: bool,
    workspace: str | None,
    project: str | None,
) -> None:
    source = source.expanduser().resolve()
    if not _is_skill_source(source):
        raise click.ClickException(
            "Invalid skill source: expected a directory containing SKILL.md "
            "or meta.yaml and prompt.md."
        )

    name = source.name
    validate_resource_name(name, "skill")

    core = CoreRepository()
    root, scope, scope_note = _install_root(
        core,
        global_scope=global_scope,
        workspace=workspace,
        project=project,
    )
    destination = root / "skills" / name
    if destination.exists():
        raise click.ClickException(f"Skill already exists: {scope}:{name}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    if scope_note is not None:
        click.echo(scope_note)
    click.echo(f"Installed {scope} skill: {name}")
    click.echo(f"Source: {compact_home_path(source)}")
    click.echo(f"Destination: {compact_home_path(destination)}")


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
    skill_dir = compact_home_path(root / "skills")
    scope_message = (
        f"No workspace skills configured for {workspace}"
        if workspace
        else "No global skills configured"
    )
    empty_message = (
        f"{scope_message} in {skill_dir}.\n"
        f"- Copy a skill into {skill_dir}/<name>\n"
        "- code-agnostic plan\n"
        "- code-agnostic apply"
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
    validate_resource_name(name, "skill")
    core = CoreRepository()
    root = workspace_config_root(core, workspace)
    skill_dir = root / "skills" / name
    if not skill_dir.exists():
        raise click.ClickException(f"Skill not found: {name}")
    shutil.rmtree(skill_dir)
    scope = f"workspace:{workspace}" if workspace else "global"
    click.echo(f"Removed {scope} skill: {name}")
