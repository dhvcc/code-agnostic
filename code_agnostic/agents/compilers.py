"""Per-editor agent compilers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import yaml

from code_agnostic.agents.claude import serialize_claude_agent
from code_agnostic.agents.codex import serialize_codex_agent
from code_agnostic.agents.models import Agent
from code_agnostic.agents.opencode import serialize_opencode_agent
from code_agnostic.errors import InvalidConfigSchemaError

_CURSOR_AGENT_FRONTMATTER_KEYS = frozenset({"model", "readonly", "is_background"})


class IAgentCompiler(ABC):
    @abstractmethod
    def compile(self, agent: Agent) -> str:
        """Return compiled agent content for target editor."""


class OpenCodeAgentCompiler(IAgentCompiler):
    """Cross-compile for OpenCode agents."""

    def compile(self, agent: Agent) -> str:
        return serialize_opencode_agent(agent)


class CursorAgentCompiler(IAgentCompiler):
    """Cross-compile for Cursor subagents."""

    def compile(self, agent: Agent) -> str:
        return _serialize_cursor_agent(agent)


def _serialize_cursor_agent(agent: Agent) -> str:
    overrides = dict(agent.metadata.app_overrides.get("cursor", {}))
    fm: dict[str, Any] = {}
    if agent.metadata.name:
        fm["name"] = agent.metadata.name
    if agent.metadata.description:
        fm["description"] = agent.metadata.description

    model = overrides.pop("model", agent.metadata.model)
    if model:
        fm["model"] = model

    if agent.metadata.tools.write is False:
        fm["readonly"] = True

    for key in sorted(overrides):
        if key not in _CURSOR_AGENT_FRONTMATTER_KEYS:
            allowed = ", ".join(sorted(_CURSOR_AGENT_FRONTMATTER_KEYS))
            raise InvalidConfigSchemaError(
                agent.source_path,
                f"x-cursor.{key} is not supported in cursor agent "
                f"frontmatter; allowed keys: {allowed}",
            )
        fm[key] = overrides[key]

    parts: list[str] = []
    if fm:
        parts.append("---")
        parts.append(yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip())
        parts.append("---")
        parts.append("")
    parts.append(agent.content)
    return "\n".join(parts)


class CodexAgentCompiler(IAgentCompiler):
    """Cross-compile for Codex subagents."""

    def compile(self, agent: Agent) -> str:
        return serialize_codex_agent(agent)


class ClaudeAgentCompiler(IAgentCompiler):
    """Cross-compile for Claude Code subagents."""

    def compile(self, agent: Agent) -> str:
        return serialize_claude_agent(agent)
