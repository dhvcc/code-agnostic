from pathlib import Path

from click.testing import CliRunner

from llm_sync.cli import cli


def test_apply_opencode_skips_workspace_repo_links(minimal_shared_config: Path, tmp_path: Path) -> None:
    runner = CliRunner()

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / "AGENTS.md").write_text("rules", encoding="utf-8")
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

    add_result = runner.invoke(cli, ["workspaces", "add", "workspace-example", str(workspace_root)])
    assert add_result.exit_code == 0

    apply_result = runner.invoke(cli, ["apply", "opencode"])
    assert apply_result.exit_code == 0

    opencode_config = tmp_path / ".config" / "opencode" / "opencode.json"
    assert opencode_config.exists()

    workspace_link = workspace_root / "service-a" / "AGENTS.md"
    assert not workspace_link.exists()


def test_apply_default_syncs_everything(minimal_shared_config: Path, tmp_path: Path) -> None:
    runner = CliRunner()

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / "AGENTS.md").write_text("rules", encoding="utf-8")
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

    add_result = runner.invoke(cli, ["workspaces", "add", "workspace-example", str(workspace_root)])
    assert add_result.exit_code == 0

    apply_result = runner.invoke(cli, ["apply"])
    assert apply_result.exit_code == 0

    workspace_link = workspace_root / "service-a" / "AGENTS.md"
    assert workspace_link.is_symlink()
    assert workspace_link.resolve() == (workspace_root / "AGENTS.md").resolve()
