from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from code_agnostic.apps.sync.base import IAppConfigRepository, IAppMCPMapper
from code_agnostic.apps.sync.models import MCPAuthDTO, MCPServerDTO, MCPServerType
from code_agnostic.errors import InvalidConfigSchemaError, InvalidJsonFormatError
from code_agnostic.utils import read_json_safe, write_json


class CursorMCPMapper(IAppMCPMapper):
    def to_common(self, payload: dict[str, Any]) -> dict[str, MCPServerDTO]:
        mapped: dict[str, MCPServerDTO] = {}
        for name, server in payload.items():
            if not isinstance(server, dict):
                continue

            if isinstance(server.get("command"), str):
                mapped[name] = MCPServerDTO(
                    name=name,
                    type=MCPServerType.STDIO,
                    command=server["command"],
                    args=[
                        str(item)
                        for item in server.get("args", [])
                        if isinstance(item, (str, int, float, bool))
                    ],
                    env={k: str(v) for k, v in (server.get("env") or {}).items()},
                    headers={
                        k: str(v) for k, v in (server.get("headers") or {}).items()
                    },
                )
                continue

            url = server.get("url")
            if not isinstance(url, str):
                continue

            auth_obj = server.get("auth")
            auth: MCPAuthDTO | None = None
            server_type = MCPServerType.HTTP
            if isinstance(auth_obj, dict):
                client_id = auth_obj.get("CLIENT_ID") or auth_obj.get("client_id")
                client_secret = auth_obj.get("CLIENT_SECRET") or auth_obj.get(
                    "client_secret"
                )
                scopes = auth_obj.get("scopes")
                normalized_scopes = (
                    [str(item) for item in scopes] if isinstance(scopes, list) else []
                )
                if isinstance(client_id, str) and isinstance(client_secret, str):
                    server_type = MCPServerType.OAUTH
                    auth = MCPAuthDTO(
                        client_id=client_id,
                        client_secret=client_secret,
                        scopes=normalized_scopes,
                    )

            mapped[name] = MCPServerDTO(
                name=name,
                type=server_type,
                url=url,
                headers={k: str(v) for k, v in (server.get("headers") or {}).items()},
                env={k: str(v) for k, v in (server.get("env") or {}).items()},
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
                out["command"] = server.command
                if server.args:
                    out["args"] = deepcopy(server.args)
            else:
                if not server.url:
                    continue
                out["url"] = server.url
                if server.type == MCPServerType.OAUTH and server.auth is not None:
                    out["auth"] = {
                        "CLIENT_ID": server.auth.client_id,
                        "CLIENT_SECRET": server.auth.client_secret,
                    }
                    if server.auth.scopes:
                        out["auth"]["scopes"] = deepcopy(server.auth.scopes)

            if server.headers:
                out["headers"] = deepcopy(server.headers)
            if server.env:
                out["env"] = deepcopy(server.env)
            mapped[name] = out
        return mapped


class CursorRepository(IAppConfigRepository):
    def __init__(self, root: Optional[Path] = None) -> None:
        self._root = root or (Path.home() / ".cursor")

    @property
    def root(self) -> Path:
        return self._root

    @property
    def config_path(self) -> Path:
        return self.root / "mcp.json"

    def load_config(self) -> dict[str, Any]:
        payload, error = read_json_safe(self.config_path)
        if error is not None:
            raise InvalidJsonFormatError(self.config_path, error)
        if payload is None:
            return {}
        if not isinstance(payload, dict):
            raise InvalidConfigSchemaError(self.config_path, "must be a JSON object")
        return payload

    def save_config(self, payload: dict[str, Any]) -> None:
        write_json(self.config_path, payload)

    def load_mcp_payload(self) -> dict[str, Any]:
        payload = self.load_config()
        mcp = payload.get("mcpServers")
        if isinstance(mcp, dict):
            return mcp
        return {}

    def save_mcp_payload(self, payload: dict[str, Any]) -> None:
        config = self.load_config()
        config["mcpServers"] = payload
        self.save_config(config)
