from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

from code_agnostic.apps.common.interfaces.repositories import IAppConfigRepository
from code_agnostic.errors import InvalidConfigSchemaError, InvalidJsonFormatError


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


class CodexConfigRepository(IAppConfigRepository):
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (Path.home() / ".codex")

    @property
    def root(self) -> Path:
        return self._root

    @property
    def config_path(self) -> Path:
        return self.root / "config.toml"

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

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
                    "scopes",
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
        return mcp if isinstance(mcp, dict) else {}

    def save_mcp_payload(self, payload: dict[str, Any]) -> None:
        config = self.load_config()
        config["mcp_servers"] = payload
        self.save_config(config)
