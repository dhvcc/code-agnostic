"""Apply command."""

import click
from rich.console import Console

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.cli.options import app_option, verbose_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.models import SyncPlan
from code_agnostic.tui import SyncConsoleUI


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

    if restore_lines:
        lines.append("Repair global/workspace outputs from the active synced revision.")
        lines.extend(restore_lines)

    if any(action.project is not None for action in plan.actions):
        lines.append(
            "Project outputs are checked by status; project restore is not available yet."
        )

    return "\n".join(lines)


@click.command(help="Apply planned sync changes.")
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
    next_steps = (
        _apply_next_steps(scoped_plan, target) if applied > 0 and failed == 0 else None
    )
    ui.render_apply_result(applied, failed, failures, next_steps=next_steps)

    if failed:
        raise click.exceptions.Exit(1)
