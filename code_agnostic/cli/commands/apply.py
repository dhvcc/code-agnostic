"""Apply command."""

import click
from rich.console import Console

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.cli.options import app_option, verbose_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.models import SyncPlan
from code_agnostic.tui import SyncConsoleUI
from code_agnostic.utils import compact_home_paths_in_text

_MAX_PLANNER_ERROR_LENGTH = 2_000


def _planner_error_summary(error: Exception) -> str:
    summary = compact_home_paths_in_text(" ".join(str(error).split()))
    summary = "".join(character for character in summary if character.isprintable())
    if not summary:
        return type(error).__name__
    if len(summary) > _MAX_PLANNER_ERROR_LENGTH:
        return f"{summary[:_MAX_PLANNER_ERROR_LENGTH]}..."
    return summary


def _apply_next_steps(plan: SyncPlan, target: str) -> str | None:
    if not plan.actions:
        return None

    normalized_target = target.lower()
    target_flag = "" if normalized_target == "all" else f" -a {normalized_target}"
    lines = [
        "Managed outputs were written. Check drift after target files change.",
        f"- code-agnostic status{target_flag}",
    ]

    restore_lines = []
    if any(
        action.workspace is None and action.project is None for action in plan.actions
    ):
        restore_lines.append("- code-agnostic restore")

    workspace_names = sorted(
        {action.workspace for action in plan.actions if action.workspace}
    )
    for workspace_name in workspace_names[:3]:
        restore_lines.append(f"- code-agnostic restore -w {workspace_name}")
    if len(workspace_names) > 3:
        restore_lines.append("- code-agnostic restore -w <workspace>")

    project_names = sorted(
        {action.project for action in plan.actions if action.project}
    )
    for project_name in project_names[:3]:
        restore_lines.append(f"- code-agnostic restore --project {project_name}")
    if len(project_names) > 3:
        restore_lines.append("- code-agnostic restore --project <project>")

    if restore_lines:
        lines.append("Repair managed outputs from the active synced revision.")
        lines.extend(restore_lines)

    return "\n".join(lines)


@click.command(help="Apply planned sync changes.")
@app_option()
@click.option(
    "--apply-excludes",
    is_flag=True,
    default=False,
    help="Also write managed sync paths to each repo's .git/info/exclude.",
)
@verbose_option()
@click.pass_obj
def apply(obj: dict[str, str], app: str, apply_excludes: bool, verbose: bool) -> None:
    target = app or "all"
    ui = SyncConsoleUI(Console())
    core = CoreRepository()
    apps = AppsService(core)

    try:
        scoped_plan, apply_result = apps.apply_target(
            target, apply_excludes=apply_excludes
        )
    except Exception as exc:
        raise click.ClickException(f"Fatal: {exc}")

    ui.render_plan(scoped_plan, mode=f"apply:{target.lower()}", verbose=verbose)

    if not scoped_plan.actions and not scoped_plan.errors:
        ui.render_apply_result(applied=0, failed=0, failures=[])
        return

    if scoped_plan.errors:
        for error in scoped_plan.errors:
            click.echo(
                f"code-agnostic apply planning error: {_planner_error_summary(error)}",
                err=True,
            )
        raise click.ClickException(
            "Apply aborted due to planning/parsing errors above."
        )

    applied, failed, failures = apply_result
    next_steps = (
        _apply_next_steps(scoped_plan, target) if applied > 0 and failed == 0 else None
    )
    ui.render_apply_result(applied, failed, failures, next_steps=next_steps)

    if failed:
        for failure in failures:
            click.echo(f"code-agnostic apply: {failure}", err=True)
        raise click.exceptions.Exit(1)
