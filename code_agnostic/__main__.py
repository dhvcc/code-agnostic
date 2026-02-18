from pathlib import Path
from collections.abc import Callable

import click
from rich.console import Console

from code_agnostic.apps.app_id import app_ids_by_capability
from code_agnostic.apps.apps_service import AppsService
from code_agnostic.apps.common.framework import list_registered_app_services
from code_agnostic.core.repository import CoreRepository
from code_agnostic.imports.models import ConflictPolicy, ImportSection
from code_agnostic.imports.service import ImportService
from code_agnostic.mcp_service import MCPManagementService
from code_agnostic.models import ActionStatus, EditorStatusRow, EditorSyncStatus
from code_agnostic.status import StatusService
from code_agnostic.tui import SyncConsoleUI
from code_agnostic.workspaces import WorkspaceService


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Shared option / argument decorators
# ---------------------------------------------------------------------------


def app_option(required: bool = False) -> Callable:
    return click.option(
        "-a",
        "--app",
        required=required,
        type=click.Choice(_target_values(), case_sensitive=False),
        default="all" if not required else None,
        help="Target app (default: all).",
    )


def manageable_app_option(required: bool = True) -> Callable:
    return click.option(
        "-a",
        "--app",
        required=required,
        type=click.Choice(_manageable_app_values(), case_sensitive=False),
        help="App to manage.",
    )


def import_app_option(required: bool = True) -> Callable:
    return click.option(
        "-a",
        "--app",
        required=required,
        type=click.Choice(_import_source_values(), case_sensitive=False),
        help="Source app to import from.",
    )


def workspace_option(required: bool = False) -> Callable:
    return click.option(
        "-w",
        "--workspace",
        required=required,
        default=None,
        help="Workspace name.",
    )


def verbose_option() -> Callable:
    return click.option("-v", "--verbose", is_flag=True, default=False)


# ---------------------------------------------------------------------------
# Status helper
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# AliasedGroup for singular/plural aliases
# ---------------------------------------------------------------------------


class AliasedGroup(click.Group):
    ALIASES: dict[str, str] = {
        "app": "apps",
        "workspace": "workspaces",
    }

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        return super().get_command(ctx, self.ALIASES.get(cmd_name, cmd_name))

    def resolve_command(self, ctx: click.Context, args: list[str]):
        if args and args[0] in self.ALIASES:
            args[0] = self.ALIASES[args[0]]
        return super().resolve_command(ctx, args)


# ---------------------------------------------------------------------------
# Root CLI
# ---------------------------------------------------------------------------


@click.group(
    cls=AliasedGroup,
    context_settings={"help_option_names": ["-h", "--help"]},
)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """App-based config sync."""
    ctx.obj = {}


# ---------------------------------------------------------------------------
# plan / apply / status
# ---------------------------------------------------------------------------


@cli.command(help="Build and print a dry-run plan.")
@app_option()
@verbose_option()
@click.pass_obj
def plan(obj: dict[str, str], app: str, verbose: bool) -> None:
    target = app or "all"
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
@app_option()
@verbose_option()
@click.pass_obj
def apply(obj: dict[str, str], app: str, verbose: bool) -> None:
    target = app or "all"
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
@app_option()
@verbose_option()
@click.pass_obj
def status(obj: dict[str, str], app: str, verbose: bool) -> None:
    target = app or "all"
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


# ---------------------------------------------------------------------------
# apps group
# ---------------------------------------------------------------------------


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
@manageable_app_option()
@click.pass_obj
def apps_enable(obj: dict[str, str], app: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = AppsService(core)
    service.enable(app.lower())
    ui.render_apps(service.list_status_rows())


@apps.command("disable", help="Disable app sync target.")
@manageable_app_option()
@click.pass_obj
def apps_disable(obj: dict[str, str], app: str) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = AppsService(core)
    service.disable(app.lower())
    ui.render_apps(service.list_status_rows())


# ---------------------------------------------------------------------------
# workspaces group
# ---------------------------------------------------------------------------


@cli.group(help="Manage workspace roots for repo rule propagation.")
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
@workspace_option()
@click.pass_obj
def workspaces_git_exclude(obj: dict[str, str], workspace: str | None) -> None:
    from code_agnostic.git_exclude_service import GitExcludeService

    core = CoreRepository()
    apps = AppsService(core)
    workspace_service = WorkspaceService()
    exclude_service = GitExcludeService(core)

    enabled_apps = apps.enabled_apps()

    ws_list = core.load_workspaces()
    if workspace is not None:
        ws_list = [item for item in ws_list if item["name"] == workspace]
        if not ws_list:
            raise click.ClickException(f"Workspace not found: {workspace}")

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
            exclude_path = repo / ".git" / "info" / "exclude"
            added, changed = _ensure_exclude_entries(exclude_path, entries)
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
    from code_agnostic.git_exclude_service import GitExcludeService

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
    from code_agnostic.git_exclude_service import GitExcludeService

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
    from code_agnostic.git_exclude_service import GitExcludeService

    core = CoreRepository()
    service = GitExcludeService(core)
    try:
        config = service.list_patterns(workspace)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(f"  include_defaults: {config.get('include_defaults', True)}")
    extras = config.get("extra_patterns", [])
    if extras:
        click.echo("  extra_patterns:")
        for p in extras:
            click.echo(f"    - {p}")
    else:
        click.echo("  extra_patterns: (none)")


# ---------------------------------------------------------------------------
# rules group
# ---------------------------------------------------------------------------


@cli.group(help="Manage rule definitions in the hub config.")
def rules() -> None:
    pass


@rules.command("list", help="List configured rules.")
@workspace_option()
@click.pass_obj
def rules_list(obj: dict[str, str], workspace: str | None) -> None:
    from code_agnostic.rules.repository import RulesRepository

    core = CoreRepository()
    if workspace is not None:
        names = {item["name"] for item in core.load_workspaces()}
        if workspace not in names:
            raise click.ClickException(f"Workspace not found: {workspace}")
        root = core.workspace_config_dir(workspace)
    else:
        root = core.root

    repo = RulesRepository(root)
    rule_list = repo.list_rules()
    if not rule_list:
        click.echo("No rules configured.")
        return
    for rule in rule_list:
        desc = rule.metadata.description or "(no description)"
        click.echo(f"  {rule.name}: {desc}")


@rules.command("remove", help="Remove a rule by name.")
@click.option("--name", required=True, help="Rule name to remove.")
@workspace_option()
@click.pass_obj
def rules_remove(obj: dict[str, str], name: str, workspace: str | None) -> None:
    from code_agnostic.rules.repository import RulesRepository

    core = CoreRepository()
    if workspace is not None:
        names = {item["name"] for item in core.load_workspaces()}
        if workspace not in names:
            raise click.ClickException(f"Workspace not found: {workspace}")
        root = core.workspace_config_dir(workspace)
    else:
        root = core.root

    repo = RulesRepository(root)
    if not repo.remove_rule(name):
        raise click.ClickException(f"Rule not found: {name}")
    click.echo(f"Removed: {name}")


# ---------------------------------------------------------------------------
# skills group
# ---------------------------------------------------------------------------


@cli.group(help="Manage skill definitions in the hub config.")
def skills() -> None:
    pass


@skills.command("list", help="List configured skills.")
@workspace_option()
@click.pass_obj
def skills_list(obj: dict[str, str], workspace: str | None) -> None:
    core = CoreRepository()
    if workspace is not None:
        names = {item["name"] for item in core.load_workspaces()}
        if workspace not in names:
            raise click.ClickException(f"Workspace not found: {workspace}")
        root = core.workspace_config_dir(workspace)
    else:
        root = core.root
    skill_sources = []
    skills_dir = root / "skills"
    if skills_dir.exists():
        for child in sorted(skills_dir.iterdir()):
            if child.is_dir() and (child / "SKILL.md").exists():
                skill_sources.append(child)
    if not skill_sources:
        click.echo("No skills configured.")
        return
    for source in skill_sources:
        click.echo(f"  {source.name}")


@skills.command("remove", help="Remove a skill by name.")
@click.option("--name", required=True, help="Skill name to remove.")
@workspace_option()
@click.pass_obj
def skills_remove(obj: dict[str, str], name: str, workspace: str | None) -> None:
    import shutil

    core = CoreRepository()
    if workspace is not None:
        names = {item["name"] for item in core.load_workspaces()}
        if workspace not in names:
            raise click.ClickException(f"Workspace not found: {workspace}")
        root = core.workspace_config_dir(workspace)
    else:
        root = core.root
    skill_dir = root / "skills" / name
    if not skill_dir.exists():
        raise click.ClickException(f"Skill not found: {name}")
    shutil.rmtree(skill_dir)
    click.echo(f"Removed: {name}")


# ---------------------------------------------------------------------------
# agents group (CLI management)
# ---------------------------------------------------------------------------


@cli.group(name="agents", help="Manage agent definitions in the hub config.")
def agents_group() -> None:
    pass


@agents_group.command("list", help="List configured agents.")
@workspace_option()
@click.pass_obj
def agents_list(obj: dict[str, str], workspace: str | None) -> None:
    core = CoreRepository()
    if workspace is not None:
        names = {item["name"] for item in core.load_workspaces()}
        if workspace not in names:
            raise click.ClickException(f"Workspace not found: {workspace}")
        root = core.workspace_config_dir(workspace)
    else:
        root = core.root
    agents_dir = root / "agents"
    agent_files = []
    if agents_dir.exists():
        for child in sorted(agents_dir.iterdir()):
            if not child.name.startswith("."):
                agent_files.append(child)
    if not agent_files:
        click.echo("No agents configured.")
        return
    for f in agent_files:
        click.echo(f"  {f.stem}")


@agents_group.command("remove", help="Remove an agent by name.")
@click.option("--name", required=True, help="Agent name to remove.")
@workspace_option()
@click.pass_obj
def agents_remove(obj: dict[str, str], name: str, workspace: str | None) -> None:
    core = CoreRepository()
    if workspace is not None:
        names = {item["name"] for item in core.load_workspaces()}
        if workspace not in names:
            raise click.ClickException(f"Workspace not found: {workspace}")
        root = core.workspace_config_dir(workspace)
    else:
        root = core.root
    agent_path = root / "agents" / f"{name}.md"
    if not agent_path.exists():
        raise click.ClickException(f"Agent not found: {name}")
    agent_path.unlink()
    click.echo(f"Removed: {name}")


# ---------------------------------------------------------------------------
# mcp group
# ---------------------------------------------------------------------------


@cli.group(help="Manage MCP server definitions in the hub config.")
def mcp() -> None:
    pass


@mcp.command("list", help="List configured MCP servers.")
@workspace_option()
@click.pass_obj
def mcp_list(obj: dict[str, str], workspace: str | None) -> None:
    core = CoreRepository()
    service = MCPManagementService(core)
    try:
        servers = service.list_servers(workspace=workspace)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    if not servers:
        click.echo("No MCP servers configured.")
        return
    for name, dto in sorted(servers.items()):
        detail = dto.command or dto.url or ""
        click.echo(f"  {name}: {detail}")


def _parse_env_pair(raw: str) -> tuple[str, str]:
    if "=" in raw:
        key, _, value = raw.partition("=")
        return key, value
    return raw, f"${{{raw}}}"


@mcp.command("add", help="Add an MCP server definition.")
@click.argument("name")
@click.option("--command", default=None, help="Command for stdio server.")
@click.option(
    "--args", "args_str", default=None, help="Comma-separated args for stdio server."
)
@click.option("--url", default=None, help="URL for HTTP/SSE server.")
@click.option(
    "--env",
    "env_pairs",
    multiple=True,
    help="Env var as KEY or KEY=VALUE (repeatable).",
)
@click.option(
    "--headers", "header_pairs", multiple=True, help="Header as KEY=VALUE (repeatable)."
)
@click.option(
    "--on-conflict",
    type=click.Choice([item.value for item in ConflictPolicy]),
    default=ConflictPolicy.FAIL.value,
    show_default=True,
)
@workspace_option()
@click.pass_obj
def mcp_add(
    obj: dict[str, str],
    name: str,
    command: str | None,
    args_str: str | None,
    url: str | None,
    env_pairs: tuple[str, ...],
    header_pairs: tuple[str, ...],
    on_conflict: str,
    workspace: str | None,
) -> None:
    args = [a.strip() for a in args_str.split(",")] if args_str else []
    env = dict(_parse_env_pair(p) for p in env_pairs) if env_pairs else {}
    headers = dict(_parse_env_pair(p) for p in header_pairs) if header_pairs else {}

    core = CoreRepository()
    service = MCPManagementService(core)
    try:
        msg = service.add_server(
            name=name,
            command=command,
            args=args or None,
            url=url,
            env=env or None,
            headers=headers or None,
            workspace=workspace,
            on_conflict=ConflictPolicy(on_conflict),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))
    click.echo(msg)


@mcp.command("remove", help="Remove an MCP server definition.")
@click.argument("name")
@workspace_option()
@click.pass_obj
def mcp_remove(obj: dict[str, str], name: str, workspace: str | None) -> None:
    core = CoreRepository()
    service = MCPManagementService(core)
    try:
        removed = service.remove_server(name, workspace=workspace)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    if not removed:
        raise click.ClickException(f"Server not found: {name}")
    click.echo(f"Removed: {name}")


# ---------------------------------------------------------------------------
# import group
# ---------------------------------------------------------------------------


@cli.group(name="import", help="Import existing app config into hub.")
def import_group() -> None:
    pass


def _parse_import_sections(items: tuple[str, ...]) -> list[ImportSection] | None:
    if not items:
        return None
    return [ImportSection(item.lower()) for item in items]


@import_group.command("plan", help="Plan import from source app into hub.")
@import_app_option()
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
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    default=False,
    help="Launch interactive TUI to pick individual items.",
)
@verbose_option()
@click.pass_obj
def import_plan(
    obj: dict[str, str],
    app: str,
    includes: tuple[str, ...],
    excludes: tuple[str, ...],
    on_conflict: str,
    source_root: Path | None,
    follow_symlinks: bool,
    interactive: bool,
    verbose: bool,
) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = ImportService(core)

    result_plan = service.plan(
        source_app=app,
        include=_parse_import_sections(includes),
        exclude=_parse_import_sections(excludes),
        conflict_policy=ConflictPolicy(on_conflict),
        source_root=source_root,
        follow_symlinks=follow_symlinks,
    )

    if interactive:
        from code_agnostic.tui.import_selector import (
            ImportSelectorApp,
            filter_plan_by_selection,
        )

        tui_app = ImportSelectorApp(result_plan)
        selected = tui_app.run()
        if not selected:
            click.echo("No items selected.")
            return
        result_plan = filter_plan_by_selection(result_plan, selected)

    ui.render_import_plan(
        result_plan,
        mode=f"import:plan:{app.lower()}",
        verbose=verbose,
    )

    if result_plan.errors:
        raise click.exceptions.Exit(1)


@import_group.command("apply", help="Apply import from source app into hub.")
@import_app_option()
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
@click.option(
    "-i",
    "--interactive",
    is_flag=True,
    default=False,
    help="Launch interactive TUI to pick individual items.",
)
@verbose_option()
@click.pass_obj
def import_apply(
    obj: dict[str, str],
    app: str,
    includes: tuple[str, ...],
    excludes: tuple[str, ...],
    on_conflict: str,
    source_root: Path | None,
    follow_symlinks: bool,
    interactive: bool,
    verbose: bool,
) -> None:
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    service = ImportService(core)

    result_plan = service.plan(
        source_app=app,
        include=_parse_import_sections(includes),
        exclude=_parse_import_sections(excludes),
        conflict_policy=ConflictPolicy(on_conflict),
        source_root=source_root,
        follow_symlinks=follow_symlinks,
    )

    if interactive:
        from code_agnostic.tui.import_selector import (
            ImportSelectorApp,
            filter_plan_by_selection,
        )

        tui_app = ImportSelectorApp(result_plan)
        selected = tui_app.run()
        if not selected:
            click.echo("No items selected.")
            return
        result_plan = filter_plan_by_selection(result_plan, selected)

    ui.render_import_plan(
        result_plan,
        mode=f"import:apply:{app.lower()}",
        verbose=verbose,
    )

    if result_plan.errors:
        raise click.ClickException("Import aborted due to conflicts/errors above.")

    result = service.apply(result_plan)
    ui.render_import_apply_result(result)

    if result.failed:
        raise click.exceptions.Exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


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
