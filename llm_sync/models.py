from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class Action:
    kind: str
    path: Path
    status: str
    detail: str
    source: Optional[Path] = None
    payload: Optional[Any] = None


@dataclass
class PlanResult:
    actions: list[Action]
    errors: list[str]
    skipped: list[str]
