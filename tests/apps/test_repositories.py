from pathlib import Path

from code_agnostic.apps.sync.codex import CodexRepository
from code_agnostic.apps.sync.cursor import CursorRepository
from code_agnostic.apps.sync.opencode import OpenCodeRepository


def test_opencode_repository_reads_and_writes_mcp(write_json, tmp_path: Path) -> None:
    root = tmp_path / ".config" / "opencode"
    write_json(
        root / "opencode.json",
        {"mcp": {"demo": {"type": "remote", "url": "https://x"}}},
    )

    repo = OpenCodeRepository(root=root)
    assert repo.load_mcp_payload() == {"demo": {"type": "remote", "url": "https://x"}}

    repo.save_mcp_payload({"new": {"type": "local", "command": ["npx"]}})
    assert repo.load_mcp_payload() == {"new": {"type": "local", "command": ["npx"]}}


def test_cursor_repository_reads_and_writes_mcp(write_json, tmp_path: Path) -> None:
    root = tmp_path / ".cursor"
    write_json(root / "mcp.json", {"mcpServers": {"demo": {"command": "npx"}}})

    repo = CursorRepository(root=root)
    assert repo.load_mcp_payload() == {"demo": {"command": "npx"}}

    repo.save_mcp_payload({"http": {"url": "https://x"}})
    assert repo.load_mcp_payload() == {"http": {"url": "https://x"}}


def test_codex_repository_reads_and_writes_mcp(tmp_path: Path) -> None:
    root = tmp_path / ".codex"
    config_path = root / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "[mcp_servers.demo]",
                'url = "https://x"',
                "",
                "[mcp_servers.demo.http_headers]",
                'X-Test = "1"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    repo = CodexRepository(root=root)
    assert repo.load_mcp_payload()["demo"]["url"] == "https://x"

    repo.save_mcp_payload({"local": {"command": "uvx", "args": ["demo"]}})
    reloaded = repo.load_mcp_payload()
    assert reloaded["local"]["command"] == "uvx"
    assert reloaded["local"]["args"] == ["demo"]
