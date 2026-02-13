from pathlib import Path
from typing import Any

from code_agnostic.apps.common.interfaces.repositories import IAppConfigRepository
from code_agnostic.errors import InvalidConfigSchemaError, InvalidJsonFormatError
from code_agnostic.utils import read_json_safe, write_json


class CursorConfigRepository(IAppConfigRepository):
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (Path.home() / ".cursor")

    @property
    def root(self) -> Path:
        return self._root

    @property
    def config_path(self) -> Path:
        return self.root / "mcp.json"

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def agents_dir(self) -> Path:
        return self.root / "agents"

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
        return mcp if isinstance(mcp, dict) else {}

    def save_mcp_payload(self, payload: dict[str, Any]) -> None:
        config = self.load_config()
        config["mcpServers"] = payload
        self.save_config(config)
