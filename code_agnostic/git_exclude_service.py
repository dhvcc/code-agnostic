"""Git-exclude customization service."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from code_agnostic.apps.app_id import AppId, app_metadata
from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.utils import read_json_safe, write_json
from code_agnostic.workspace_artifacts import git_exclude_entries_for_repo


class GitExcludeService:
    def __init__(self, core: ISourceRepository) -> None:
        self._core = core

    def _config_path(self, workspace_name: str) -> Path:
        return self._core.workspace_config_dir(workspace_name) / "git-exclude.json"

    def _load_config(self, workspace_name: str) -> dict[str, Any]:
        path = self._config_path(workspace_name)
        payload, _ = read_json_safe(path)
        if not isinstance(payload, dict):
            return {"include_defaults": True, "extra_patterns": []}
        payload.setdefault("include_defaults", True)
        payload.setdefault("extra_patterns", [])
        if not isinstance(payload["extra_patterns"], list):
            payload["extra_patterns"] = []
        return payload

    def _save_config(self, workspace_name: str, config: dict[str, Any]) -> None:
        path = self._config_path(workspace_name)
        write_json(path, config)

    def _ensure_workspace_exists(self, workspace_name: str) -> None:
        names = {item["name"] for item in self._core.load_workspaces()}
        if workspace_name not in names:
            raise ValueError(f"Workspace not found: {workspace_name}")

    def compute_entries(
        self, workspace_name: str, enabled_apps: list[str]
    ) -> list[str]:
        return self.compute_entries_for_repo(workspace_name, enabled_apps)

    def compute_entries_for_repo(
        self,
        workspace_name: str,
        enabled_apps: list[str],
        *,
        workspace_path: Path | None = None,
        repo_path: Path | None = None,
    ) -> list[str]:
        config = self._load_config(workspace_name)
        extras = [str(p) for p in config.get("extra_patterns", [])]

        if not config.get("include_defaults", True):
            return extras

        workspace_apps: list[str] = []
        for app_name in enabled_apps:
            try:
                metadata = app_metadata(app_name)
            except ValueError:
                continue
            if metadata.supports_workspace_propagation:
                workspace_apps.append(metadata.app_id.value)

        ws_source = WorkspaceConfigRepository(
            root=self._core.workspace_config_dir(workspace_name)
        )
        app_ids = [AppId(app_name) for app_name in workspace_apps]
        defaults = git_exclude_entries_for_repo(
            ws_source,
            app_ids,
            workspace_path=workspace_path,
            repo_path=repo_path,
        )
        return defaults + extras

    def add_pattern(self, workspace_name: str, pattern: str) -> None:
        self._ensure_workspace_exists(workspace_name)
        config = self._load_config(workspace_name)
        patterns = config["extra_patterns"]
        if pattern not in patterns:
            patterns.append(pattern)
        config["extra_patterns"] = patterns
        self._save_config(workspace_name, config)

    def remove_pattern(self, workspace_name: str, pattern: str) -> bool:
        self._ensure_workspace_exists(workspace_name)
        config = self._load_config(workspace_name)
        patterns = config["extra_patterns"]
        if pattern not in patterns:
            return False
        patterns.remove(pattern)
        config["extra_patterns"] = patterns
        self._save_config(workspace_name, config)
        return True

    def list_patterns(self, workspace_name: str) -> dict[str, Any]:
        self._ensure_workspace_exists(workspace_name)
        return self._load_config(workspace_name)
