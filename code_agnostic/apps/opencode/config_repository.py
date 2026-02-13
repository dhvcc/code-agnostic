from copy import deepcopy
from pathlib import Path
from typing import Any

from code_agnostic.apps.common.interfaces.repositories import IAppConfigRepository
from code_agnostic.errors import InvalidConfigSchemaError, InvalidJsonFormatError
from code_agnostic.utils import read_json_safe, write_json


class OpenCodeConfigRepository(IAppConfigRepository):
    def __init__(self, root: Path | None = None) -> None:
        self._root = root or (Path.home() / ".config" / "opencode")

    @property
    def root(self) -> Path:
        return self._root

    @property
    def config_path(self) -> Path:
        return self.root / "opencode.json"

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def agents_dir(self) -> Path:
        plural = self.root / "agents"
        singular = self.root / "agent"
        if plural.exists():
            return plural
        if singular.exists():
            return singular
        return plural

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
        mcp = payload.get("mcp")
        return mcp if isinstance(mcp, dict) else {}

    def save_mcp_payload(self, payload: dict[str, Any]) -> None:
        config = self.load_config()
        config["mcp"] = payload
        self.save_config(config)

    def merge_config(
        self, existing: dict[str, Any], base: dict[str, Any], mapped_mcp: dict[str, Any]
    ) -> dict[str, Any]:
        merged = deepcopy(existing)
        self._migrate_legacy_permission(base, merged)
        for key, value in base.items():
            if key == "permission" and isinstance(value, list):
                continue
            merged[key] = deepcopy(value)
        merged["mcp"] = deepcopy(mapped_mcp)
        return merged

    @staticmethod
    def _migrate_legacy_permission(
        base: dict[str, Any], merged: dict[str, Any]
    ) -> None:
        permission = base.get("permission")
        if not isinstance(permission, list):
            return

        tools = merged.get("tools")
        if not isinstance(tools, dict):
            tools = {}

        for rule in permission:
            if not isinstance(rule, dict):
                continue
            permission_name = rule.get("permission")
            action = rule.get("action")
            if not isinstance(permission_name, str) or not isinstance(action, str):
                continue
            if permission_name == "*":
                continue
            if action == "deny":
                tools[permission_name] = False
            elif action == "allow":
                tools[permission_name] = True

        if tools:
            merged["tools"] = tools

        merged.pop("permission", None)
