from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

import tomlkit

from code_agnostic.apps.common.interfaces.repositories import IAppConfigRepository
from code_agnostic.errors import InvalidConfigSchemaError, InvalidJsonFormatError


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
        normalized = dict(payload)
        mcp = normalized.get("mcp_servers")
        if isinstance(mcp, dict) and not mcp:
            normalized.pop("mcp_servers", None)
        return tomlkit.dumps(normalized)

    def load_mcp_payload(self) -> dict[str, Any]:
        payload = self.load_config()
        mcp = payload.get("mcp_servers")
        return mcp if isinstance(mcp, dict) else {}

    def save_mcp_payload(self, payload: dict[str, Any]) -> None:
        config = self.load_config()
        config["mcp_servers"] = payload
        self.save_config(config)
