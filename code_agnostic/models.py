from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ActionKind(str, Enum):
    WRITE_JSON = "write_json"
    WRITE_TEXT = "write_text"
    SYMLINK = "symlink"
    REMOVE_SYMLINK = "remove_symlink"


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


class EditorSyncStatus(str, Enum):
    SYNCED = "synced"
    DRIFT = "drift"
    DISABLED = "disabled"
    ERROR = "error"


class WorkspaceSyncStatus(str, Enum):
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
    source: Optional[Path] = None
    payload: Optional[Any] = None
    app: Optional[str] = None
    scope: Optional[str] = None


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
        if normalized in (SyncTarget.CURSOR.value, SyncTarget.CODEX.value):
            filtered = [
                action
                for action in self.actions
                if action.app in (normalized, "workspace")
            ]
            return SyncPlan(actions=filtered, errors=self.errors, skipped=self.skipped)

        filtered_actions: list[Action] = []
        for action in self.actions:
            if action.app in (SyncTarget.CURSOR.value, SyncTarget.CODEX.value):
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
            if skills_root is not None and _is_under(action.path, skills_root):
                filtered_actions.append(action)
                continue
            if agents_root is not None and _is_under(action.path, agents_root):
                filtered_actions.append(action)
        return SyncPlan(
            actions=filtered_actions, errors=self.errors, skipped=self.skipped
        )


PlanResult = SyncPlan


@dataclass(frozen=True)
class WorkspaceConfig:
    name: str
    path: Path


@dataclass(frozen=True)
class EditorStatusRow:
    name: str
    status: EditorSyncStatus
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class WorkspaceRepoStatusRow:
    repo: str
    status: RepoSyncStatus
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {
            "repo": self.repo,
            "status": self.status.value,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class WorkspaceStatusRow:
    name: str
    path: str
    status: WorkspaceSyncStatus
    detail: str
    repos: list[WorkspaceRepoStatusRow]

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "status": self.status.value,
            "detail": self.detail,
            "repos": [repo.as_dict() for repo in self.repos],
        }


@dataclass(frozen=True)
class AppStatusRow:
    name: str
    status: AppSyncStatus
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
        }


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False
