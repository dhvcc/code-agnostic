from copy import deepcopy
from typing import Any

from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.models import MCPServerDTO, MCPServerType


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


def _as_str_dict(value: Any) -> dict[str, str]:
    return {str(k): str(v) for k, v in value.items()} if isinstance(value, dict) else {}


def _timeout(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


class ClaudeMCPMapper(IAppMCPMapper):
    def to_common(self, payload: dict[str, Any]) -> dict[str, MCPServerDTO]:
        mapped: dict[str, MCPServerDTO] = {}
        for name, server in payload.items():
            if not isinstance(server, dict):
                continue

            server_type = server.get("type")
            command = server.get("command")
            if server_type == "stdio" or isinstance(command, str):
                if not isinstance(command, str) or not command:
                    continue
                mapped[name] = MCPServerDTO(
                    name=name,
                    type=MCPServerType.STDIO,
                    command=command,
                    args=_as_list(server.get("args")),
                    env=_as_str_dict(server.get("env")),
                    headers=_as_str_dict(server.get("headers")),
                    timeout_ms=_timeout(server.get("timeout")),
                )
                continue

            url = server.get("url")
            if not isinstance(url, str) or not url:
                continue
            mapped[name] = MCPServerDTO(
                name=name,
                type=MCPServerType.HTTP,
                url=url,
                env=_as_str_dict(server.get("env")),
                headers=_as_str_dict(server.get("headers")),
                timeout_ms=_timeout(server.get("timeout")),
            )
        return mapped

    def from_common(self, servers: dict[str, MCPServerDTO]) -> dict[str, Any]:
        mapped: dict[str, Any] = {}
        for name, server in servers.items():
            out: dict[str, Any] = {}
            if server.type == MCPServerType.STDIO:
                if not server.command:
                    continue
                out["type"] = "stdio"
                out["command"] = server.command
                if server.args:
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
