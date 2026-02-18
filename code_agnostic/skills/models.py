"""Skill data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class SkillToolPermissions:
    read: bool = True
    write: bool = False
    mcp: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class SkillMetadata:
    name: str = ""
    description: str = ""
    tools: SkillToolPermissions = field(default_factory=SkillToolPermissions)


@dataclass(frozen=True)
class Skill:
    name: str
    source_path: Path
    metadata: SkillMetadata
    content: str
