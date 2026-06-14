from pathlib import Path
import json

from code_agnostic.__main__ import cli
from code_agnostic.core.repository import CoreRepository
from code_agnostic.executor import SyncExecutor
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan


def test_restore_replays_active_global_revision(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
) -> None:
    target = tmp_path / "generated.txt"
    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=target,
                status=ActionStatus.CREATE,
                detail="create file",
                payload="hello\n",
                scope="app:test:text",
                app="opencode",
            )
        ],
        errors=[],
        skipped=[],
    )
    SyncExecutor(core=CoreRepository(core_root)).execute(plan)
    target.write_text("broken\n", encoding="utf-8")
    (core_root / ".sync-state.json").write_text('{"broken": true}\n', encoding="utf-8")

    result = cli_runner.invoke(cli, ["restore"])

    assert result.exit_code == 0
    assert result.output.startswith("Restored revision ")
    assert target.read_text(encoding="utf-8") == "hello\n"
    assert json.loads((core_root / ".sync-state.json").read_text(encoding="utf-8"))[
        "managed_paths"
    ]["app:test:text"] == [str(target)]


def test_restore_replays_active_workspace_revision(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
) -> None:
    core = CoreRepository(core_root)
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    core.add_workspace("team", workspace_root)

    target = workspace_root / "AGENTS.md"
    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=target,
                status=ActionStatus.CREATE,
                detail="create workspace file",
                payload="workspace\n",
                scope="rules",
                app="workspace",
                workspace="team",
            )
        ],
        errors=[],
        skipped=[],
    )
    SyncExecutor(core=core).execute(plan)
    target.unlink()
    (core_root / "workspaces" / "team" / ".sync-state.json").write_text(
        '{"broken": true}\n', encoding="utf-8"
    )

    result = cli_runner.invoke(cli, ["restore", "--workspace", "team"])

    assert result.exit_code == 0
    assert result.output.startswith("Restored revision ")
    assert target.read_text(encoding="utf-8") == "workspace\n"
    assert json.loads(
        (core_root / "workspaces" / "team" / ".sync-state.json").read_text(
            encoding="utf-8"
        )
    )["managed_paths"]["rules"] == [str(target)]


def test_restore_replays_active_project_revision(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
) -> None:
    core = CoreRepository(core_root)
    project_root = tmp_path / "service-api"
    project_root.mkdir()
    core.add_project("service-api", project_root)

    target = project_root / ".agents" / "skills" / "project-tool" / "SKILL.md"
    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=target,
                status=ActionStatus.CREATE,
                detail="create project skill",
                payload="project\n",
                scope="project:service-api:codex:skill:project-tool",
                app="codex",
                project="service-api",
            )
        ],
        errors=[],
        skipped=[],
    )
    SyncExecutor(core=core).execute(plan)
    target.write_text("broken\n", encoding="utf-8")
    (core_root / "projects" / "service-api" / ".sync-state.json").write_text(
        '{"broken": true}\n', encoding="utf-8"
    )

    result = cli_runner.invoke(cli, ["restore", "--project", "service-api"])

    assert result.exit_code == 0
    assert result.output.startswith("Restored revision ")
    assert target.read_text(encoding="utf-8") == "project\n"
    assert json.loads(
        (core_root / "projects" / "service-api" / ".sync-state.json").read_text(
            encoding="utf-8"
        )
    )["managed_paths"]["project:service-api:codex:skill:project-tool"] == [str(target)]


def test_restore_rejects_workspace_and_project_together(
    minimal_shared_config: Path,
    cli_runner,
) -> None:
    result = cli_runner.invoke(
        cli, ["restore", "--workspace", "team", "--project", "service-api"]
    )

    assert result.exit_code != 0
    assert "Choose only one scope" in result.output


def test_restore_repairs_pending_global_revision(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
) -> None:
    target = tmp_path / "generated.txt"
    plan = SyncPlan(
        actions=[
            Action(
                kind=ActionKind.WRITE_TEXT,
                path=target,
                status=ActionStatus.CREATE,
                detail="create file",
                payload="hello\n",
                scope="app:test:text",
                app="opencode",
            )
        ],
        errors=[],
        skipped=[],
    )
    SyncExecutor(core=CoreRepository(core_root)).execute(plan)
    target.write_text("broken\n", encoding="utf-8")
    pending_path = core_root / ".sync-revisions" / "pending.json"
    pending_path.write_text('{"revision_id": "pending"}\n', encoding="utf-8")

    result = cli_runner.invoke(cli, ["restore"])

    assert result.exit_code == 0
    assert target.read_text(encoding="utf-8") == "hello\n"
    assert not pending_path.exists()
