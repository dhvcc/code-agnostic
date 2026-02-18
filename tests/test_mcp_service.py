"""Tests for MCPManagementService."""

import json
from pathlib import Path

import pytest

from code_agnostic.core.repository import CoreRepository
from code_agnostic.imports.models import ConflictPolicy
from code_agnostic.mcp_service import MCPManagementService


@pytest.fixture
def service(minimal_shared_config: Path) -> MCPManagementService:
    core = CoreRepository()
    return MCPManagementService(core)


def test_list_empty(service: MCPManagementService) -> None:
    servers = service.list_servers()
    assert servers == {}


def test_list_populated(service: MCPManagementService, core_root: Path) -> None:
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "github": {"command": "npx", "args": ["mcp-github"]},
                    "remote": {"url": "https://example.com/mcp"},
                }
            }
        ),
        encoding="utf-8",
    )
    servers = service.list_servers()
    assert "github" in servers
    assert "remote" in servers
    assert servers["github"].command == "npx"
    assert servers["remote"].url == "https://example.com/mcp"


def test_add_stdio_server(service: MCPManagementService, core_root: Path) -> None:
    service.add_server(
        name="github",
        command="npx",
        args=["@modelcontextprotocol/server-github"],
    )
    servers = service.list_servers()
    assert "github" in servers
    assert servers["github"].command == "npx"
    assert servers["github"].args == ["@modelcontextprotocol/server-github"]


def test_add_http_server(service: MCPManagementService) -> None:
    service.add_server(
        name="remote",
        url="https://example.com/mcp",
    )
    servers = service.list_servers()
    assert "remote" in servers
    assert servers["remote"].url == "https://example.com/mcp"


def test_add_with_env_vars(service: MCPManagementService) -> None:
    service.add_server(
        name="github",
        command="npx",
        args=["mcp-github"],
        env={"GITHUB_TOKEN": "${GITHUB_TOKEN}"},
    )
    servers = service.list_servers()
    assert servers["github"].env == {"GITHUB_TOKEN": "${GITHUB_TOKEN}"}


def test_add_with_headers(service: MCPManagementService) -> None:
    service.add_server(
        name="remote",
        url="https://example.com/mcp",
        headers={"Authorization": "Bearer ${TOKEN}"},
    )
    servers = service.list_servers()
    assert servers["remote"].headers == {"Authorization": "Bearer ${TOKEN}"}


def test_add_conflict_fail(service: MCPManagementService) -> None:
    service.add_server(name="demo", command="uvx", args=["tool"])
    with pytest.raises(ValueError, match="already exists"):
        service.add_server(
            name="demo",
            command="uvx",
            args=["other"],
            on_conflict=ConflictPolicy.FAIL,
        )


def test_add_conflict_skip(service: MCPManagementService) -> None:
    service.add_server(name="demo", command="uvx", args=["tool"])
    service.add_server(
        name="demo",
        command="uvx",
        args=["other"],
        on_conflict=ConflictPolicy.SKIP,
    )
    servers = service.list_servers()
    assert servers["demo"].args == ["tool"]


def test_add_conflict_overwrite(service: MCPManagementService) -> None:
    service.add_server(name="demo", command="uvx", args=["tool"])
    service.add_server(
        name="demo",
        command="uvx",
        args=["other"],
        on_conflict=ConflictPolicy.OVERWRITE,
    )
    servers = service.list_servers()
    assert servers["demo"].args == ["other"]


def test_remove_existing(service: MCPManagementService) -> None:
    service.add_server(name="demo", command="uvx", args=["tool"])
    assert service.remove_server("demo") is True
    assert service.list_servers() == {}


def test_remove_nonexistent(service: MCPManagementService) -> None:
    assert service.remove_server("nope") is False


def test_workspace_scoped_add(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    core = CoreRepository()
    core.add_workspace("myws", ws)
    service = MCPManagementService(core)

    service.add_server(
        name="local",
        command="uvx",
        args=["tool"],
        workspace="myws",
    )
    servers = service.list_servers(workspace="myws")
    assert "local" in servers

    global_servers = service.list_servers()
    assert "local" not in global_servers


def test_workspace_scoped_remove(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    core = CoreRepository()
    core.add_workspace("myws", ws)
    service = MCPManagementService(core)

    service.add_server(name="local", command="uvx", args=["tool"], workspace="myws")
    assert service.remove_server("local", workspace="myws") is True
    assert service.list_servers(workspace="myws") == {}


def test_workspace_scoped_list(
    minimal_shared_config: Path, tmp_path: Path, core_root: Path
) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    core = CoreRepository()
    core.add_workspace("myws", ws)
    service = MCPManagementService(core)

    service.add_server(name="ws-srv", url="https://example.com/ws", workspace="myws")
    service.add_server(name="global-srv", url="https://example.com/global")

    ws_servers = service.list_servers(workspace="myws")
    assert "ws-srv" in ws_servers
    assert "global-srv" not in ws_servers

    global_servers = service.list_servers()
    assert "global-srv" in global_servers
    assert "ws-srv" not in global_servers


def test_add_requires_command_or_url(service: MCPManagementService) -> None:
    with pytest.raises(ValueError, match="command.*url"):
        service.add_server(name="broken")


def test_workspace_not_found(service: MCPManagementService) -> None:
    with pytest.raises(ValueError, match="not found"):
        service.list_servers(workspace="nonexistent")
