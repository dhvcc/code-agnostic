from typing import Any

from code_agnostic.apps.app_id import AppId, app_ids_by_capability
from code_agnostic.apps.common.models import MCPAuthDTO, MCPServerDTO, MCPServerType
from code_agnostic.constants import (
    MCP_APP_EXCLUDE_PREFIX,
    MCP_APP_INCLUDE_PREFIX,
    MCP_APP_TARGET_SEPARATOR,
)


_TARGETABLE_APP_NAMES = {
    app_id.value for app_id in app_ids_by_capability(targetable=True)
}


def _split_app_targeted_key(key: str) -> tuple[str, str, str] | None:
    if not key or key[0] not in (MCP_APP_INCLUDE_PREFIX, MCP_APP_EXCLUDE_PREFIX):
        return None

    marker = key[0]
    remainder = key[1:]
    app_name, separator, server_name = remainder.partition(MCP_APP_TARGET_SEPARATOR)
    if (
        separator != MCP_APP_TARGET_SEPARATOR
        or not server_name
        or app_name not in _TARGETABLE_APP_NAMES
    ):
        return None
    return marker, app_name, server_name


def mcp_servers_for_app(
    mcp_servers: dict[str, Any], app_id: AppId | str
) -> dict[str, Any]:
    target = app_id.value if isinstance(app_id, AppId) else app_id
    filtered: dict[str, Any] = {}
    for name, raw in mcp_servers.items():
        targeted = _split_app_targeted_key(name)
        if targeted is None:
            filtered[name] = raw
            continue

        marker, app_name, server_name = targeted
        if marker == MCP_APP_INCLUDE_PREFIX and app_name == target:
            filtered[server_name] = raw
        elif marker == MCP_APP_EXCLUDE_PREFIX and app_name != target:
            filtered[server_name] = raw
    return filtered


def _coerce_timeout_ms(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 else None
    return None


def common_mcp_to_dto(mcp_servers: dict[str, Any]) -> dict[str, MCPServerDTO]:
    mapped: dict[str, MCPServerDTO] = {}
    for name, raw in mcp_servers.items():
        if not isinstance(raw, dict):
            continue

        command = raw.get("command")
        args = raw.get("args")
        url = raw.get("url")
        timeout_ms = _coerce_timeout_ms(raw.get("timeout"))

        headers = raw.get("headers")
        env = raw.get("env")
        if not isinstance(env, dict):
            env = raw.get("environment")
        auth_obj = raw.get("auth")

        auth: MCPAuthDTO | None = None
        if isinstance(auth_obj, dict):
            client_id = auth_obj.get("client_id")
            client_secret = auth_obj.get("client_secret")
            scopes = auth_obj.get("scopes")
            if isinstance(client_id, str) and isinstance(client_secret, str):
                auth = MCPAuthDTO(
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=[str(item) for item in scopes]
                    if isinstance(scopes, list)
                    else [],
                )

        if isinstance(command, str):
            mapped[name] = MCPServerDTO(
                name=name,
                type=MCPServerType.STDIO,
                command=command,
                args=[str(item) for item in args] if isinstance(args, list) else [],
                timeout_ms=timeout_ms,
                headers={str(k): str(v) for k, v in headers.items()}
                if isinstance(headers, dict)
                else {},
                env={str(k): str(v) for k, v in env.items()}
                if isinstance(env, dict)
                else {},
            )
            continue

        if isinstance(url, str):
            mapped[name] = MCPServerDTO(
                name=name,
                type=MCPServerType.OAUTH if auth is not None else MCPServerType.HTTP,
                url=url,
                timeout_ms=timeout_ms,
                headers={str(k): str(v) for k, v in headers.items()}
                if isinstance(headers, dict)
                else {},
                env={str(k): str(v) for k, v in env.items()}
                if isinstance(env, dict)
                else {},
                auth=auth,
            )

    return mapped


def dto_to_common_mcp(servers: dict[str, MCPServerDTO]) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for name in sorted(servers):
        server = servers[name]
        item: dict[str, Any] = {}

        if server.command:
            item["command"] = server.command
            item["args"] = [str(arg) for arg in server.args]
        elif server.url:
            item["url"] = server.url
        else:
            continue

        if server.timeout_ms is not None:
            item["timeout"] = server.timeout_ms

        if server.headers:
            item["headers"] = {str(k): str(v) for k, v in server.headers.items()}
        if server.env:
            item["env"] = {str(k): str(v) for k, v in server.env.items()}
        if server.auth is not None:
            item["auth"] = {
                "client_id": server.auth.client_id,
                "client_secret": server.auth.client_secret,
                "scopes": [str(scope) for scope in server.auth.scopes],
            }

        mapped[name] = item
    return mapped
