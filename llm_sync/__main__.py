from pathlib import Path
from typing import Dict

import click
from rich.console import Console

from llm_sync.executor import SyncExecutor
from llm_sync.models import EditorStatusRow, EditorSyncStatus, SyncTarget
from llm_sync.planner import SyncPlanner
from llm_sync.repositories.common import CommonRepository
from llm_sync.repositories.opencode import OpenCodeRepository
from llm_sync.status import StatusService
from llm_sync.tui import SyncConsoleUI
from llm_sync.workspaces import WorkspaceService


def _repos_from_obj(_obj: Dict[str, str]) -> tuple[CommonRepository, OpenCodeRepository]:
    common = CommonRepository()
    opencode = OpenCodeRepository()
    return common, opencode


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.pass_context
def cli(ctx: click.Context) -> None:
    """OpenCode-first config sync."""
    ctx.obj = {}


@cli.command(help="Build and print a dry-run plan.")
@click.pass_obj
def plan(obj: Dict[str, str]) -> None:
    ui = SyncConsoleUI(Console())
    common, opencode = _repos_from_obj(obj)

    try:
        plan_result = SyncPlanner(common=common, opencode=opencode).build()
    except Exception as exc:
        raise click.ClickException(f"Fatal: {exc}")

    ui.render_plan(plan_result, mode="plan")

    if plan_result.errors:
        raise click.exceptions.Exit(1)


@cli.command(help="Apply planned sync changes.")
@click.argument(
    "target",
    required=False,
    type=click.Choice([SyncTarget.ALL.value, SyncTarget.OPENCODE.value], case_sensitive=False),
    default=SyncTarget.ALL.value,
)
@click.pass_obj
def apply(obj: Dict[str, str], target: str) -> None:
    ui = SyncConsoleUI(Console())
    common, opencode = _repos_from_obj(obj)

    try:
        plan_result = SyncPlanner(common=common, opencode=opencode).build()
    except Exception as exc:
        raise click.ClickException(f"Fatal: {exc}")

    normalized_target = SyncTarget(target.lower())
    scoped_plan = plan_result.filter_for_target(
        target=normalized_target,
        config_path=opencode.config_path,
        skills_root=opencode.skills_dir,
        agents_root=opencode.agents_dir,
    )

    ui.render_plan(scoped_plan, mode=f"apply:{normalized_target.value}")

    if scoped_plan.errors:
        raise click.ClickException("Apply aborted due to planning/parsing errors above.")

    applied, failed, failures = SyncExecutor(common=common, opencode=opencode).execute(scoped_plan)
    ui.render_apply_result(applied, failed, failures, str(common.state_md))

    if failed:
        raise click.exceptions.Exit(1)


@cli.command(help="Show sync status for editors and workspaces.")
@click.pass_obj
def status(obj: Dict[str, str]) -> None:
    ui = SyncConsoleUI(Console())
    common, opencode = _repos_from_obj(obj)
    status_service = StatusService()

    try:
        plan_result = SyncPlanner(common=common, opencode=opencode).build()
        editor_rows = status_service.build_editor_status(plan_result, opencode)
    except Exception as exc:
        editor_rows = [
            EditorStatusRow(
                name="opencode",
                status=EditorSyncStatus.ERROR,
                detail=f"cannot evaluate ({exc})",
            ),
            EditorStatusRow(
                name="cursor",
                status=EditorSyncStatus.DISABLED,
                detail="not managed",
            ),
        ]

    workspace_rows = status_service.build_workspace_status(common)
    ui.render_status(
        [item.as_dict() for item in editor_rows],
        [item.as_dict() for item in workspace_rows],
    )


@cli.group(help="Manage workspace roots for repo rule propagation.")
def workspaces() -> None:
    pass


@workspaces.command("add", help="Add a workspace by name and path.")
@click.argument("name")
@click.argument("path", type=click.Path(path_type=Path))
@click.pass_obj
def workspaces_add(obj: Dict[str, str], name: str, path: Path) -> None:
    ui = SyncConsoleUI(Console())
    common, _ = _repos_from_obj(obj)
    try:
        common.add_workspace(name, path)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    ui.render_workspace_saved(name, str(path.expanduser().resolve()))


@workspaces.command("remove", help="Remove a workspace from config by name.")
@click.argument("name")
@click.pass_obj
def workspaces_remove(obj: Dict[str, str], name: str) -> None:
    ui = SyncConsoleUI(Console())
    common, _ = _repos_from_obj(obj)
    existing = {item["name"]: item["path"] for item in common.load_workspaces()}
    removed = common.remove_workspace(name)
    if not removed:
        raise click.ClickException(f"Workspace not found: {name}")
    ui.render_workspace_saved(name, existing.get(name, ""), removed=True)


@workspaces.command("list", help="List configured workspaces and detected repos.")
@click.pass_obj
def workspaces_list(obj: Dict[str, str]) -> None:
    ui = SyncConsoleUI(Console())
    common, _ = _repos_from_obj(obj)
    workspace_service = WorkspaceService()

    overview: list[dict] = []
    for item in common.load_workspaces():
        workspace_path = Path(item["path"])
        repos: list[str] = []
        if workspace_path.exists() and workspace_path.is_dir():
            repos = [
                str(path.relative_to(workspace_path))
                for path in workspace_service.discover_git_repos(workspace_path)
            ]
        overview.append(
            {
                "name": item["name"],
                "path": item["path"],
                "repos": repos,
            }
        )

    ui.render_workspaces_overview(overview)


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
