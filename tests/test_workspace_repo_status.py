"""Tests for workspace repo status detection.

Reproduction tests for the bug where code-agnostic status incorrectly reports
"needs sync" (drift) for repos where the sync has been applied successfully.

The root cause: _repo_sync_status checks for symlinks (is_symlink()) but the
planner creates regular files for MCP configs and skill/agent entries.
"""

from pathlib import Path

from code_agnostic.apps.codex.config_repository import CodexConfigRepository
from code_agnostic.apps.codex.mapper import CodexMCPMapper
from code_agnostic.apps.codex.schema_repository import CodexSchemaRepository
from code_agnostic.apps.codex.service import CodexConfigService
from code_agnostic.apps.opencode.config_repository import OpenCodeConfigRepository
from code_agnostic.apps.opencode.mapper import OpenCodeMCPMapper
from code_agnostic.apps.opencode.schema_repository import OpenCodeSchemaRepository
from code_agnostic.apps.opencode.service import OpenCodeConfigService
from code_agnostic.core.repository import CoreRepository
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.executor import SyncExecutor
from code_agnostic.models import RepoSyncStatus, WorkspaceSyncStatus
from code_agnostic.planner import SyncPlanner
from code_agnostic.status import StatusService


def _opencode_service(
    core: CoreRepository, opencode_root: Path
) -> OpenCodeConfigService:
    return OpenCodeConfigService(
        repository=OpenCodeConfigRepository(root=opencode_root),
        mapper=OpenCodeMCPMapper(),
        schema_repository=OpenCodeSchemaRepository(),
        base_config_path=core.opencode_base_path,
    )


def _codex_service(codex_root: Path) -> CodexConfigService:
    return CodexConfigService(
        repository=CodexConfigRepository(root=codex_root),
        mapper=CodexMCPMapper(),
        schema_repository=CodexSchemaRepository(),
    )


class TestWorkspaceRepoStatusBugRepro:
    """Reproduction tests for workspace repo status false-positive drift detection."""

    def test_repo_status_reports_synced_after_mcp_sync(
        self,
        minimal_shared_config: Path,
        core_root: Path,
        tmp_path: Path,
        write_json,
    ) -> None:
        """Reproduction: after apply, repos should report SYNCED not NEEDS_SYNC.

        Bug: _repo_sync_status checks is_symlink() but planner creates regular files.
        """
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        (workspace_root / "repo-a" / ".git").mkdir(parents=True)

        core = CoreRepository(core_root)
        core.add_workspace("myws", workspace_root)

        ws_config = core.workspace_config_dir("myws")
        write_json(
            ws_config / "mcp.base.json",
            {"mcpServers": {"test-server": {"url": "https://test.example.com/mcp"}}},
        )

        opencode_root = tmp_path / ".config" / "opencode"
        plan = SyncPlanner(
            core=core, app_services=[_opencode_service(core, opencode_root)]
        ).build()
        SyncExecutor(core=core).execute(plan)

        ws_source = WorkspaceConfigRepository(root=ws_config)
        repo_path = workspace_root / "repo-a"

        from code_agnostic.apps.app_id import app_metadata

        opencode_meta = _opencode_service(core, opencode_root)

        from code_agnostic.models import WorkspaceRepoStatusRow

        repo_status: WorkspaceRepoStatusRow = StatusService._repo_sync_status(
            repo_path=repo_path,
            ws_source=ws_source,
            app_metas=[app_metadata(opencode_meta.app_id)],
        )

        assert repo_status.status == RepoSyncStatus.SYNCED, (
            f"Expected SYNCED but got {repo_status.status}: {repo_status.detail}"
        )

    def test_repo_status_reports_synced_after_skills_sync(
        self,
        minimal_shared_config: Path,
        core_root: Path,
        tmp_path: Path,
    ) -> None:
        """Reproduction: workspace skills synced to repos should report SYNCED.

        Bug: _repo_sync_status checks is_symlink() but skills are regular compiled files.
        """
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        (workspace_root / "repo-a" / ".git").mkdir(parents=True)

        core = CoreRepository(core_root)
        core.add_workspace("myws", workspace_root)

        ws_config = core.workspace_config_dir("myws")
        (ws_config / "skills" / "my-skill").mkdir(parents=True)
        (ws_config / "skills" / "my-skill" / "SKILL.md").write_text(
            "shared skill", encoding="utf-8"
        )

        opencode_root = tmp_path / ".config" / "opencode"
        plan = SyncPlanner(
            core=core, app_services=[_opencode_service(core, opencode_root)]
        ).build()
        SyncExecutor(core=core).execute(plan)

        ws_source = WorkspaceConfigRepository(root=ws_config)
        repo_path = workspace_root / "repo-a"

        from code_agnostic.apps.app_id import app_metadata
        from code_agnostic.models import WorkspaceRepoStatusRow

        opencode_meta = _opencode_service(core, opencode_root)
        repo_status: WorkspaceRepoStatusRow = StatusService._repo_sync_status(
            repo_path=repo_path,
            ws_source=ws_source,
            app_metas=[app_metadata(opencode_meta.app_id)],
        )

        assert repo_status.status == RepoSyncStatus.SYNCED, (
            f"Expected SYNCED but got {repo_status.status}: {repo_status.detail}"
        )

    def test_workspace_status_reports_synced_after_full_apply(
        self,
        minimal_shared_config: Path,
        core_root: Path,
        tmp_path: Path,
        write_json,
    ) -> None:
        """Full end-to-end: after apply, workspace should report SYNCED not drift."""
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        (workspace_root / "repo-a" / ".git").mkdir(parents=True)

        core = CoreRepository(core_root)
        core.add_workspace("myws", workspace_root)

        ws_config = core.workspace_config_dir("myws")
        write_json(
            ws_config / "mcp.base.json",
            {"mcpServers": {"test-server": {"url": "https://test.example.com/mcp"}}},
        )
        (ws_config / "skills" / "my-skill").mkdir(parents=True)
        (ws_config / "skills" / "my-skill" / "SKILL.md").write_text(
            "s", encoding="utf-8"
        )

        opencode_root = tmp_path / ".config" / "opencode"
        plan = SyncPlanner(
            core=core, app_services=[_opencode_service(core, opencode_root)]
        ).build()
        SyncExecutor(core=core).execute(plan)

        ws_rows = StatusService().build_workspace_status(
            source_repo=core,
            app_services=[_opencode_service(core, opencode_root)],
        )
        assert len(ws_rows) == 1
        assert ws_rows[0].status == WorkspaceSyncStatus.SYNCED, (
            f"Expected SYNCED but got {ws_rows[0].status}: {ws_rows[0].detail}"
        )
        assert len(ws_rows[0].repos) == 1
        assert ws_rows[0].repos[0].status == RepoSyncStatus.SYNCED

    def test_repo_status_codex_and_opencode_both_synced_after_apply(
        self,
        minimal_shared_config: Path,
        core_root: Path,
        tmp_path: Path,
        write_json,
    ) -> None:
        """Both codex and opencode repos should report SYNCED after apply.

        The status check incorrectly expected symlinks for both apps' MCP configs.
        """
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        (workspace_root / "repo-a" / ".git").mkdir(parents=True)

        core = CoreRepository(core_root)
        core.add_workspace("myws", workspace_root)

        ws_config = core.workspace_config_dir("myws")
        write_json(
            ws_config / "mcp.base.json",
            {"mcpServers": {"test-server": {"command": "npx", "args": ["test"]}}},
        )

        opencode_root = tmp_path / ".config" / "opencode"
        codex_root = tmp_path / ".codex"
        plan = SyncPlanner(
            core=core,
            app_services=[
                _opencode_service(core, opencode_root),
                _codex_service(codex_root),
            ],
        ).build()
        SyncExecutor(core=core).execute(plan)

        ws_source = WorkspaceConfigRepository(root=ws_config)
        repo_path = workspace_root / "repo-a"

        from code_agnostic.apps.app_id import app_metadata
        from code_agnostic.models import WorkspaceRepoStatusRow

        app_metas = [
            app_metadata(_opencode_service(core, opencode_root).app_id),
            app_metadata(_codex_service(codex_root).app_id),
        ]
        repo_status: WorkspaceRepoStatusRow = StatusService._repo_sync_status(
            repo_path=repo_path,
            ws_source=ws_source,
            app_metas=app_metas,
        )

        assert repo_status.status == RepoSyncStatus.SYNCED, (
            f"Expected SYNCED but got {repo_status.status}: {repo_status.detail}"
        )
