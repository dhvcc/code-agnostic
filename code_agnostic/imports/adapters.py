from dataclasses import dataclass
from pathlib import Path

from code_agnostic.apps.app_id import AppId
from code_agnostic.apps.codex.config_repository import CodexConfigRepository
from code_agnostic.apps.codex.mapper import CodexMCPMapper
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.cursor.config_repository import CursorConfigRepository
from code_agnostic.apps.cursor.mapper import CursorMCPMapper
from code_agnostic.apps.opencode.config_repository import OpenCodeConfigRepository
from code_agnostic.apps.opencode.mapper import OpenCodeMCPMapper


@dataclass(frozen=True)
class ImportAdapter:
    app_id: AppId
    root: Path
    skills_dir: Path
    agents_dir: Path | None
    mapper: IAppMCPMapper
    config_repository: object

    def load_mcp_payload(self) -> dict:
        return self.config_repository.load_mcp_payload()  # type: ignore[attr-defined]


def create_import_adapter(app: str, source_root: Path | None = None) -> ImportAdapter:
    normalized = app.lower()
    if normalized == AppId.CODEX.value:
        repo = CodexConfigRepository(root=source_root)
        return ImportAdapter(
            app_id=AppId.CODEX,
            root=repo.root,
            skills_dir=repo.skills_dir,
            agents_dir=None,
            mapper=CodexMCPMapper(),
            config_repository=repo,
        )
    if normalized == AppId.CURSOR.value:
        repo = CursorConfigRepository(root=source_root)
        return ImportAdapter(
            app_id=AppId.CURSOR,
            root=repo.root,
            skills_dir=repo.skills_dir,
            agents_dir=repo.agents_dir,
            mapper=CursorMCPMapper(),
            config_repository=repo,
        )
    if normalized == AppId.OPENCODE.value:
        repo = OpenCodeConfigRepository(root=source_root)
        return ImportAdapter(
            app_id=AppId.OPENCODE,
            root=repo.root,
            skills_dir=repo.skills_dir,
            agents_dir=repo.agents_dir,
            mapper=OpenCodeMCPMapper(),
            config_repository=repo,
        )
    raise ValueError(f"Unsupported source app: {app}")
