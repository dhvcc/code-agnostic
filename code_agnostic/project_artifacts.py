from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from code_agnostic.apps.app_id import AppId
from code_agnostic.constants import (
    AGENTS_PROJECT_DIRNAME,
    CLAUDE_PROJECT_DIRNAME,
    CODEX_PROJECT_DIRNAME,
    COPILOT_PROJECT_DIRNAME,
    CURSOR_PROJECT_DIRNAME,
    OPENCODE_PROJECT_DIRNAME,
    SKILLS_DIRNAME,
)

if TYPE_CHECKING:
    from code_agnostic.core.repository import CoreRepository


def load_project_entries(core: CoreRepository) -> list[dict[str, str]]:
    return core.load_projects()


def project_config_dir(core: CoreRepository, name: str) -> Path:
    return core.project_config_dir(name)


def project_skills_dir(app_id: AppId, project_root: Path) -> Path:
    if app_id == AppId.CODEX:
        return project_root / AGENTS_PROJECT_DIRNAME / SKILLS_DIRNAME
    return project_root / _project_dir_name(app_id) / SKILLS_DIRNAME


def _project_dir_name(app_id: AppId) -> str:
    if app_id == AppId.OPENCODE:
        return OPENCODE_PROJECT_DIRNAME
    if app_id == AppId.CURSOR:
        return CURSOR_PROJECT_DIRNAME
    if app_id == AppId.CODEX:
        return CODEX_PROJECT_DIRNAME
    if app_id == AppId.CLAUDE:
        return CLAUDE_PROJECT_DIRNAME
    if app_id == AppId.COPILOT:
        return COPILOT_PROJECT_DIRNAME
    raise ValueError(f"Unsupported app for project artifact: {app_id.value}")
