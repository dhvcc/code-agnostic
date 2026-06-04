from pathlib import Path

from code_agnostic.__main__ import cli
from code_agnostic.constants import AGENTS_FILENAME


def test_status_reports_editor_and_workspace_repo_sync(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path, cli_runner, enable_app
) -> None:
    enable_app("opencode")

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / "service-api" / ".git").mkdir(parents=True)
    (workspace_root / "service-web" / ".git").mkdir(parents=True)
    (workspace_root / "notes").mkdir()

    add_result = cli_runner.invoke(
        cli,
        [
            "workspaces",
            "add",
            "--name",
            "workspace-example",
            "--path",
            str(workspace_root),
        ],
    )
    assert add_result.exit_code == 0

    ws_config_dir = core_root / "workspaces" / "workspace-example"
    (ws_config_dir / AGENTS_FILENAME).write_text("workspace rules", encoding="utf-8")

    initial_status = cli_runner.invoke(cli, ["status"])
    assert initial_status.exit_code == 0
    assert "opencode" in initial_status.output
    assert "drift" in initial_status.output
    assert "workspace-example" in initial_status.output
    assert "service-api" in initial_status.output
    assert "service-web" in initial_status.output
    assert "notes" not in initial_status.output
    assert "needs sync" in initial_status.output

    apply_result = cli_runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    synced_status = cli_runner.invoke(cli, ["status"])
    assert synced_status.exit_code == 0
    assert "opencode" in synced_status.output
    assert "synced" in synced_status.output
    assert "service-api" in synced_status.output
    assert "service-web" in synced_status.output


def test_status_reports_workspace_repo_generated_config_content_drift(
    minimal_shared_config: Path,
    tmp_path: Path,
    core_root: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("opencode")

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    repo = workspace_root / "service-api"
    (repo / ".git").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli,
        [
            "workspaces",
            "add",
            "--name",
            "ws",
            "--path",
            str(workspace_root),
        ],
    )
    assert add_result.exit_code == 0

    ws_config_dir = core_root / "workspaces" / "ws"
    (ws_config_dir / AGENTS_FILENAME).write_text("workspace rules", encoding="utf-8")

    apply_result = cli_runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    (repo / ".opencode" / "opencode.json").write_text("{}\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "ws" in result.output
    assert "service-api" in result.output
    assert "drift" in result.output
    assert "needs sync" in result.output


def test_status_can_scope_to_single_app(
    minimal_shared_config: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")

    result = cli_runner.invoke(cli, ["status", "-a", "cursor"])

    assert result.exit_code == 0
    assert "cursor" in result.output
    assert "opencode" not in result.output


def test_status_reports_error_for_invalid_existing_mcp_source(
    core_root: Path, cli_runner, enable_app
) -> None:
    enable_app("codex")
    source = core_root / "config" / "mcp.base.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("{}", encoding="utf-8")

    result = cli_runner.invoke(cli, ["status", "-a", "codex"])

    assert result.exit_code != 0
    assert "codex" in result.output
    assert "error" in result.output
    assert "Invalid config schema" in result.output
    assert "synced" not in result.output


def test_status_app_scope_ignores_other_app_config_errors(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("codex")
    enable_app("opencode")
    opencode_config = tmp_path / ".config" / "opencode" / "opencode.json"
    opencode_config.parent.mkdir(parents=True, exist_ok=True)
    opencode_config.write_text("[]", encoding="utf-8")

    result = cli_runner.invoke(cli, ["status", "-a", "codex"])

    assert result.exit_code == 0
    assert "codex" in result.output
    assert "opencode" not in result.output
    assert "opencode.json" not in result.output
    assert "cannot evaluate" not in result.output


def test_status_returns_nonzero_for_workspace_error(tmp_path: Path, cli_runner) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    add_result = cli_runner.invoke(
        cli,
        [
            "workspaces",
            "add",
            "--name",
            "missingws",
            "--path",
            str(workspace_root),
        ],
    )
    assert add_result.exit_code == 0
    workspace_root.rmdir()

    result = cli_runner.invoke(cli, ["status"])

    assert result.exit_code != 0
    assert "missingws" in result.output
    assert "error" in result.output
    assert "workspace path" in result.output


def test_status_app_scope_returns_nonzero_for_workspace_error(
    tmp_path: Path, cli_runner, enable_app
) -> None:
    enable_app("codex")
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    add_result = cli_runner.invoke(
        cli,
        [
            "workspaces",
            "add",
            "--name",
            "missingws",
            "--path",
            str(workspace_root),
        ],
    )
    assert add_result.exit_code == 0
    workspace_root.rmdir()

    result = cli_runner.invoke(cli, ["status", "-a", "codex"])

    assert result.exit_code != 0
    assert "codex" in result.output
    assert "missingws" in result.output
    assert "workspace path" in result.output
