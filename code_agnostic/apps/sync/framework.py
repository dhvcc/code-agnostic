import json
from abc import ABC, ABCMeta, abstractmethod
from pathlib import Path
from typing import Any, ClassVar

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


class AppServiceRegistryMeta(ABCMeta):
    _registry: dict[AppId, type["RegisteredAppConfigService"]] = {}

    def __new__(
        mcls,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
        **kwargs: Any,
    ):
        cls = super().__new__(mcls, name, bases, namespace, **kwargs)
        app_id = getattr(cls, "APP_ID", None)
        is_abstract = bool(getattr(cls, "__abstractmethods__", False))
        if app_id is not None and not is_abstract:
            mcls._registry[app_id] = cls
        return cls


class RegisteredAppConfigService(IAppConfigService, metaclass=AppServiceRegistryMeta):
    APP_ID: ClassVar[AppId | None] = None

    @classmethod
    @abstractmethod
    def create_default(cls) -> "RegisteredAppConfigService":
        raise NotImplementedError


def list_registered_app_services() -> list[AppId]:
    _load_registered_modules()
    return sorted(AppServiceRegistryMeta._registry.keys(), key=lambda item: item.value)


def create_registered_app_service(app_id: AppId) -> RegisteredAppConfigService:
    _load_registered_modules()
    service_class = AppServiceRegistryMeta._registry.get(app_id)
    if service_class is None:
        raise KeyError(f"No app service registered for: {app_id.value}")
    return service_class.create_default()


def _load_registered_modules() -> None:
    from code_agnostic.apps.sync.apps.loader import load_app_service_modules

    load_app_service_modules()
