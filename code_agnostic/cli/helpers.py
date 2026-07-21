"""Shared helper functions for CLI commands."""

from pathlib import Path, PureWindowsPath

import click

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.core.repository import CoreRepository
from code_agnostic.errors import SyncAppError
from code_agnostic.models import (
    ActionStatus,
    EditorStatusRow,
    EditorSyncStatus,
    SyncPlan,
    WorkspaceConfig,
)


def _workspace_entries_by_name(core: CoreRepository) -> dict[str, WorkspaceConfig]:
    return {item.name: item for item in core.load_workspaces()}


def _project_entries_by_name(core: CoreRepository) -> dict[str, WorkspaceConfig]:
    return {item.name: item for item in core.load_projects()}


def require_workspace_entry(core: CoreRepository, workspace: str) -> WorkspaceConfig:
    try:
        entry = _workspace_entries_by_name(core).get(workspace)
    except SyncAppError as exc:
        raise click.ClickException(str(exc)) from exc
    if entry is None:
        raise click.ClickException(f"Workspace not found: {workspace}")
    return entry


def require_project_entry(core: CoreRepository, project: str) -> WorkspaceConfig:
    try:
        entry = _project_entries_by_name(core).get(project)
    except SyncAppError as exc:
        raise click.ClickException(str(exc)) from exc
    if entry is None:
        raise click.ClickException(f"Project not found: {project}")
    return entry


def workspace_config_root(core: CoreRepository, workspace: str | None) -> Path:
    if workspace is None:
        return core.root
    require_workspace_entry(core, workspace)
    return core.workspace_config_dir(workspace)


def validate_resource_name(name: str, resource_type: str) -> None:
    if (
        not name.strip()
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or Path(name).is_absolute()
        or PureWindowsPath(name).drive
    ):
        raise click.ClickException(f"Invalid {resource_type} name: {name}")


def reject_symlinked_source_dir(path: Path, resource_type: str) -> None:
    if path.is_symlink():
        raise click.ClickException(
            f"Refusing to modify symlinked {resource_type} source directory: {path}"
        )


def status_row_for_app(
    app_name: str, plan: SyncPlan, apps: AppsService
) -> EditorStatusRow:
    if not apps.is_enabled(app_name):
        return EditorStatusRow(
            name=app_name,
            status=EditorSyncStatus.DISABLED,
            detail="disabled by apps config",
        )

    relevant = [action for action in plan.actions if action.app == app_name]

    if plan.errors:
        return EditorStatusRow(
            name=app_name,
            status=EditorSyncStatus.ERROR,
            detail=f"cannot evaluate ({plan.errors[0]})",
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


def ensure_exclude_entries(path: Path, entries: list[str]) -> tuple[int, bool]:
    """Add entries to a file, skipping duplicates and comments."""
    existing_lines: list[str] = []
    if path.exists():
        existing_lines = path.read_text(encoding="utf-8").splitlines()

    seen_entries = {
        line.strip()
        for line in existing_lines
        if line.strip() and not line.lstrip().startswith("#")
    }
    additions: list[str] = []
    for entry in entries:
        normalized = entry.strip()
        if not normalized or normalized in seen_entries:
            continue
        additions.append(entry)
        seen_entries.add(normalized)
    if not additions:
        return 0, False

    merged = list(existing_lines)
    if merged and merged[-1] != "":
        merged.append("")
    merged.extend(additions)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(merged) + "\n", encoding="utf-8")
    return len(additions), True
