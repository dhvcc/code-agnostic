from pathlib import Path
from typing import Any, Optional

from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.constants import AGENTS_FILENAME
from code_agnostic.models import (
    RepoSyncStatus,
    WorkspaceRepoStatusRow,
    WorkspaceStatusRow,
    WorkspaceSyncStatus,
)
from code_agnostic.workspaces import WorkspaceService


class StatusService:
    def __init__(self, workspace_service: Optional[WorkspaceService] = None) -> None:
        self.workspace_service = workspace_service or WorkspaceService()

    def build_workspace_status(
        self, source_repo: ISourceRepository
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

            rules_file = self.workspace_service.resolve_rules_file(workspace_path)
            if rules_file is None:
                status_rows.append(
                    WorkspaceStatusRow(
                        name=workspace_name,
                        path=str(workspace_path),
                        status=WorkspaceSyncStatus.ERROR,
                        detail="no workspace rules file",
                        repos=[],
                    )
                )
                continue

            repos = self.workspace_service.discover_git_repos(workspace_path)
            repo_rows = [self._repo_sync_status(repo, rules_file) for repo in repos]

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
    def _repo_sync_status(repo_path: Path, rules_file: Path) -> WorkspaceRepoStatusRow:
        target = repo_path / AGENTS_FILENAME
        desired = str(rules_file.resolve())
        if target.is_symlink() and str(target.resolve()) == desired:
            return WorkspaceRepoStatusRow(
                repo=repo_path.name, status=RepoSyncStatus.SYNCED, detail="linked"
            )
        return WorkspaceRepoStatusRow(
            repo=repo_path.name,
            status=RepoSyncStatus.NEEDS_SYNC,
            detail=f"missing or mismatched {AGENTS_FILENAME}",
        )


def build_workspace_status(core: ISourceRepository) -> list[dict[str, Any]]:
    rows = StatusService().build_workspace_status(source_repo=core)
    return [row.as_dict() for row in rows]
