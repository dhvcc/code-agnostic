import json
from pathlib import Path

from code_agnostic.__main__ import cli


def test_apply_cursor_target_writes_only_cursor_config(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")

    result = cli_runner.invoke(cli, ["apply", "cursor"])

    assert result.exit_code == 0
    assert (tmp_path / ".cursor" / "mcp.json").exists()
    assert not (tmp_path / ".config" / "opencode" / "opencode.json").exists()


def test_apply_codex_target_writes_toml_config(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    enable_app("codex")

    result = cli_runner.invoke(cli, ["apply", "codex"])

    assert result.exit_code == 0
    codex_config = tmp_path / ".codex" / "config.toml"
    assert codex_config.exists()
    assert "[mcp_servers]" not in codex_config.read_text(encoding="utf-8")


def test_apply_all_with_cursor_and_codex_writes_both(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")
    enable_app("codex")

    result = cli_runner.invoke(cli, ["apply", "all"])

    assert result.exit_code == 0
    cursor_payload = json.loads(
        (tmp_path / ".cursor" / "mcp.json").read_text(encoding="utf-8")
    )
    assert "mcpServers" in cursor_payload
    assert (tmp_path / ".codex" / "config.toml").exists()
