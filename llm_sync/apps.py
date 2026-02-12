from pathlib import Path

from llm_sync.models import AppId, AppStatusRow, AppSyncStatus
from llm_sync.repositories.common import CommonRepository
from llm_sync.utils import read_json_safe, write_json


class AppsService:
    def __init__(self, common: CommonRepository) -> None:
        self.common = common

    @property
    def apps_path(self) -> Path:
        return self.common.config_dir / "apps.json"

    def load_apps(self) -> dict[str, bool]:
        payload, error = read_json_safe(self.apps_path)
        if error is not None or not isinstance(payload, dict):
            return self._default_apps()

        result = self._default_apps()
        for app in AppId:
            value = payload.get(app.value)
            if isinstance(value, bool):
                result[app.value] = value
        return result

    def save_apps(self, apps: dict[str, bool]) -> None:
        normalized = self._default_apps()
        for app in AppId:
            value = apps.get(app.value)
            if isinstance(value, bool):
                normalized[app.value] = value
        write_json(self.apps_path, normalized)

    def is_enabled(self, app: AppId) -> bool:
        return self.load_apps().get(app.value, False)

    def set_enabled(self, app: AppId, enabled: bool) -> None:
        apps = self.load_apps()
        apps[app.value] = enabled
        self.save_apps(apps)

    def enable(self, app: AppId) -> None:
        self.set_enabled(app=app, enabled=True)

    def disable(self, app: AppId) -> None:
        self.set_enabled(app=app, enabled=False)

    def list_status_rows(self) -> list[AppStatusRow]:
        apps = self.load_apps()
        rows: list[AppStatusRow] = []
        for app in AppId:
            enabled = apps.get(app.value, False)
            detail = "enabled by user" if enabled else "disabled by default"
            rows.append(
                AppStatusRow(
                    name=app,
                    status=AppSyncStatus.ENABLED if enabled else AppSyncStatus.DISABLED,
                    detail=detail,
                )
            )
        return rows

    def enabled_apps(self) -> list[AppId]:
        apps = self.load_apps()
        return [app for app in AppId if apps.get(app.value, False)]

    @staticmethod
    def _default_apps() -> dict[str, bool]:
        return {app.value: False for app in AppId}
