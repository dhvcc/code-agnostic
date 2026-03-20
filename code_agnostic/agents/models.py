"""Agent data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_OVERRIDE_ATTRS: dict[str, str] = {
    "model": "model",
    "reasoning_effort": "model_reasoning_effort",
    "sandbox_mode": "sandbox_mode",
    "nickname_candidates": "nickname_candidates",
}


def normalize_agent_override_key(key: str) -> str:
    aliases = {
        "model_reasoning_effort": "reasoning_effort",
        "reasoningEffort": "reasoning_effort",
    }
    return aliases.get(key, key)


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
    app_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    codex: AgentCodexConfig = field(default_factory=AgentCodexConfig)

    def effective_value(self, app: str, key: str) -> Any:
        normalized_key = normalize_agent_override_key(key)
        overrides = self.app_overrides.get(app, {})
        if normalized_key in overrides:
            return overrides[normalized_key]
        attr_name = APP_OVERRIDE_ATTRS.get(normalized_key)
        if attr_name is None:
            return None
        return getattr(self, attr_name)

    def app_passthrough(
        self, app: str, *, consumed_keys: set[str] | None = None
    ) -> dict[str, Any]:
        consumed = {
            normalize_agent_override_key(key) for key in (consumed_keys or set())
        }
        overrides = self.app_overrides.get(app, {})
        return {
            key: value
            for key, value in overrides.items()
            if normalize_agent_override_key(key) not in consumed
        }


@dataclass(frozen=True)
class Agent:
    name: str
    source_path: Path
    metadata: AgentMetadata
    content: str
