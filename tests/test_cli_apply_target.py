from pathlib import Path

from llm_sync.__main__ import cli
from llm_sync.constants import AGENTS_FILENAME


def test_apply_opencode_skips_workspace_repo_links(minimal_shared_config: Path, tmp_path: Path, cli_runner) -> None:

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / AGENTS_FILENAME).write_text("rules", encoding="utf-8")
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

    add_result = cli_runner.invoke(cli, ["workspaces", "add", "workspace-example", str(workspace_root)])
    assert add_result.exit_code == 0

    apply_result = cli_runner.invoke(cli, ["apply", "opencode"])
    assert apply_result.exit_code == 0

    opencode_config = tmp_path / ".config" / "opencode" / "opencode.json"
    assert opencode_config.exists()

    workspace_link = workspace_root / "service-a" / AGENTS_FILENAME
    assert not workspace_link.exists()


def test_apply_default_syncs_everything(minimal_shared_config: Path, tmp_path: Path, cli_runner) -> None:

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / AGENTS_FILENAME).write_text("rules", encoding="utf-8")
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

    add_result = cli_runner.invoke(cli, ["workspaces", "add", "workspace-example", str(workspace_root)])
    assert add_result.exit_code == 0

    apply_result = cli_runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    workspace_link = workspace_root / "service-a" / AGENTS_FILENAME
    assert workspace_link.is_symlink()
    assert workspace_link.resolve() == (workspace_root / AGENTS_FILENAME).resolve()


def test_apply_aborts_on_invalid_opencode_json(
    minimal_shared_config: Path,
    opencode_root: Path,
    cli_runner,
) -> None:
    config_path = opencode_root / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{oops", encoding="utf-8")

    result = cli_runner.invoke(cli, ["apply"])

    assert result.exit_code != 0
    assert "Apply aborted" in result.output
    assert "Invalid JSON format" in result.output
    assert "opencode" in result.output
