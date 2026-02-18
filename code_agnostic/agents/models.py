"""Agent data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class AgentToolPermissions:
    read: bool = True
    write: bool = True
    mcp: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class AgentMetadata:
    name: str = ""
    description: str = ""
    model: str = ""
    tools: AgentToolPermissions = field(default_factory=AgentToolPermissions)


@dataclass(frozen=True)
class Agent:
    name: str
    source_path: Path
    metadata: AgentMetadata
    content: str
