import json
from pathlib import Path

from code_agnostic.apps.claude.config_repository import ClaudeConfigRepository
from code_agnostic.apps.claude.mapper import ClaudeMCPMapper
from code_agnostic.apps.claude.service import ClaudeConfigService
from code_agnostic.apps.common.models import MCPServerDTO, MCPServerType
from code_agnostic.models import ActionStatus


def _service(root: Path) -> ClaudeConfigService:
    return ClaudeConfigService(
        repository=ClaudeConfigRepository(
            root=root,
            config_path=root.parent / ".claude.json",
        ),
        mapper=ClaudeMCPMapper(),
    )


def test_claude_service_preserves_unmanaged_global_config(tmp_path: Path) -> None:
    config_path = tmp_path / ".claude.json"
    config_path.write_text(
        json.dumps(
            {
                "theme": "dark",
                "mcpServers": {
                    "personal": {"type": "http", "url": "https://p.example/mcp"}
                },
            }
        ),
        encoding="utf-8",
    )

    action = _service(tmp_path / ".claude").build_action(
        {
            "managed": MCPServerDTO(
                name="managed",
                type=MCPServerType.STDIO,
                command="uvx",
                args=["managed"],
            )
        }
    )

    assert action.status == ActionStatus.UPDATE
    assert action.payload["theme"] == "dark"
    assert action.payload["mcpServers"]["personal"] == {
        "type": "http",
        "url": "https://p.example/mcp",
    }
    assert action.payload["mcpServers"]["managed"] == {
        "type": "stdio",
        "command": "uvx",
        "args": ["managed"],
    }


def test_claude_service_builds_project_mcp_action(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    action = _service(tmp_path / ".claude").build_project_mcp_action(
        {
            repo: {
                "repo-server": MCPServerDTO(
                    name="repo-server",
                    type=MCPServerType.HTTP,
                    url="https://example.com/mcp",
                )
            }
        }
    )

    assert action.status == ActionStatus.CREATE
    assert action.path == tmp_path / ".claude.json"
    assert action.payload["projects"][str(repo.resolve())]["mcpServers"] == {
        "repo-server": {"type": "http", "url": "https://example.com/mcp"}
    }
