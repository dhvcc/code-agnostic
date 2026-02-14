from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Any, ClassVar, cast

from code_agnostic.apps.app_id import AppId, app_label
from code_agnostic.apps.common.interfaces.service import IAppConfigService


def format_schema_error(error: Any) -> str:
    path = ".".join([str(part) for part in error.path])
    return f"{error.message} at {path}" if path else str(error.message)


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
            mcls._registry[app_id] = cast(type["RegisteredAppConfigService"], cls)  # type: ignore[assignment]
        return cls


class RegisteredAppConfigService(IAppConfigService, metaclass=AppServiceRegistryMeta):
    APP_ID: ClassVar[AppId | None] = None
    APP_LABEL: ClassVar[str | None] = None

    @property
    def app_label(self) -> str:
        if self.APP_LABEL is not None:
            return self.APP_LABEL
        return app_label(self.app_id)

    @classmethod
    @abstractmethod
    def create_default(cls, root: Path | None = None) -> "RegisteredAppConfigService":
        raise NotImplementedError


def list_registered_app_services() -> list[AppId]:
    _load_registered_modules()
    return sorted(AppServiceRegistryMeta._registry.keys(), key=lambda item: item.value)


def create_registered_app_service(
    app_id: AppId, root: Path | None = None
) -> RegisteredAppConfigService:
    _load_registered_modules()
    service_class = AppServiceRegistryMeta._registry.get(app_id)
    if service_class is None:
        raise KeyError(f"No app service registered for: {app_id.value}")
    return service_class.create_default(root=root)


def _load_registered_modules() -> None:
    from code_agnostic.apps.common.loader import load_app_service_modules

    load_app_service_modules()
