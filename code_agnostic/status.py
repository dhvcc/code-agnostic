from pathlib import Path

from code_agnostic.utils import read_json_safe

from code_agnostic.apps.app_id import AppId, AppMetadata, app_metadata
from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.apps.common.interfaces.service import IAppConfigService
from code_agnostic.constants import (
    AGENTS_PROJECT_DIRNAME,
    CLAUDE_CONFIG_FILENAME,
    CLAUDE_LOCAL_FILENAME,
)
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.models import (
    Action,
    ActionStatus,
    RepoSyncStatus,
    WorkspaceRepoStatusRow,
    WorkspaceStatusRow,
    WorkspaceSyncStatus,
)
from code_agnostic.planner import SyncPlanner
from code_agnostic.utils import is_under
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
        workspace_actions = self._workspace_actions(source_repo, app_services)

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
                self._repo_sync_status(
                    repo,
                    ws_source,
                    app_metas,
                    workspace_actions=[
                        action
                        for action in workspace_actions
                        if action.workspace == workspace_name
                        and is_under(action.path, repo)
                    ],
                )
                for repo in repos
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
    def _workspace_actions(
        source_repo: ISourceRepository,
        app_services: list[IAppConfigService] | None,
    ) -> list[Action]:
        if not app_services:
            return []
        plan = SyncPlanner(core=source_repo, app_services=app_services).build()
        return [action for action in plan.actions if action.workspace is not None]

    @staticmethod
    def _repo_sync_status(
        repo_path: Path,
        ws_source: WorkspaceConfigRepository,
        app_metas: list[AppMetadata] | None = None,
        workspace_actions: list[Action] | None = None,
    ) -> WorkspaceRepoStatusRow:
        issues: list[str] = []

        if workspace_actions is not None:
            for action in workspace_actions:
                if action.status == ActionStatus.NOOP:
                    continue
                issues.append(StatusService._repo_action_issue(action, repo_path))
            return StatusService._repo_status_row(repo_path, issues)

        # Check workspace-managed config files in repo project dirs.
        # Workspace rendering creates regular files (not symlinks) in
        # ws_source.root/<project_dir_name>/..., and repos get the same.

        for meta in app_metas or []:
            filename = meta.config_filename
            if filename is None or meta.project_dir_name is None:
                continue
            # Cursor workspace propagation is disabled to avoid duplicate MCP startup.
            if meta.app_id == AppId.CURSOR:
                continue
            if meta.app_id == AppId.CLAUDE:
                if ws_source.has_mcp() and not _claude_project_mcp_exists(repo_path):
                    issues.append("missing or mismatched claude project mcp")
                if (
                    ws_source.has_rules()
                    and not (repo_path / CLAUDE_LOCAL_FILENAME).exists()
                ):
                    issues.append("missing or mismatched claude local memory")
                continue

            needs_config_link = ws_source.has_mcp() or (
                ws_source.has_rules() and meta.app_id == AppId.OPENCODE
            )
            if not needs_config_link:
                continue

            target = repo_path / meta.project_dir_name / filename
            if not target.exists():
                issues.append(f"missing or mismatched {meta.app_id.value} mcp link")

        if ws_source.has_skills():
            for meta in app_metas or []:
                if meta.project_dir_name is None:
                    continue
                if meta.app_id == AppId.CURSOR:
                    continue
                target = repo_path / meta.project_dir_name / "skills"
                if meta.app_id == AppId.CODEX:
                    target = repo_path / AGENTS_PROJECT_DIRNAME / "skills"
                if not target.exists():
                    issues.append(
                        f"missing or mismatched {meta.app_id.value} skills link"
                    )

        if ws_source.has_agents():
            for meta in app_metas or []:
                if not meta.supports_import_agents:
                    continue
                if meta.project_dir_name is None:
                    continue
                if meta.app_id == AppId.CURSOR:
                    continue
                target = repo_path / meta.project_dir_name / "agents"
                if not target.exists():
                    issues.append(
                        f"missing or mismatched {meta.app_id.value} agents link"
                    )

        return StatusService._repo_status_row(repo_path, issues)

    @staticmethod
    def _repo_status_row(repo_path: Path, issues: list[str]) -> WorkspaceRepoStatusRow:
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

    @staticmethod
    def _repo_action_issue(action: Action, repo_path: Path) -> str:
        rel_path = StatusService._relative_repo_path(action.path, repo_path)
        if action.status == ActionStatus.CREATE:
            return f"missing {rel_path}"
        if action.status in {ActionStatus.UPDATE, ActionStatus.FIX}:
            return f"mismatched {rel_path}"
        if action.status == ActionStatus.CONFLICT:
            return f"conflict at {rel_path}"
        if action.status == ActionStatus.REMOVE:
            return f"stale {rel_path}"
        return f"{action.status.value} {rel_path}"

    @staticmethod
    def _relative_repo_path(path: Path, repo_path: Path) -> str:
        try:
            return (
                path.resolve(strict=False)
                .relative_to(repo_path.resolve(strict=False))
                .as_posix()
            )
        except ValueError:
            return path.as_posix()


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
