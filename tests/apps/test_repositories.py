from pathlib import Path

from code_agnostic.apps.codex.config_repository import CodexConfigRepository
from code_agnostic.apps.cursor.config_repository import CursorConfigRepository
from code_agnostic.apps.opencode.config_repository import OpenCodeConfigRepository


def test_opencode_repository_reads_and_writes_mcp(write_json, tmp_path: Path) -> None:
    root = tmp_path / ".config" / "opencode"
    write_json(
        root / "opencode.json",
        {"mcp": {"demo": {"type": "remote", "url": "https://x"}}},
    )

    repo = OpenCodeConfigRepository(root=root)
    assert repo.load_mcp_payload() == {"demo": {"type": "remote", "url": "https://x"}}

    repo.save_mcp_payload({"new": {"type": "local", "command": ["npx"]}})
    assert repo.load_mcp_payload() == {"new": {"type": "local", "command": ["npx"]}}


def test_cursor_repository_reads_and_writes_mcp(write_json, tmp_path: Path) -> None:
    root = tmp_path / ".cursor"
    write_json(root / "mcp.json", {"mcpServers": {"demo": {"command": "npx"}}})

    repo = CursorConfigRepository(root=root)
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

    repo = CodexConfigRepository(root=root)
    assert repo.load_mcp_payload()["demo"]["url"] == "https://x"

    repo.save_mcp_payload({"local": {"command": "uvx", "args": ["demo"]}})
    reloaded = repo.load_mcp_payload()
    assert reloaded["local"]["command"] == "uvx"
    assert reloaded["local"]["args"] == ["demo"]


def test_opencode_repository_load_mcp_when_file_missing(tmp_path: Path) -> None:
    root = tmp_path / ".config" / "opencode"
    repo = OpenCodeConfigRepository(root=root)

    assert repo.load_mcp_payload() == {}


def test_opencode_repository_load_config_when_file_empty(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".config" / "opencode"
    config_path = root / "opencode.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("", encoding="utf-8")

    repo = OpenCodeConfigRepository(root=root)

    assert repo.load_config() == {}


def test_cursor_repository_load_mcp_when_file_missing(tmp_path: Path) -> None:
    root = tmp_path / ".cursor"
    repo = CursorConfigRepository(root=root)

    assert repo.load_mcp_payload() == {}


def test_codex_repository_load_mcp_with_empty_toml(tmp_path: Path) -> None:
    root = tmp_path / ".codex"
    config_path = root / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("", encoding="utf-8")

    repo = CodexConfigRepository(root=root)

    assert repo.load_mcp_payload() == {}


def test_cursor_repository_skills_dir(tmp_path: Path) -> None:
    root = tmp_path / ".cursor"
    repo = CursorConfigRepository(root=root)
    assert repo.skills_dir == root / "skills"


def test_cursor_repository_agents_dir(tmp_path: Path) -> None:
    root = tmp_path / ".cursor"
    repo = CursorConfigRepository(root=root)
    assert repo.agents_dir == root / "agents"


def test_codex_repository_skills_dir(tmp_path: Path) -> None:
    root = tmp_path / ".codex"
    repo = CodexConfigRepository(root=root)
    assert repo.skills_dir == root / "skills"


def test_codex_repository_roundtrip(tmp_path: Path) -> None:
    root = tmp_path / ".codex"
    repo = CodexConfigRepository(root=root)

    payload = {
        "local": {"command": "uvx", "args": ["demo"]},
        "remote": {"url": "https://x"},
    }
    repo.save_mcp_payload(payload)
    reloaded = repo.load_mcp_payload()

    assert reloaded["local"]["command"] == "uvx"
    assert reloaded["local"]["args"] == ["demo"]
    assert reloaded["remote"]["url"] == "https://x"


def test_codex_repository_save_mcp_payload_preserves_other_sections(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".codex"
    config_path = root / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    project_path = str(tmp_path / "repo-a")
    config_path.write_text(
        "\n".join(
            [
                f'[projects."{project_path}"]',
                'trust_level = "trusted"',
                "",
                "[mcp_servers.old]",
                'command = "uvx"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    repo = CodexConfigRepository(root=root)
    repo.save_mcp_payload({"new": {"url": "https://x"}})
    payload = repo.load_config()

    assert payload["projects"][project_path]["trust_level"] == "trusted"
    assert payload["mcp_servers"] == {"new": {"url": "https://x"}}
