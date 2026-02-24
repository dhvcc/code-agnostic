from copy import deepcopy
from typing import Any

from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.models import MCPAuthDTO, MCPServerDTO, MCPServerType


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str):
        return [value]
    return []


class OpenCodeMCPMapper(IAppMCPMapper):
    def to_common(self, payload: dict[str, Any]) -> dict[str, MCPServerDTO]:
        mapped: dict[str, MCPServerDTO] = {}
        for name, server in payload.items():
            if not isinstance(server, dict):
                continue

            server_type = server.get("type")
            if server_type == "local" or "command" in server:
                command_parts = _as_list(server.get("command"))
                command = command_parts[0] if command_parts else None
                args = command_parts[1:] if command_parts else []
                if not command:
                    continue
                mapped[name] = MCPServerDTO(
                    name=name,
                    type=MCPServerType.STDIO,
                    command=command,
                    args=args,
                    env={
                        k: str(v) for k, v in (server.get("environment") or {}).items()
                    },
                    headers={
                        k: str(v) for k, v in (server.get("headers") or {}).items()
                    },
                )
                continue

            url = server.get("url")
            if not isinstance(url, str):
                continue

            oauth = server.get("oauth")
            auth: MCPAuthDTO | None = None
            normalized_type = MCPServerType.HTTP
            if isinstance(oauth, dict):
                client_id = oauth.get("clientId")
                client_secret = oauth.get("clientSecret")
                if isinstance(client_id, str) and isinstance(client_secret, str):
                    normalized_type = MCPServerType.OAUTH
                    scope = oauth.get("scope")
                    scopes = [scope] if isinstance(scope, str) else []
                    auth = MCPAuthDTO(
                        client_id=client_id, client_secret=client_secret, scopes=scopes
                    )

            mapped[name] = MCPServerDTO(
                name=name,
                type=normalized_type,
                url=url,
                env={k: str(v) for k, v in (server.get("environment") or {}).items()},
                headers={k: str(v) for k, v in (server.get("headers") or {}).items()},
                auth=auth,
            )
        return mapped

    def from_common(self, servers: dict[str, MCPServerDTO]) -> dict[str, Any]:
        mapped: dict[str, Any] = {}
        for name, server in servers.items():
            out: dict[str, Any] = {}
            if server.type == MCPServerType.STDIO:
                if not server.command:
                    continue
                out["type"] = "local"
                out["command"] = [server.command, *server.args]
            else:
                if not server.url:
                    continue
                out["type"] = "remote"
                out["url"] = server.url
                if server.type == MCPServerType.OAUTH and server.auth is not None:
                    out["oauth"] = {
                        "clientId": server.auth.client_id,
                        "clientSecret": server.auth.client_secret,
                    }
                    if server.auth.scopes:
                        out["oauth"]["scope"] = server.auth.scopes[0]

            out["enabled"] = True

            if server.headers:
                out["headers"] = deepcopy(server.headers)
            if server.env:
                out["environment"] = deepcopy(server.env)

            mapped[name] = out
        return mapped
