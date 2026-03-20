"""Shared helper functions for CLI commands."""

from pathlib import Path

import click

from code_agnostic.apps.apps_service import AppsService
from code_agnostic.core.repository import CoreRepository
from code_agnostic.models import ActionStatus, EditorStatusRow, EditorSyncStatus


def _workspace_entries_by_name(core: CoreRepository) -> dict[str, dict[str, str]]:
    return {item["name"]: item for item in core.load_workspaces()}


def require_workspace_entry(core: CoreRepository, workspace: str) -> dict[str, str]:
    entry = _workspace_entries_by_name(core).get(workspace)
    if entry is None:
        raise click.ClickException(f"Workspace not found: {workspace}")
    return entry


def workspace_config_root(core: CoreRepository, workspace: str | None) -> Path:
    if workspace is None:
        return core.root
    require_workspace_entry(core, workspace)
    return core.workspace_config_dir(workspace)


def status_row_for_app(app_name: str, plan, apps: AppsService) -> EditorStatusRow:
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
