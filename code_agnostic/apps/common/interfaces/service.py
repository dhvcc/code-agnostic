from abc import ABC, abstractmethod
from typing import Any

from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import IAppConfigRepository
from code_agnostic.apps.common.models import MCPServerDTO
from code_agnostic.models import Action, ActionKind, ActionStatus, AppId


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
