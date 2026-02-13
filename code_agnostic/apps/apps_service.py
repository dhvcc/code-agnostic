from pathlib import Path

from code_agnostic.apps.app_id import AppId, app_ids_by_capability
from code_agnostic.apps.common.framework import (
    create_registered_app_service,
    list_registered_app_services,
)
from code_agnostic.apps.common.interfaces.service import IAppConfigService
from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.executor import SyncExecutor
from code_agnostic.models import AppStatusRow, AppSyncStatus, SyncPlan
from code_agnostic.planner import SyncPlanner
from code_agnostic.utils import read_json_safe, write_json


class AppsService:
    def __init__(self, core_repository: ISourceRepository) -> None:
        self.core_repository = core_repository

    @property
    def apps_path(self) -> Path:
        return self.core_repository.root / "config" / "apps.json"

    def available_apps(self) -> list[str]:
        registered = set(list_registered_app_services())
        manageable = set(app_ids_by_capability(toggleable=True))
        return [
            app.value
            for app in sorted(registered & manageable, key=lambda item: item.value)
        ]

    def load_apps(self) -> dict[str, bool]:
        payload, error = read_json_safe(self.apps_path)
        if error is not None or not isinstance(payload, dict):
            return self._default_apps()

        result = self._default_apps()
        for app_name in self.available_apps():
            value = payload.get(app_name)
            if isinstance(value, bool):
                result[app_name] = value
        return result

    def save_apps(self, apps: dict[str, bool]) -> None:
        normalized = self._default_apps()
        for app_name in self.available_apps():
            value = apps.get(app_name)
            if isinstance(value, bool):
                normalized[app_name] = value
        write_json(self.apps_path, normalized)

    def is_enabled(self, app_name: str) -> bool:
        return self.load_apps().get(app_name, False)

    def set_enabled(self, app_name: str, enabled: bool) -> None:
        if app_name not in self.available_apps():
            raise ValueError(f"Unknown app: {app_name}")
        apps = self.load_apps()
        apps[app_name] = enabled
        self.save_apps(apps)

    def enable(self, app_name: str) -> None:
        self.set_enabled(app_name=app_name, enabled=True)

    def disable(self, app_name: str) -> None:
        self.set_enabled(app_name=app_name, enabled=False)

    def list_status_rows(self) -> list[AppStatusRow]:
        apps = self.load_apps()
        rows: list[AppStatusRow] = []
        for app_name in self.available_apps():
            enabled = apps.get(app_name, False)
            detail = "enabled by user" if enabled else "disabled by default"
            rows.append(
                AppStatusRow(
                    name=app_name,
                    status=AppSyncStatus.ENABLED if enabled else AppSyncStatus.DISABLED,
                    detail=detail,
                )
            )
        return rows

    def enabled_apps(self) -> list[str]:
        apps = self.load_apps()
        return [name for name in self.available_apps() if apps.get(name, False)]

    def plan_for_target(self, target: str) -> SyncPlan:
        normalized = target.lower()
        app_services = self._resolve_services_for_target(normalized)
        plan = SyncPlanner(
            core=self.core_repository,
            app_services=app_services,
            include_workspace=True,
        ).build()
        if normalized == "all":
            if (
                not app_services
                and not plan.actions
                and not plan.errors
                and not plan.skipped
            ):
                return SyncPlan([], [], ["No apps enabled for sync."])
            return plan
        return plan.filter_for_target(normalized)

    def execute_plan(self, scoped_plan: SyncPlan) -> tuple[int, int, list[str]]:
        persist_state = self._requires_state_persist(scoped_plan)
        return SyncExecutor(core=self.core_repository).execute(
            scoped_plan, persist_state=persist_state
        )

    def _resolve_services_for_target(self, target: str) -> list[IAppConfigService]:
        enabled = set(self.enabled_apps())
        if target == "all":
            selected = enabled
        else:
            selected = {target} if target in enabled else set()

        services: list[IAppConfigService] = []
        for app in sorted(selected):
            try:
                services.append(create_registered_app_service(AppId(app)))
            except (KeyError, ValueError):
                continue
        return services

    @staticmethod
    def _requires_state_persist(scoped_plan: SyncPlan) -> bool:
        return any(
            action.kind.value in ("symlink", "remove_symlink") or action.app is not None
            for action in scoped_plan.actions
        )

    def _default_apps(self) -> dict[str, bool]:
        return {name: False for name in self.available_apps()}
