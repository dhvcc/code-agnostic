from typing import Any

from code_agnostic.apps.sync.models import MCPAuthDTO, MCPServerDTO, MCPServerType


def common_mcp_to_dto(mcp_servers: dict[str, Any]) -> dict[str, MCPServerDTO]:
    mapped: dict[str, MCPServerDTO] = {}
    for name, raw in mcp_servers.items():
        if not isinstance(raw, dict):
            continue

        command = raw.get("command")
        args = raw.get("args")
        url = raw.get("url")

        headers = raw.get("headers")
        env = raw.get("env")
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
                headers={str(k): str(v) for k, v in headers.items()}
                if isinstance(headers, dict)
                else {},
                env={str(k): str(v) for k, v in env.items()}
                if isinstance(env, dict)
                else {},
                auth=auth,
            )

    return mapped
