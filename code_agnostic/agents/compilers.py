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

_CURSOR_AGENT_FRONTMATTER_KEYS = frozenset(
    {"name", "description", "model", "readonly", "is_background"}
)
_COPILOT_AGENT_FRONTMATTER_KEYS = frozenset(
    {
        "name",
        "description",
        "model",
        "target",
        "disable-model-invocation",
        "user-invocable",
        "infer",
        "mcp-servers",
        "metadata",
    }
)


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


class CopilotAgentCompiler(IAgentCompiler):
    """Cross-compile for GitHub Copilot custom agents."""

    def compile(self, agent: Agent) -> str:
        return _serialize_copilot_agent(agent)


def _serialize_copilot_agent(agent: Agent) -> str:
    overrides = dict(agent.metadata.app_overrides.get("copilot", {}))
    fm: dict[str, Any] = {}

    name = overrides.pop("name", agent.metadata.name or agent.name)
    if name:
        fm["name"] = name

    description = overrides.pop("description", agent.metadata.description)
    if not description:
        raise InvalidConfigSchemaError(
            agent.source_path,
            "Copilot agents require a description",
        )
    fm["description"] = description

    model = overrides.pop("model", agent.metadata.model)
    if model:
        fm["model"] = model

    tools = _copilot_tools(agent)
    if tools is not None:
        fm["tools"] = tools

    for key in sorted(overrides):
        if key not in _COPILOT_AGENT_FRONTMATTER_KEYS:
            allowed = ", ".join(sorted(_COPILOT_AGENT_FRONTMATTER_KEYS))
            raise InvalidConfigSchemaError(
                agent.source_path,
                f"x-copilot.{key} is not supported in copilot agent "
                f"frontmatter; allowed keys: {allowed}",
            )
        if key in fm:
            continue
        fm[key] = overrides[key]

    parts: list[str] = []
    if fm:
        parts.append("---")
        parts.append(yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip())
        parts.append("---")
        parts.append("")
    parts.append(agent.content)
    return "\n".join(parts)


def _copilot_tools(agent: Agent) -> list[str] | None:
    permissions = agent.metadata.tools
    if permissions.read is True and permissions.write is True and not permissions.mcp:
        return None

    tools: list[str] = []
    if permissions.read:
        tools.append("read")
    if permissions.write:
        tools.append("edit")

    for item in agent.metadata.tools.mcp:
        server = item.get("server")
        tool = item.get("tool")
        if not server:
            raise InvalidConfigSchemaError(
                agent.source_path,
                "Copilot agent MCP tools require a server",
            )
        tools.append(f"{server}/{tool}" if tool else f"{server}/*")
    return tools


class ClaudeAgentCompiler(IAgentCompiler):
    """Cross-compile for Claude Code subagents."""

    def compile(self, agent: Agent) -> str:
        return serialize_claude_agent(agent)
