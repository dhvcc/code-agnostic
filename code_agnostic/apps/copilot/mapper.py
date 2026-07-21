from copy import deepcopy
from pathlib import Path
from typing import Any

from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.mapper_utils import as_str_dict
from code_agnostic.apps.common.models import MCPServerDTO, MCPServerType
from code_agnostic.errors import InvalidConfigSchemaError


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float, bool))]


def _timeout_ms(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None
    return None


class CopilotMCPMapper(IAppMCPMapper):
    def to_common(self, payload: dict[str, Any]) -> dict[str, MCPServerDTO]:
        mapped: dict[str, MCPServerDTO] = {}
        for name, server in payload.items():
            if not isinstance(server, dict):
                continue

            server_type = server.get("type")
            command = server.get("command")
            if server_type in ("local", "stdio") or isinstance(command, str):
                if not isinstance(command, str):
                    continue
                mapped[name] = MCPServerDTO(
                    name=name,
                    type=MCPServerType.STDIO,
                    command=command,
                    args=_as_string_list(server.get("args")),
                    timeout_ms=_timeout_ms(server.get("timeout")),
                    env=as_str_dict(server.get("env")),
                    headers=as_str_dict(server.get("headers")),
                )
                continue

            url = server.get("url")
            if server_type in ("http", "sse") and isinstance(url, str):
                mapped[name] = MCPServerDTO(
                    name=name,
                    type=MCPServerType.HTTP,
                    url=url,
                    timeout_ms=_timeout_ms(server.get("timeout")),
                    env=as_str_dict(server.get("env")),
                    headers=as_str_dict(server.get("headers")),
                )
        return mapped

    def from_common(self, servers: dict[str, MCPServerDTO]) -> dict[str, Any]:
        mapped: dict[str, Any] = {}
        for name, server in servers.items():
            if server.type == MCPServerType.OAUTH or server.auth is not None:
                raise InvalidConfigSchemaError(
                    Path(f"mcpServers/{name}"),
                    "GitHub Copilot MCP does not support canonical OAuth servers",
                )

            out: dict[str, Any] = {"tools": ["*"]}
            if server.type == MCPServerType.STDIO:
                if not server.command:
                    continue
                out["type"] = "local"
                out["command"] = server.command
                out["args"] = deepcopy(server.args)
            else:
                if not server.url:
                    continue
                out["type"] = "http"
                out["url"] = server.url

            if server.env:
                out["env"] = deepcopy(server.env)
            if server.headers:
                out["headers"] = deepcopy(server.headers)
            if server.timeout_ms is not None:
                out["timeout"] = server.timeout_ms

            mapped[name] = out
        return mapped
