import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from code_agnostic.apps.sync.base import IAppConfigRepository, IAppMCPMapper
from code_agnostic.apps.sync.models import MCPServerDTO, MCPServerType
from code_agnostic.errors import InvalidConfigSchemaError, InvalidJsonFormatError

_ENV_PATTERN = re.compile(r"^\$\{(?:env:)?([A-Z_][A-Z0-9_]*)\}$")
_BEARER_PATTERN = re.compile(r"^Bearer\s+\$\{(?:env:)?([A-Z_][A-Z0-9_]*)\}$")


def _extract_env_var(value: str) -> str | None:
    match = _ENV_PATTERN.match(value.strip())
    return match.group(1) if match else None


def _extract_bearer_env_var(value: str) -> str | None:
    match = _BEARER_PATTERN.match(value.strip())
    return match.group(1) if match else None


def _dump_toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_dump_toml_value(item) for item in value) + "]"
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _dump_string_table(
    lines: list[str], table_name: str, values: dict[str, str]
) -> None:
    if not values:
        return
    lines.append(f"[{table_name}]")
    for key in sorted(values):
        lines.append(f"{key} = {_dump_toml_value(values[key])}")
    lines.append("")


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

            if server.type == MCPServerType.OAUTH and server.auth is not None:
                out["oauth_client_id"] = server.auth.client_id
                out["oauth_client_secret"] = server.auth.client_secret

            mapped[name] = out
        return mapped


class CodexRepository(IAppConfigRepository):
    def __init__(self, root: Optional[Path] = None) -> None:
        self._root = root or (Path.home() / ".codex")

    @property
    def root(self) -> Path:
        return self._root

    @property
    def config_path(self) -> Path:
        return self.root / "config.toml"

    def load_config(self) -> dict[str, Any]:
        if not self.config_path.exists() or self.config_path.stat().st_size == 0:
            return {}
        try:
            payload = tomllib.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise InvalidJsonFormatError(self.config_path, str(exc)) from exc
        if not isinstance(payload, dict):
            raise InvalidConfigSchemaError(self.config_path, "must be a TOML object")
        return payload

    def save_config(self, payload: dict[str, Any]) -> None:
        serialized = self.serialize_config(payload)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(serialized, encoding="utf-8")

    def serialize_config(self, payload: dict[str, Any]) -> str:
        lines: list[str] = []
        mcp_servers = payload.get("mcp_servers")
        if isinstance(mcp_servers, dict):
            for name in sorted(mcp_servers):
                server = mcp_servers[name]
                if not isinstance(server, dict):
                    continue
                lines.append(f"[mcp_servers.{name}]")
                for key in [
                    "command",
                    "args",
                    "url",
                    "env_vars",
                    "bearer_token_env_var",
                    "oauth_client_id",
                    "oauth_client_secret",
                ]:
                    if key in server:
                        lines.append(f"{key} = {_dump_toml_value(server[key])}")
                lines.append("")
                env_table = server.get("env")
                if isinstance(env_table, dict):
                    _dump_string_table(
                        lines,
                        f"mcp_servers.{name}.env",
                        {str(k): str(v) for k, v in env_table.items()},
                    )
                http_headers = server.get("http_headers")
                if isinstance(http_headers, dict):
                    _dump_string_table(
                        lines,
                        f"mcp_servers.{name}.http_headers",
                        {str(k): str(v) for k, v in http_headers.items()},
                    )
                env_http_headers = server.get("env_http_headers")
                if isinstance(env_http_headers, dict):
                    _dump_string_table(
                        lines,
                        f"mcp_servers.{name}.env_http_headers",
                        {str(k): str(v) for k, v in env_http_headers.items()},
                    )
        return "\n".join(lines).strip() + "\n"

    def load_mcp_payload(self) -> dict[str, Any]:
        payload = self.load_config()
        mcp = payload.get("mcp_servers")
        if isinstance(mcp, dict):
            return mcp
        return {}

    def save_mcp_payload(self, payload: dict[str, Any]) -> None:
        config = self.load_config()
        config["mcp_servers"] = payload
        self.save_config(config)
