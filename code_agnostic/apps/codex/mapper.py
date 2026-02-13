import re
from copy import deepcopy
from typing import Any

from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.models import MCPServerDTO, MCPServerType

_ENV_PATTERN = re.compile(r"^\$\{(?:env:)?([A-Z_][A-Z0-9_]*)\}$")
_BEARER_PATTERN = re.compile(r"^Bearer\s+\$\{(?:env:)?([A-Z_][A-Z0-9_]*)\}$")


def _extract_env_var(value: str) -> str | None:
    match = _ENV_PATTERN.match(value.strip())
    return match.group(1) if match else None


def _extract_bearer_env_var(value: str) -> str | None:
    match = _BEARER_PATTERN.match(value.strip())
    return match.group(1) if match else None


class CodexMCPMapper(IAppMCPMapper):
    def to_common(self, payload: dict[str, Any]) -> dict[str, MCPServerDTO]:
        mapped: dict[str, MCPServerDTO] = {}
        for name, server in payload.items():
            if not isinstance(server, dict):
                continue

            url = server.get("url")
            server_type = (
                MCPServerType.HTTP if isinstance(url, str) else MCPServerType.STDIO
            )

            env: dict[str, str] = {}
            env_vars = server.get("env_vars")
            if isinstance(env_vars, list):
                for key in env_vars:
                    if isinstance(key, str):
                        env[key] = f"${{{key}}}"
            env_table = server.get("env")
            if isinstance(env_table, dict):
                for key, value in env_table.items():
                    env[str(key)] = str(value)

            headers: dict[str, str] = {}
            http_headers = server.get("http_headers")
            if isinstance(http_headers, dict):
                for key, value in http_headers.items():
                    headers[str(key)] = str(value)

            env_http_headers = server.get("env_http_headers")
            if isinstance(env_http_headers, dict):
                for key, env_name in env_http_headers.items():
                    if isinstance(env_name, str):
                        headers[str(key)] = f"${{{env_name}}}"

            bearer_token_env_var = server.get("bearer_token_env_var")
            if isinstance(bearer_token_env_var, str):
                headers["Authorization"] = f"Bearer ${{{bearer_token_env_var}}}"

            mapped[name] = MCPServerDTO(
                name=name,
                type=server_type,
                command=server.get("command")
                if isinstance(server.get("command"), str)
                else None,
                args=[str(item) for item in server.get("args", [])]
                if isinstance(server.get("args"), list)
                else [],
                url=url if isinstance(url, str) else None,
                headers=headers,
                env=env,
                auth=None,
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

            env_vars: list[str] = []
            env_table: dict[str, str] = {}
            for key, value in server.env.items():
                env_name = _extract_env_var(value)
                if env_name is None:
                    env_table[key] = value
                else:
                    env_vars.append(env_name)
            if env_vars:
                out["env_vars"] = sorted(set(env_vars))
            if env_table:
                out["env"] = env_table

            http_headers: dict[str, str] = {}
            env_http_headers: dict[str, str] = {}
            for key, value in server.headers.items():
                bearer_env = (
                    _extract_bearer_env_var(value)
                    if key.lower() == "authorization"
                    else None
                )
                if bearer_env is not None:
                    out["bearer_token_env_var"] = bearer_env
                    continue
                env_name = _extract_env_var(value)
                if env_name is None:
                    http_headers[key] = value
                else:
                    env_http_headers[key] = env_name
            if http_headers:
                out["http_headers"] = http_headers
            if env_http_headers:
                out["env_http_headers"] = env_http_headers

            if (
                server.type == MCPServerType.OAUTH
                and server.auth is not None
                and server.auth.scopes
            ):
                out["scopes"] = deepcopy(server.auth.scopes)

            mapped[name] = out
        return mapped
