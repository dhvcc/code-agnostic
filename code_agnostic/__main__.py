from pathlib import Path
from collections.abc import Callable

import click
from rich.console import Console

from code_agnostic.apps.app_id import app_ids_by_capability
from code_agnostic.apps.apps_service import AppsService
from code_agnostic.apps.common.framework import list_registered_app_services
from code_agnostic.constants import AGENTS_FILENAME, CLAUDE_FILENAME
from code_agnostic.core.repository import CoreRepository
from code_agnostic.imports.models import ConflictPolicy, ImportSection
from code_agnostic.imports.service import ImportService
from code_agnostic.models import ActionStatus, EditorStatusRow, EditorSyncStatus
from code_agnostic.status import StatusService
from code_agnostic.tui import SyncConsoleUI
from code_agnostic.workspaces import WorkspaceService


def _target_values() -> list[str]:
    registered = set(list_registered_app_services())
    targetable = set(app_ids_by_capability(targetable=True))
    return [
        "all",
        *[
            app.value
            for app in sorted(registered & targetable, key=lambda item: item.value)
        ],
    ]


def _manageable_app_values() -> list[str]:
    registered = set(list_registered_app_services())
    manageable = set(app_ids_by_capability(toggleable=True))
    return [
        app.value
        for app in sorted(registered & manageable, key=lambda item: item.value)
    ]


def _import_source_values() -> list[str]:
    registered = set(list_registered_app_services())
    importable = set(app_ids_by_capability(importable=True))
    return [
        app.value
        for app in sorted(registered & importable, key=lambda item: item.value)
    ]


def _target_argument(default: str = "all") -> Callable:
    return click.argument(
        "target",
        required=False,
        type=click.Choice(_target_values(), case_sensitive=False),
        default=default,
    )


def _status_row_for_app(app_name: str, plan, apps: AppsService) -> EditorStatusRow:
    if not apps.is_enabled(app_name):
        return EditorStatusRow(
            name=app_name,
            status=EditorSyncStatus.DISABLED,
            detail="disabled by apps config",
        )

    relevant = [action for action in plan.actions if action.app == app_name]

    for error in plan.errors:
        if app_name in str(error).lower():
            return EditorStatusRow(
                name=app_name,
                status=EditorSyncStatus.ERROR,
                detail=f"cannot evaluate ({error})",
            )

    synced = (
        all(action.status == ActionStatus.NOOP for action in relevant)
        if relevant
        else True
    )
    return EditorStatusRow(
        name=app_name,
        status=EditorSyncStatus.SYNCED if synced else EditorSyncStatus.DRIFT,
        detail="in sync" if synced else "out of sync",
    )


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(ctx: click.Context) -> None:
    """App-based config sync."""
    ctx.obj = {}


@cli.command(help="Build and print a dry-run plan.")
@_target_argument()
@click.option("-v", "--verbose", is_flag=True, default=False)
@click.pass_obj
def plan(obj: dict[str, str], target: str, verbose: bool) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    apps = AppsService(core)

    try:
        scoped_plan = apps.plan_for_target(target)
    except Exception as exc:
        raise click.ClickException(f"Fatal: {exc}")

    ui.render_plan(scoped_plan, mode=f"plan:{target.lower()}", verbose=verbose)

    if scoped_plan.errors:
        raise click.exceptions.Exit(1)


@cli.command(help="Apply planned sync changes.")
@_target_argument()
@click.option("-v", "--verbose", is_flag=True, default=False)
@click.pass_obj
def apply(obj: dict[str, str], target: str, verbose: bool) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    apps = AppsService(core)

    try:
        scoped_plan = apps.plan_for_target(target)
    except Exception as exc:
        raise click.ClickException(f"Fatal: {exc}")

    ui.render_plan(scoped_plan, mode=f"apply:{target.lower()}", verbose=verbose)

    if not scoped_plan.actions and not scoped_plan.errors:
        ui.render_apply_result(applied=0, failed=0, failures=[])
        return

    if scoped_plan.errors:
        raise click.ClickException(
            "Apply aborted due to planning/parsing errors above."
        )

    applied, failed, failures = apps.execute_plan(scoped_plan)
    ui.render_apply_result(applied, failed, failures)

    if failed:
        raise click.exceptions.Exit(1)


@cli.command(help="Show sync status for editors and workspaces.")
@_target_argument()
@click.pass_obj
def status(obj: dict[str, str], target: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    apps = AppsService(core)

    try:
        plan_result = apps.plan_for_target("all")
        editor_rows = [
            _status_row_for_app(app_name, plan_result, apps)
            for app_name in apps.available_apps()
        ]
    except Exception as exc:
        editor_rows = [
            EditorStatusRow(
                name=app_name,
                status=EditorSyncStatus.ERROR,
                detail=f"cannot evaluate ({exc})",
            )
            for app_name in apps.available_apps()
        ]

    normalized_target = target.lower()
    if normalized_target != "all":
        editor_rows = [row for row in editor_rows if row.name == normalized_target]

    status_service = StatusService()
    enabled_services = apps._resolve_services_for_target("all")
    ui.render_status(
        editor_rows,
        status_service.build_workspace_status(core, app_services=enabled_services),
    )


@cli.group(help="Enable or disable app sync targets.")
def apps() -> None:
    pass


@apps.command("list", help="List app sync target status.")
@click.pass_obj
def apps_list(obj: dict[str, str]) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = AppsService(core)
    ui.render_apps(service.list_status_rows())


@apps.command("enable", help="Enable app sync target.")
@click.argument(
    "name", type=click.Choice(_manageable_app_values(), case_sensitive=False)
)
@click.pass_obj
def apps_enable(obj: dict[str, str], name: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = AppsService(core)
    service.enable(name.lower())
    ui.render_apps(service.list_status_rows())


@apps.command("disable", help="Disable app sync target.")
@click.argument(
    "name", type=click.Choice(_manageable_app_values(), case_sensitive=False)
)
@click.pass_obj
def apps_disable(obj: dict[str, str], name: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = AppsService(core)
    service.disable(name.lower())
    ui.render_apps(service.list_status_rows())


@cli.group(help="Manage workspace roots for repo rule propagation.")
def workspaces() -> None:
    pass


@workspaces.command("add", help="Add a workspace by name and path.")
@click.argument("name")
@click.argument("path", type=click.Path(path_type=Path))
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
@click.argument("name")
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
    from code_agnostic.core.workspace_repository import WorkspaceConfigRepository

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


def _ensure_exclude_entries(path: Path, entries: list[str]) -> tuple[int, bool]:
    existing_lines: list[str] = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8").splitlines()

    seen = set(existing_lines)
    additions = [entry for entry in entries if entry not in seen]
    if not additions:
        return 0, False

    merged = list(existing_lines)
    if merged and merged[-1] != "":
        merged.append("")
    merged.extend(additions)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(merged) + "\n", encoding="utf-8")
    return len(additions), True


@workspaces.command(
    "git-exclude",
    help="Add managed sync paths to each repo's .git/info/exclude.",
)
@click.option("--workspace", "workspace_name", default=None)
@click.pass_obj
def workspaces_git_exclude(obj: dict[str, str], workspace_name: str | None) -> None:
    core = CoreRepository()
    apps = AppsService(core)
    workspace_service = WorkspaceService()

    enabled_apps = apps.enabled_apps()
    app_entries = [f".{app_name}" for app_name in enabled_apps]
    base_entries = [AGENTS_FILENAME, CLAUDE_FILENAME]
    entries = app_entries + base_entries

    workspaces = core.load_workspaces()
    if workspace_name is not None:
        workspaces = [item for item in workspaces if item["name"] == workspace_name]
        if not workspaces:
            raise click.ClickException(f"Workspace not found: {workspace_name}")

    processed = 0
    touched = 0
    added_lines = 0

    for item in workspaces:
        workspace_path = Path(item["path"])
        if not workspace_path.exists() or not workspace_path.is_dir():
            continue
        repos = workspace_service.discover_git_repos(workspace_path)
        for repo in repos:
            exclude_path = repo / ".git" / "info" / "exclude"
            added, changed = _ensure_exclude_entries(exclude_path, entries)
            processed += 1
            if changed:
                touched += 1
                added_lines += added

    click.echo(
        f"Updated git excludes: repos={processed}, changed={touched}, lines_added={added_lines}"
    )


@cli.group(name="import", help="Import existing app config into hub.")
def import_group() -> None:
    pass


def _parse_import_sections(items: tuple[str, ...]) -> list[ImportSection] | None:
    if not items:
        return None
    return [ImportSection(item.lower()) for item in items]


@import_group.command("plan", help="Plan import from source app into hub.")
@click.argument(
    "source_app",
    type=click.Choice(_import_source_values()),
)
@click.option(
    "--include",
    "includes",
    type=click.Choice([item.value for item in ImportSection]),
    multiple=True,
    help="Repeatable section include (mcp, skills, agents).",
)
@click.option(
    "--exclude",
    "excludes",
    type=click.Choice([item.value for item in ImportSection]),
    multiple=True,
    help="Repeatable section exclude (mcp, skills, agents).",
)
@click.option(
    "--on-conflict",
    type=click.Choice([item.value for item in ConflictPolicy]),
    default=ConflictPolicy.SKIP.value,
    show_default=True,
)
@click.option("--source-root", type=click.Path(path_type=Path))
@click.option("--follow-symlinks", is_flag=True, default=False)
@click.option("-v", "--verbose", is_flag=True, default=False)
@click.pass_obj
def import_plan(
    obj: dict[str, str],
    source_app: str,
    includes: tuple[str, ...],
    excludes: tuple[str, ...],
    on_conflict: str,
    source_root: Path | None,
    follow_symlinks: bool,
    verbose: bool,
) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = ImportService(core)

    plan = service.plan(
        source_app=source_app,
        include=_parse_import_sections(includes),
        exclude=_parse_import_sections(excludes),
        conflict_policy=ConflictPolicy(on_conflict),
        source_root=source_root,
        follow_symlinks=follow_symlinks,
    )
    ui.render_import_plan(
        plan,
        mode=f"import:plan:{source_app.lower()}",
        verbose=verbose,
    )

    if plan.errors:
        raise click.exceptions.Exit(1)


@import_group.command("apply", help="Apply import from source app into hub.")
@click.argument(
    "source_app",
    type=click.Choice(_import_source_values()),
)
@click.option(
    "--include",
    "includes",
    type=click.Choice([item.value for item in ImportSection]),
    multiple=True,
    help="Repeatable section include (mcp, skills, agents).",
)
@click.option(
    "--exclude",
    "excludes",
    type=click.Choice([item.value for item in ImportSection]),
    multiple=True,
    help="Repeatable section exclude (mcp, skills, agents).",
)
@click.option(
    "--on-conflict",
    type=click.Choice([item.value for item in ConflictPolicy]),
    default=ConflictPolicy.SKIP.value,
    show_default=True,
)
@click.option("--source-root", type=click.Path(path_type=Path))
@click.option("--follow-symlinks", is_flag=True, default=False)
@click.option("-v", "--verbose", is_flag=True, default=False)
@click.pass_obj
def import_apply(
    obj: dict[str, str],
    source_app: str,
    includes: tuple[str, ...],
    excludes: tuple[str, ...],
    on_conflict: str,
    source_root: Path | None,
    follow_symlinks: bool,
    verbose: bool,
) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = ImportService(core)

    plan = service.plan(
        source_app=source_app,
        include=_parse_import_sections(includes),
        exclude=_parse_import_sections(excludes),
        conflict_policy=ConflictPolicy(on_conflict),
        source_root=source_root,
        follow_symlinks=follow_symlinks,
    )
    ui.render_import_plan(
        plan,
        mode=f"import:apply:{source_app.lower()}",
        verbose=verbose,
    )

    if plan.errors:
        raise click.ClickException("Import aborted due to conflicts/errors above.")

    result = service.apply(plan)
    ui.render_import_apply_result(result)

    if result.failed:
        raise click.exceptions.Exit(1)


def main() -> int:
    try:
        cli(standalone_mode=False)
    except click.exceptions.Exit as exc:
        code = exc.exit_code
        return code if isinstance(code, int) else 1
    except click.ClickException as exc:
        exc.show()
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
