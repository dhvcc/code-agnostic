from pathlib import Path

from code_agnostic.apps.app_id import AppId, AppMetadata, app_metadata
from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.apps.common.interfaces.service import IAppConfigService
from code_agnostic.constants import CLAUDE_CONFIG_FILENAME
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.models import (
    RepoSyncStatus,
    WorkspaceRepoStatusRow,
    WorkspaceStatusRow,
    WorkspaceSyncStatus,
)
from code_agnostic.utils import read_json_safe
from code_agnostic.workspace_artifacts import repo_artifact_paths
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
                if (
                    meta.project_dir_name is not None
                    and meta.supports_workspace_propagation
                ):
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
        app_ids = [meta.app_id for meta in app_metas or []]

        for meta in app_metas or []:
            if meta.app_id == AppId.CLAUDE:
                if ws_source.has_mcp() and not _claude_project_mcp_exists(repo_path):
                    issues.append("missing or mismatched claude project mcp")

        for artifact in repo_artifact_paths(
            ws_source,
            app_ids,
            repo_path=repo_path,
        ):
            if not (repo_path / artifact.relative_path).exists():
                issues.append(f"missing or mismatched {artifact.label}")

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


def _claude_project_mcp_exists(repo_path: Path) -> bool:
    payload, error = read_json_safe(Path.home() / CLAUDE_CONFIG_FILENAME)
    if error is not None or not isinstance(payload, dict):
        return False
    projects = payload.get("projects")
    if not isinstance(projects, dict):
        return False
    project = projects.get(str(repo_path.resolve()))
    if not isinstance(project, dict):
        return False
    return isinstance(project.get("mcpServers"), dict)
