from pathlib import Path
from typing import Dict

import click
from rich.console import Console

from llm_sync.executor import execute_apply
from llm_sync.output import render_apply_result, render_plan, render_status, render_workspace_saved, render_workspaces_overview
from llm_sync.planner import build_plan, filter_plan_for_target
from llm_sync.repositories.common import CommonRepository
from llm_sync.repositories.opencode import OpenCodeRepository
from llm_sync.status import build_editor_status, build_workspace_status
from llm_sync.workspaces import list_workspace_repos


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
    console = Console()
    common, opencode = _repos_from_obj(obj)

    try:
        plan_result = build_plan(common, opencode)
    except Exception as exc:
        raise click.ClickException("Fatal: {0}".format(exc))

    render_plan(console, plan_result, mode="plan")

    if plan_result.errors:
        raise click.exceptions.Exit(1)


@cli.command(help="Apply planned sync changes.")
@click.argument("target", required=False, type=click.Choice(["all", "opencode"], case_sensitive=False), default="all")
@click.pass_obj
def apply(obj: Dict[str, str], target: str) -> None:
    console = Console()
    common, opencode = _repos_from_obj(obj)

    try:
        plan_result = build_plan(common, opencode)
    except Exception as exc:
        raise click.ClickException("Fatal: {0}".format(exc))

    scoped_plan = filter_plan_for_target(plan_result, target.lower(), opencode)

    render_plan(console, scoped_plan, mode="apply:{0}".format(target.lower()))

    if scoped_plan.errors:
        raise click.ClickException("Apply aborted due to planning/parsing errors above.")

    applied, failed, failures = execute_apply(scoped_plan, common, opencode)
    render_apply_result(console, applied, failed, failures, str(common.state_md))

    if failed:
        raise click.exceptions.Exit(1)


@cli.command(help="Show sync status for editors and workspaces.")
@click.pass_obj
def status(obj: Dict[str, str]) -> None:
    console = Console()
    common, opencode = _repos_from_obj(obj)

    try:
        plan_result = build_plan(common, opencode)
        editors = build_editor_status(plan_result, opencode)
    except Exception as exc:
        editors = [
            {
                "name": "opencode",
                "status": "error",
                "detail": "cannot evaluate ({0})".format(exc),
            },
            {
                "name": "cursor",
                "status": "disabled",
                "detail": "not managed",
            },
        ]
    workspaces = build_workspace_status(common)
    render_status(console, editors, workspaces)


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


@cli.group(help="Manage workspace roots for repo rule propagation.")
def workspaces() -> None:
    pass


@workspaces.command("add", help="Add a workspace by name and path.")
@click.argument("name")
@click.argument("path", type=click.Path(path_type=Path))
@click.pass_obj
def workspaces_add(obj: Dict[str, str], name: str, path: Path) -> None:
    console = Console()
    common, _ = _repos_from_obj(obj)
    try:
        common.add_workspace(name, path)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    render_workspace_saved(console, name, str(path.expanduser().resolve()))


@workspaces.command("remove", help="Remove a workspace from config by name.")
@click.argument("name")
@click.pass_obj
def workspaces_remove(obj: Dict[str, str], name: str) -> None:
    console = Console()
    common, _ = _repos_from_obj(obj)
    existing = {item["name"]: item["path"] for item in common.load_workspaces()}
    removed = common.remove_workspace(name)
    if not removed:
        raise click.ClickException(f"Workspace not found: {name}")
    render_workspace_saved(console, name, existing.get(name, ""), removed=True)


@workspaces.command("list", help="List configured workspaces and detected repos.")
@click.pass_obj
def workspaces_list(obj: Dict[str, str]) -> None:
    console = Console()
    common, _ = _repos_from_obj(obj)

    overview: list[dict] = []
    for item in common.load_workspaces():
        workspace_path = Path(item["path"])
        repos = []
        if workspace_path.exists() and workspace_path.is_dir():
            repos = [str(path.relative_to(workspace_path)) for path in list_workspace_repos(workspace_path)]
        overview.append(
            {
                "name": item["name"],
                "path": item["path"],
                "repos": repos,
            }
        )

    render_workspaces_overview(console, overview)


if __name__ == "__main__":
    raise SystemExit(main())
