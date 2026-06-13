"""Skills group commands."""

from pathlib import Path
import shutil

import click
from rich.console import Console

from code_agnostic.cli.helpers import validate_resource_name, workspace_config_root
from code_agnostic.cli.options import workspace_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.errors import SyncAppError
from code_agnostic.skills.install_sources import (
    SkillInstallSourceError,
    cleanup_skill_install_resolution,
    resolve_skill_install_source,
)
from code_agnostic.tui import SyncConsoleUI
from code_agnostic.utils import compact_home_path


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


def _preflight_skill_destinations(
    source_dirs: tuple[Path, ...], root: Path, scope: str
) -> list[tuple[str, Path, Path]]:
    installs: list[tuple[str, Path, Path]] = []
    names = _validate_skill_source_names(source_dirs)
    for name, source_dir in zip(names, source_dirs, strict=True):
        destination = root / "skills" / name
        if destination.exists():
            raise click.ClickException(f"Skill already exists: {scope}:{name}")
        installs.append((name, source_dir, destination))
    return installs


def _validate_skill_source_names(source_dirs: tuple[Path, ...]) -> list[str]:
    names: list[str] = []
    seen_names: set[str] = set()
    for source_dir in source_dirs:
        name = source_dir.name
        validate_resource_name(name, "skill")
        if name in seen_names:
            raise click.ClickException(f"Duplicate skill name in source: {name}")
        seen_names.add(name)
        names.append(name)
    return names


@click.group(
    help=(
        "Manage source skill definitions across global, workspace, and project scopes."
    )
)
def skills() -> None:
    pass


@skills.command("install", help="Install a skill source into managed source config.")
@click.argument("source")
@click.option(
    "--skill",
    "skill_selectors",
    multiple=True,
    help="Select a skill by name or source path; repeat to install multiple.",
)
@click.option("--global", "global_scope", is_flag=True, help="Install globally.")
@workspace_option()
@click.option("--project", help="Install into a registered project source.")
@click.pass_obj
def skills_install(
    obj: dict[str, str],
    source: str,
    skill_selectors: tuple[str, ...],
    global_scope: bool,
    workspace: str | None,
    project: str | None,
) -> None:
    resolution = None
    source_path = Path(source).expanduser()
    if source_path.exists():
        try:
            resolution = resolve_skill_install_source(
                source,
                skill_selectors=skill_selectors,
            )
            _validate_skill_source_names(resolution.skill_dirs)
        except SkillInstallSourceError as exc:
            raise click.ClickException(str(exc)) from exc

    core = CoreRepository()
    root, scope, scope_note = _install_root(
        core,
        global_scope=global_scope,
        workspace=workspace,
        project=project,
    )
    try:
        if resolution is None:
            resolution = resolve_skill_install_source(
                source,
                skill_selectors=skill_selectors,
            )
        installs = _preflight_skill_destinations(resolution.skill_dirs, root, scope)
        for _name, _source_dir, destination in installs:
            destination.parent.mkdir(parents=True, exist_ok=True)
        installed = False
        for name, source_dir, destination in installs:
            shutil.copytree(source_dir, destination)
            installed = True
            if scope_note is not None:
                click.echo(scope_note)
                scope_note = None
            click.echo(f"Installed {scope} skill: {name}")
            click.echo(f"Source: {compact_home_path(source_dir)}")
            click.echo(f"Destination: {compact_home_path(destination)}")
        if installed:
            click.echo("Next:")
            click.echo("  code-agnostic plan")
            click.echo("  code-agnostic apply")
    except SkillInstallSourceError as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        if resolution is not None:
            cleanup_skill_install_resolution(resolution)


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
    install_scope = f"--workspace {workspace}" if workspace else "--global"
    empty_message = (
        f"{scope_message} in {skill_dir}.\n"
        f"- code-agnostic skills install <source> {install_scope}\n"
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
