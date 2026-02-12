from copy import deepcopy
from typing import Any


def _as_command_array(command: Any, args: Any) -> list[str]:
    if isinstance(command, list):
        base = [str(item) for item in command]
    elif isinstance(command, str):
        base = [command]
    else:
        base = []

    if isinstance(args, list):
        base.extend(str(item) for item in args)
    return base


def map_mcp_servers_to_opencode(mcp_servers: dict[str, Any]) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for name, server in mcp_servers.items():
        if not isinstance(server, dict):
            continue

        out: dict[str, Any] = {}

        if "url" in server:
            out["type"] = "remote"
            out["url"] = server["url"]
        elif "command" in server:
            command_list = _as_command_array(server.get("command"), server.get("args"))
            if not command_list:
                continue
            out["type"] = "local"
            out["command"] = command_list
        else:
            continue

        for passthrough_key in ["headers", "environment", "enabled", "oauth", "timeout"]:
            if passthrough_key in server:
                out[passthrough_key] = deepcopy(server[passthrough_key])

        mapped[name] = out
    return mapped
