"""MCP server management service for add/remove/list operations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from code_agnostic.apps.common.models import MCPServerDTO
from code_agnostic.apps.common.utils import common_mcp_to_dto
from code_agnostic.core.repository import CoreRepository
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.imports.models import ConflictPolicy
from code_agnostic.utils import read_json_safe, write_json


class MCPManagementService:
    def __init__(self, core: CoreRepository) -> None:
        self._core = core

    def _mcp_path(self, workspace: str | None = None) -> Path:
        if workspace is None:
            return self._core.mcp_base_path
        self._ensure_workspace_exists(workspace)
        ws_repo = WorkspaceConfigRepository(
            root=self._core.workspace_config_dir(workspace)
        )
        return ws_repo.mcp_base_path

    def _ensure_workspace_exists(self, workspace: str) -> None:
        names = {item["name"] for item in self._core.load_workspaces()}
        if workspace not in names:
            raise ValueError(f"Workspace not found: {workspace}")

    def _load_raw(self, workspace: str | None = None) -> dict[str, Any]:
        path = self._mcp_path(workspace)
        payload, _ = read_json_safe(path)
        if not isinstance(payload, dict):
            return {"mcpServers": {}}
        if not isinstance(payload.get("mcpServers"), dict):
            payload["mcpServers"] = {}
        return payload

    def _save_raw(self, payload: dict[str, Any], workspace: str | None = None) -> None:
        path = self._mcp_path(workspace)
        write_json(path, payload)

    def list_servers(self, workspace: str | None = None) -> dict[str, MCPServerDTO]:
        raw = self._load_raw(workspace)
        return common_mcp_to_dto(raw.get("mcpServers", {}))

    def add_server(
        self,
        name: str,
        *,
        command: str | None = None,
        args: list[str] | None = None,
        url: str | None = None,
        headers: dict[str, str] | None = None,
        env: dict[str, str] | None = None,
        workspace: str | None = None,
        on_conflict: ConflictPolicy = ConflictPolicy.FAIL,
    ) -> str:
        if command is None and url is None:
            raise ValueError("Must provide either command or url")

        raw = self._load_raw(workspace)
        servers = raw.get("mcpServers", {})

        if name in servers:
            if on_conflict == ConflictPolicy.FAIL:
                raise ValueError(f"Server already exists: {name}")
            if on_conflict == ConflictPolicy.SKIP:
                return f"Skipped (already exists): {name}"

        entry: dict[str, Any] = {}
        if command is not None:
            entry["command"] = command
            if args:
                entry["args"] = args
        elif url is not None:
            entry["url"] = url

        if headers:
            entry["headers"] = headers
        if env:
            entry["env"] = env

        servers[name] = entry
        raw["mcpServers"] = servers
        self._save_raw(raw, workspace)
        return f"Added: {name}"

    def remove_server(self, name: str, workspace: str | None = None) -> bool:
        raw = self._load_raw(workspace)
        servers = raw.get("mcpServers", {})
        if name not in servers:
            return False
        del servers[name]
        raw["mcpServers"] = servers
        self._save_raw(raw, workspace)
        return True
