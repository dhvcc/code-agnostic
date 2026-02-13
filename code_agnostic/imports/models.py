from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class ImportSection(str, Enum):
    MCP = "mcp"
    SKILLS = "skills"
    AGENTS = "agents"


class ConflictPolicy(str, Enum):
    SKIP = "skip"
    OVERWRITE = "overwrite"
    FAIL = "fail"


class ImportActionStatus(str, Enum):
    NOOP = "noop"
    CREATE = "create"
    UPDATE = "update"
    CONFLICT = "conflict"
    SKIP = "skip"


class ImportActionKind(str, Enum):
    WRITE_MCP_BASE = "write_mcp_base"
    COPY_PATH = "copy_path"
    NOTE = "note"


@dataclass
class ImportAction:
    section: ImportSection
    kind: ImportActionKind
    status: ImportActionStatus
    detail: str
    source: Path | None = None
    target: Path | None = None
    payload: Any | None = None


@dataclass
class ImportPlan:
    source_app: str
    sections: list[ImportSection]
    actions: list[ImportAction]
    errors: list[str]
    skipped: list[str]


@dataclass(frozen=True)
class ImportApplyResult:
    applied: int
    failed: int
    failures: list[str]
