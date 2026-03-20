"""Import group commands."""

from pathlib import Path

import click
from rich.console import Console

from code_agnostic.cli.options import import_app_option, verbose_option
from code_agnostic.core.repository import CoreRepository
from code_agnostic.imports.models import ConflictPolicy, ImportSection
from code_agnostic.imports.service import ImportService
from code_agnostic.tui import SyncConsoleUI


def _parse_import_sections(items: tuple[str, ...]) -> list[ImportSection] | None:
    if not items:
        return None
    return [ImportSection(item.lower()) for item in items]


@click.group(name="import", help="Import existing app config into hub.")
def import_group() -> None:
    pass


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
