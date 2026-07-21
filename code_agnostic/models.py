from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from code_agnostic.utils import is_under


class ActionKind(str, Enum):
    WRITE_JSON = "write_json"
    WRITE_TEXT = "write_text"
    WRITE_RULE = "write_rule"
    SYMLINK = "symlink"
    REMOVE_SYMLINK = "remove_symlink"
    REMOVE_FILE = "remove_file"


class ActionStatus(str, Enum):
    NOOP = "noop"
    CREATE = "create"
    UPDATE = "update"
    FIX = "fix"
    CONFLICT = "conflict"
    REMOVE = "remove"


class SyncTarget(str, Enum):
    ALL = "all"
    OPENCODE = "opencode"
    CURSOR = "cursor"
    CODEX = "codex"
    CLAUDE = "claude"
    COPILOT = "copilot"


class EditorSyncStatus(str, Enum):
    SYNCED = "synced"
    DRIFT = "drift"
    DISABLED = "disabled"
    ERROR = "error"


class WorkspaceSyncStatus(str, Enum):
    SYNCED = "synced"
    DRIFT = "drift"
    ERROR = "error"


class ProjectSyncStatus(str, Enum):
    SYNCED = "synced"
    DRIFT = "drift"
    ERROR = "error"


class RepoSyncStatus(str, Enum):
    SYNCED = "synced"
    NEEDS_SYNC = "needs_sync"


class AppSyncStatus(str, Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"


@dataclass
class Action:
    kind: ActionKind
    path: Path
    status: ActionStatus
    detail: str
    source: Path | None = None
    payload: Any | None = None
    app: str | None = None
    scope: str | None = None
    workspace: str | None = None
    project: str | None = None
    managed_entries: dict[str, list[str]] | None = None


@dataclass
class SyncPlan:
    actions: list[Action]
    errors: list[Exception]
    skipped: list[str]

    def is_valid(self) -> bool:
        return not self.errors

    def summary(self) -> dict[str, int]:
        counts = {status.value: 0 for status in ActionStatus}
        for action in self.actions:
            counts[action.status.value] += 1
        counts["actions"] = len(self.actions)
        counts["errors"] = len(self.errors)
        counts["skipped"] = len(self.skipped)
        return counts

    def filter_for_target(
        self,
        target: str,
        config_path: Path | None = None,
        skills_root: Path | None = None,
        agents_root: Path | None = None,
    ) -> "SyncPlan":
        normalized = target.lower()
        if normalized == SyncTarget.ALL.value:
            return self
        if normalized in (
            SyncTarget.CURSOR.value,
            SyncTarget.CODEX.value,
            SyncTarget.CLAUDE.value,
            SyncTarget.COPILOT.value,
        ):
            filtered = [
                action
                for action in self.actions
                if action.app in (normalized, "workspace")
            ]
            return SyncPlan(actions=filtered, errors=self.errors, skipped=self.skipped)

        filtered_actions: list[Action] = []
        for action in self.actions:
            if action.app in (
                SyncTarget.CURSOR.value,
                SyncTarget.CODEX.value,
                SyncTarget.CLAUDE.value,
                SyncTarget.COPILOT.value,
            ):
                continue
            if action.app == "workspace":
                filtered_actions.append(action)
                continue
            if action.app in (None, SyncTarget.OPENCODE.value):
                filtered_actions.append(action)
                continue
            if config_path is not None and action.path == config_path:
                filtered_actions.append(action)
                continue
            if skills_root is not None and is_under(action.path, skills_root):
                filtered_actions.append(action)
                continue
            if agents_root is not None and is_under(action.path, agents_root):
                filtered_actions.append(action)
        return SyncPlan(
            actions=filtered_actions, errors=self.errors, skipped=self.skipped
        )


@dataclass(frozen=True)
class SyncState:
    """Typed view of a repository's `.sync-state.json`.

    All defensive normalization (missing keys, wrong JSON types, stray non-string
    entries) happens once in `from_payload`; consumers read the typed fields
    directly instead of re-guarding with `isinstance` at every call site.

    `managed_links`/`managed_paths`/`managed_mcp` are `scope -> names` maps (the
    live ownership model). The three `managed_*_links` lists are vestigial — no
    production reader consumes them — but are kept for on-disk round-trips.
    """

    managed_links: dict[str, list[str]] = field(default_factory=dict)
    managed_paths: dict[str, list[str]] = field(default_factory=dict)
    managed_mcp: dict[str, list[str]] = field(default_factory=dict)
    managed_skill_links: list[str] = field(default_factory=list)
    managed_agent_links: list[str] = field(default_factory=list)
    managed_workspace_links: list[str] = field(default_factory=list)
    updated_at: str | None = None
    skipped: list[str] = field(default_factory=list)

    @classmethod
    def from_payload(cls, payload: Any) -> "SyncState":
        if not isinstance(payload, dict):
            return cls()
        updated_at = payload.get("updated_at")
        return cls(
            managed_links=cls._coerce_group(payload.get("managed_links")),
            managed_paths=cls._coerce_group(payload.get("managed_paths")),
            managed_mcp=cls._coerce_group(payload.get("managed_mcp")),
            managed_skill_links=cls._coerce_str_list(
                payload.get("managed_skill_links")
            ),
            managed_agent_links=cls._coerce_str_list(
                payload.get("managed_agent_links")
            ),
            managed_workspace_links=cls._coerce_str_list(
                payload.get("managed_workspace_links")
            ),
            updated_at=updated_at if isinstance(updated_at, str) else None,
            skipped=cls._coerce_str_list(payload.get("skipped")),
        )

    @staticmethod
    def _coerce_group(value: Any) -> dict[str, list[str]]:
        if not isinstance(value, dict):
            return {}
        result: dict[str, list[str]] = {}
        for scope, names in value.items():
            if not isinstance(scope, str) or not isinstance(names, list):
                continue
            result[scope] = [name for name in names if isinstance(name, str)]
        return result

    @staticmethod
    def _coerce_str_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, str)]


@dataclass(frozen=True)
class WorkspaceConfig:
    """A named config root — a registered workspace or project (`{name, path}`).

    Replaces the raw `dict[str, str]` entries that `load_workspaces()` /
    `load_projects()` used to hand out, so consumers read `.name` / `.path`
    (already a `Path`) instead of stringly-typed lookups.
    """

    name: str
    path: Path


@dataclass(frozen=True)
class EditorStatusRow:
    name: str
    status: EditorSyncStatus
    detail: str


@dataclass(frozen=True)
class WorkspaceRepoStatusRow:
    repo: str
    status: RepoSyncStatus
    detail: str


@dataclass(frozen=True)
class WorkspaceStatusRow:
    name: str
    path: str
    status: WorkspaceSyncStatus
    detail: str
    repos: list[WorkspaceRepoStatusRow]


@dataclass(frozen=True)
class ProjectStatusRow:
    name: str
    path: str
    status: ProjectSyncStatus
    detail: str


@dataclass(frozen=True)
class AppStatusRow:
    name: str
    status: AppSyncStatus
    detail: str
