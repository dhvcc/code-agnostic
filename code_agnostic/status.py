from pathlib import Path

from code_agnostic.apps.app_id import AppMetadata, app_metadata
from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.apps.common.interfaces.service import IAppConfigService
from code_agnostic.constants import AGENTS_FILENAME
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.models import (
    RepoSyncStatus,
    WorkspaceRepoStatusRow,
    WorkspaceStatusRow,
    WorkspaceSyncStatus,
)
from code_agnostic.workspaces import WorkspaceService


class StatusService:
    def __init__(self, workspace_service: WorkspaceService | None = None) -> None:
        self.workspace_service = workspace_service or WorkspaceService()

    def build_workspace_status(
        self,
        source_repo: ISourceRepository,
        app_services: list[IAppConfigService] | None = None,
    ) -> list[WorkspaceStatusRow]:
        status_rows: list[WorkspaceStatusRow] = []

        for workspace in source_repo.load_workspaces():
            workspace_name = workspace["name"]
            workspace_path = Path(workspace["path"])

            if not workspace_path.exists() or not workspace_path.is_dir():
                status_rows.append(
                    WorkspaceStatusRow(
                        name=workspace_name,
                        path=str(workspace_path),
                        status=WorkspaceSyncStatus.ERROR,
                        detail="workspace path missing",
                        repos=[],
                    )
                )
                continue

            ws_source = WorkspaceConfigRepository(
                root=source_repo.workspace_config_dir(workspace_name)
            )

            if not ws_source.has_any_config():
                status_rows.append(
                    WorkspaceStatusRow(
                        name=workspace_name,
                        path=str(workspace_path),
                        status=WorkspaceSyncStatus.ERROR,
                        detail="no workspace config",
                        repos=[],
                    )
                )
                continue

            repos = self.workspace_service.discover_git_repos(workspace_path)

            app_metas: list[AppMetadata] = []
            for svc in app_services or []:
                meta = app_metadata(svc.app_id)
                if meta.project_dir_name is not None:
                    app_metas.append(meta)

            repo_rows = [
                self._repo_sync_status(repo, ws_source, app_metas) for repo in repos
            ]

            detail = "all git repos synced"
            status = WorkspaceSyncStatus.SYNCED
            if not repos:
                detail = "no git repos found"
            elif any(item.status != RepoSyncStatus.SYNCED for item in repo_rows):
                status = WorkspaceSyncStatus.DRIFT
                detail = "one or more repos need sync"

            status_rows.append(
                WorkspaceStatusRow(
                    name=workspace_name,
                    path=str(workspace_path),
                    status=status,
                    detail=detail,
                    repos=repo_rows,
                )
            )

        return status_rows

    @staticmethod
    def _repo_sync_status(
        repo_path: Path,
        ws_source: WorkspaceConfigRepository,
        app_metas: list[AppMetadata] | None = None,
    ) -> WorkspaceRepoStatusRow:
        issues: list[str] = []

        # Check AGENTS.md symlink
        if ws_source.has_rules():
            target = repo_path / AGENTS_FILENAME
            desired = str(ws_source.rules_file.resolve())
            if not (target.is_symlink() and str(target.resolve()) == desired):
                issues.append(f"missing or mismatched {AGENTS_FILENAME}")

        # Check skill symlinks per app
        skill_sources = ws_source.list_skill_sources()
        if skill_sources:
            for meta in app_metas or []:
                skills_dir = repo_path / meta.project_dir_name / "skills"
                for src in skill_sources:
                    link = skills_dir / src.name
                    if not (
                        link.is_symlink() and str(link.resolve()) == str(src.resolve())
                    ):
                        issues.append(f"missing {meta.app_id.value} skill: {src.name}")

        # Check agent symlinks per app
        agent_sources = ws_source.list_agent_sources()
        if agent_sources:
            for meta in app_metas or []:
                if not meta.supports_import_agents:
                    continue
                agents_dir = repo_path / meta.project_dir_name / "agents"
                for src in agent_sources:
                    link = agents_dir / src.name
                    if not (
                        link.is_symlink() and str(link.resolve()) == str(src.resolve())
                    ):
                        issues.append(f"missing {meta.app_id.value} agent: {src.name}")

        if not issues:
            return WorkspaceRepoStatusRow(
                repo=repo_path.name,
                status=RepoSyncStatus.SYNCED,
                detail="linked",
            )

        return WorkspaceRepoStatusRow(
            repo=repo_path.name,
            status=RepoSyncStatus.NEEDS_SYNC,
            detail="; ".join(issues),
        )
