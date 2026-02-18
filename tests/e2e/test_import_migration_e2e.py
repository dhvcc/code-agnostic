import json
from pathlib import Path

from code_agnostic.__main__ import cli


def test_import_codex_then_apply_cursor_propagates_mcp(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    codex_root = tmp_path / ".codex"
    codex_root.mkdir(parents=True, exist_ok=True)
    (codex_root / "config.toml").write_text(
        "\n".join(["[mcp_servers.demo]", 'command = "uvx"', ""]),
        encoding="utf-8",
    )

    import_result = cli_runner.invoke(cli, ["import", "apply", "-a", "codex"])
    assert import_result.exit_code == 0

    enable_app("cursor")
    apply_result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])
    assert apply_result.exit_code == 0

    cursor_payload = json.loads(
        (tmp_path / ".cursor" / "mcp.json").read_text(encoding="utf-8")
    )
    assert "demo" in cursor_payload.get("mcpServers", {})
