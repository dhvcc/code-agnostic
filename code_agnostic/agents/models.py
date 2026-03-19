"""Agent data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentToolPermissions:
    read: bool = True
    write: bool = True
    mcp: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class AgentSkillConfig:
    path: str
    enabled: bool | None = None


@dataclass(frozen=True)
class AgentCodexConfig:
    mcp_servers: dict[str, dict[str, Any]] = field(default_factory=dict)
    skills_config: list[AgentSkillConfig] = field(default_factory=list)


@dataclass(frozen=True)
class AgentMetadata:
    name: str = ""
    description: str = ""
    model: str = ""
    model_reasoning_effort: str = ""
    sandbox_mode: str = ""
    nickname_candidates: list[str] = field(default_factory=list)
    tools: AgentToolPermissions = field(default_factory=AgentToolPermissions)
    codex: AgentCodexConfig = field(default_factory=AgentCodexConfig)


@dataclass(frozen=True)
class Agent:
    name: str
    source_path: Path
    metadata: AgentMetadata
    content: str
