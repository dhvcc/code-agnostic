from enum import Enum
from dataclasses import dataclass

from code_agnostic.constants import (
    CODEX_CONFIG_FILENAME,
    CODEX_PROJECT_DIRNAME,
    CURSOR_CONFIG_FILENAME,
    CURSOR_PROJECT_DIRNAME,
    OPENCODE_CONFIG_FILENAME,
    OPENCODE_PROJECT_DIRNAME,
)


class AppId(str, Enum):
    CORE = "core"
    OPENCODE = "opencode"
    CURSOR = "cursor"
    CODEX = "codex"


@dataclass(frozen=True)
class AppMetadata:
    app_id: AppId
    label: str
    targetable: bool
    toggleable: bool
    importable: bool
    supports_import_agents: bool
    supports_workspace_propagation: bool
    project_dir_name: str | None = None
    config_filename: str | None = None


APP_CATALOG: dict[AppId, AppMetadata] = {
    AppId.CORE: AppMetadata(
        app_id=AppId.CORE,
        label="Code Agnostic",
        targetable=False,
        toggleable=False,
        importable=False,
        supports_import_agents=True,
        supports_workspace_propagation=False,
        project_dir_name=None,
    ),
    AppId.OPENCODE: AppMetadata(
        app_id=AppId.OPENCODE,
        label="OpenCode",
        targetable=True,
        toggleable=True,
        importable=True,
        supports_import_agents=True,
        supports_workspace_propagation=True,
        project_dir_name=OPENCODE_PROJECT_DIRNAME,
        config_filename=OPENCODE_CONFIG_FILENAME,
    ),
    AppId.CURSOR: AppMetadata(
        app_id=AppId.CURSOR,
        label="Cursor",
        targetable=True,
        toggleable=True,
        importable=True,
        supports_import_agents=True,
        supports_workspace_propagation=False,
        project_dir_name=CURSOR_PROJECT_DIRNAME,
        config_filename=CURSOR_CONFIG_FILENAME,
    ),
    AppId.CODEX: AppMetadata(
        app_id=AppId.CODEX,
        label="Codex",
        targetable=True,
        toggleable=True,
        importable=True,
        supports_import_agents=True,
        supports_workspace_propagation=True,
        project_dir_name=CODEX_PROJECT_DIRNAME,
        config_filename=CODEX_CONFIG_FILENAME,
    ),
}


def app_metadata(app: AppId | str) -> AppMetadata:
    app_id = app if isinstance(app, AppId) else AppId(app)
    return APP_CATALOG[app_id]


def app_label(app: AppId | str) -> str:
    return app_metadata(app).label


def app_scope(app: AppId | str, resource: str) -> str:
    app_id = app if isinstance(app, AppId) else AppId(app)
    return f"app:{app_id.value}:{resource}"


def app_ids_by_capability(
    *,
    targetable: bool | None = None,
    toggleable: bool | None = None,
    importable: bool | None = None,
    workspace_propagation: bool | None = None,
) -> list[AppId]:
    ids: list[AppId] = []
    for app_id, metadata in APP_CATALOG.items():
        if targetable is not None and metadata.targetable != targetable:
            continue
        if toggleable is not None and metadata.toggleable != toggleable:
            continue
        if importable is not None and metadata.importable != importable:
            continue
        if (
            workspace_propagation is not None
            and metadata.supports_workspace_propagation != workspace_propagation
        ):
            continue
        ids.append(app_id)
    return sorted(ids, key=lambda item: item.value)
