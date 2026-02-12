from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Optional


class ActionKind(str, Enum):
    WRITE_JSON = "write_json"
    SYMLINK = "symlink"
    REMOVE_SYMLINK = "remove_symlink"


class ActionStatus(str, Enum):
    NOOP = "noop"
    CREATE = "create"
    UPDATE = "update"
    FIX = "fix"
    CONFLICT = "conflict"
    REMOVE = "remove"


@dataclass
class Action:
    kind: ActionKind
    path: Path
    status: ActionStatus
    detail: str
    source: Optional[Path] = None
    payload: Optional[Any] = None


@dataclass
class PlanResult:
    actions: list[Action]
    errors: list[str]
    skipped: list[str]
