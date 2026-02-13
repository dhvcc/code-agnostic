import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from code_agnostic.apps.sync.base import IAppConfigRepository, IAppMCPMapper
from code_agnostic.apps.sync.models import MCPServerDTO
from code_agnostic.models import Action, ActionKind, ActionStatus, AppId


def load_json_schema(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_schema_error(error: Any) -> str:
    path = ".".join([str(part) for part in error.path])
    return f"{error.message} at {path}" if path else str(error.message)


class IAppConfigService(ABC):
    @property
    @abstractmethod
    def app_id(self) -> AppId:
        raise NotImplementedError

    @property
    @abstractmethod
    def action_kind(self) -> ActionKind:
        raise NotImplementedError

    @property
    @abstractmethod
    def repository(self) -> IAppConfigRepository:
        raise NotImplementedError

    @property
    @abstractmethod
    def mapper(self) -> IAppMCPMapper:
        raise NotImplementedError

    @abstractmethod
    def validate_config(self, payload: Any) -> None:
        raise NotImplementedError

    @abstractmethod
    def build_action_payload(self, payload: dict[str, Any]) -> Any:
        raise NotImplementedError

    @abstractmethod
    def set_mcp_payload(
        self, merged: dict[str, Any], desired_mcp: dict[str, Any]
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def derive_status(
        self, existing: dict[str, Any], merged: dict[str, Any]
    ) -> ActionStatus:
        raise NotImplementedError

    def build_action(self, common_servers: dict[str, MCPServerDTO]) -> Action:
        existing = self.repository.load_config()
        if existing or self.repository.config_path.exists():
            self.validate_config(existing)

        desired_mcp = self.mapper.from_common(common_servers)
        merged = dict(existing)
        self.set_mcp_payload(merged, desired_mcp)
        self.validate_config(merged)

        return Action(
            kind=self.action_kind,
            path=self.repository.config_path,
            status=self.derive_status(existing, merged),
            detail=f"sync {self.app_id.value} config from common mcp base",
            payload=self.build_action_payload(merged),
            app=self.app_id.value,
        )
