import json
from pathlib import Path

from code_agnostic.__main__ import cli


def test_apply_cursor_target_writes_only_cursor_config(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")

    result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])

    assert result.exit_code == 0
    assert (tmp_path / ".cursor" / "mcp.json").exists()
    assert not (tmp_path / ".config" / "opencode" / "opencode.json").exists()


def test_apply_codex_target_writes_toml_config(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    enable_app("codex")

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code == 0
    codex_config = tmp_path / ".codex" / "config.toml"
    assert codex_config.exists()
    assert "[mcp_servers]" not in codex_config.read_text(encoding="utf-8")


def test_apply_all_with_cursor_and_codex_writes_both(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")
    enable_app("codex")

    result = cli_runner.invoke(cli, ["apply", "-a", "all"])

    assert result.exit_code == 0
    cursor_payload = json.loads(
        (tmp_path / ".cursor" / "mcp.json").read_text(encoding="utf-8")
    )
    assert "mcpServers" in cursor_payload
    assert (tmp_path / ".codex" / "config.toml").exists()


def test_apply_cursor_target_does_not_apply_workspace_links(
    minimal_shared_config: Path,
    tmp_path: Path,
    core_root: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

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

    # Create workspace config with rules in rules/ directory
    ws_config_dir = core_root / "workspaces" / "workspace-example"
    (ws_config_dir / "rules").mkdir(parents=True, exist_ok=True)
    (ws_config_dir / "rules" / "shared.md").write_text("rules", encoding="utf-8")

    apply_result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])
    assert apply_result.exit_code == 0

    repo_rules_link = workspace_root / "service-a" / ".cursor" / "rules"
    assert not repo_rules_link.exists()


def test_apply_cursor_aborts_on_invalid_cursor_json(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")
    cursor_path = tmp_path / ".cursor" / "mcp.json"
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text("{oops", encoding="utf-8")

    result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])

    assert result.exit_code != 0
    assert "Apply aborted" in result.output
    assert "Invalid JSON format" in result.output


def test_apply_codex_aborts_on_invalid_toml(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("codex")
    codex_path = tmp_path / ".codex" / "config.toml"
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text("[mcp_servers.demo\nurl='x'", encoding="utf-8")

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code != 0
    assert "Apply aborted" in result.output


def test_apply_cursor_aborts_on_invalid_schema_key(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")
    cursor_path = tmp_path / ".cursor" / "mcp.json"
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "broken": {"url": "https://example.com/mcp", "badKey": True}
                }
            }
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])

    assert result.exit_code != 0
    assert "Invalid config schema" in result.output


def test_apply_codex_aborts_on_invalid_schema_key(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("codex")
    codex_path = tmp_path / ".codex" / "config.toml"
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text(
        "\n".join(
            [
                "[mcp_servers.demo]",
                'url = "https://example.com/mcp"',
                'bad_key = "boom"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code != 0
    assert "Invalid config schema" in result.output
