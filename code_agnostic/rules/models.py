"""Rule data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class RuleMetadata:
    description: str = ""
    globs: list[str] = field(default_factory=list)
    always_apply: bool = False


@dataclass(frozen=True)
class Rule:
    name: str
    source_path: Path
    metadata: RuleMetadata
    content: str
