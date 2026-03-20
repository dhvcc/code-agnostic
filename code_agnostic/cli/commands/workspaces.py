"""Workspaces group commands."""

from pathlib import Path

import click
from rich.console import Console

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.cli.helpers import ensure_exclude_entries, require_workspace_entry
from code_agnostic.cli.options import workspace_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.git_exclude_service import GitExcludeService
from code_agnostic.tui import SyncConsoleUI
from code_agnostic.workspaces import WorkspaceService


@click.group(help="Manage workspace roots for repo rule propagation.")
def workspaces() -> None:
    pass


@workspaces.command("add", help="Add a workspace by name and path.")
@click.option("--name", required=True, help="Workspace name.")
@click.option(
    "--path",
    required=True,
    type=click.Path(path_type=Path),
    help="Workspace root path.",
)
@click.pass_obj
def workspaces_add(obj: dict[str, str], name: str, path: Path) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    try:
        core.add_workspace(name, path)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    ui.render_workspace_saved(name, str(path.expanduser().resolve()))


@workspaces.command("remove", help="Remove a workspace from config by name.")
@click.option("--name", required=True, help="Workspace name to remove.")
@click.pass_obj
def workspaces_remove(obj: dict[str, str], name: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    existing = {item["name"]: item["path"] for item in core.load_workspaces()}
    removed = core.remove_workspace(name)
    if not removed:
        raise click.ClickException(f"Workspace not found: {name}")
    ui.render_workspace_saved(name, existing.get(name, ""), removed=True)


@workspaces.command("list", help="List configured workspaces and detected repos.")
@click.pass_obj
def workspaces_list(obj: dict[str, str]) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    workspace_service = WorkspaceService()

    overview: list[dict] = []
    for item in core.load_workspaces():
        workspace_path = Path(item["path"])
        repos: list[str] = []
        if workspace_path.exists() and workspace_path.is_dir():
            repos = [
                str(path.relative_to(workspace_path))
                for path in workspace_service.discover_git_repos(workspace_path)
            ]
        ws_source = WorkspaceConfigRepository(
            root=core.workspace_config_dir(item["name"])
        )
        overview.append(
            {
                "name": item["name"],
                "path": item["path"],
                "repos": repos,
                "has_mcp": ws_source.has_mcp(),
                "has_rules": ws_source.has_rules(),
                "has_skills": ws_source.has_skills(),
                "has_agents": ws_source.has_agents(),
            }
        )

    ui.render_workspaces_overview(overview)


@workspaces.command(
    "git-exclude",
    help="Add managed sync paths to each repo's .git/info/exclude.",
)
@workspace_option()
@click.pass_obj
def workspaces_git_exclude(obj: dict[str, str], workspace: str | None) -> None:
    core = CoreRepository()
    apps = AppsService(core)
    workspace_service = WorkspaceService()
    exclude_service = GitExcludeService(core)

    enabled_apps = apps.enabled_apps()

    ws_list = (
        [require_workspace_entry(core, workspace)]
        if workspace is not None
        else core.load_workspaces()
    )

    processed = 0
    touched = 0
    added_lines = 0

    for item in ws_list:
        workspace_path = Path(item["path"])
        if not workspace_path.exists() or not workspace_path.is_dir():
            continue
        entries = exclude_service.compute_entries(item["name"], enabled_apps)
        repos = workspace_service.discover_git_repos(workspace_path)
        for repo in repos:
            git_dir = workspace_service.resolve_git_dir(repo)
            if git_dir is None:
                continue
            exclude_path = git_dir / "info" / "exclude"
            added, changed = ensure_exclude_entries(exclude_path, entries)
            processed += 1
            if changed:
                touched += 1
                added_lines += added

    click.echo(
        f"Updated git excludes: repos={processed}, changed={touched}, lines_added={added_lines}"
    )


@workspaces.command(
    "exclude-add", help="Add a custom git-exclude pattern to a workspace."
)
@click.option("--pattern", required=True, help="Pattern to add.")
@workspace_option(required=True)
@click.pass_obj
def workspaces_exclude_add(obj: dict[str, str], pattern: str, workspace: str) -> None:
    core = CoreRepository()
    service = GitExcludeService(core)
    try:
        service.add_pattern(workspace, pattern)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"Added pattern: {pattern}")


@workspaces.command(
    "exclude-remove", help="Remove a custom git-exclude pattern from a workspace."
)
@click.option("--pattern", required=True, help="Pattern to remove.")
@workspace_option(required=True)
@click.pass_obj
def workspaces_exclude_remove(
    obj: dict[str, str], pattern: str, workspace: str
) -> None:
    core = CoreRepository()
    service = GitExcludeService(core)
    try:
        removed = service.remove_pattern(workspace, pattern)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    if not removed:
        raise click.ClickException(f"Pattern not found: {pattern}")
    click.echo(f"Removed pattern: {pattern}")


@workspaces.command("exclude-list", help="List git-exclude config for a workspace.")
@workspace_option(required=True)
@click.pass_obj
def workspaces_exclude_list(obj: dict[str, str], workspace: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = GitExcludeService(core)
    try:
        config = service.list_patterns(workspace)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    ui.render_exclude_config(
        workspace=workspace,
        include_defaults=config.get("include_defaults", True),
        extra_patterns=config.get("extra_patterns", []),
    )
