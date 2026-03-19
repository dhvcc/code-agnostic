"""OpenCode agent markdown conversion."""

from __future__ import annotations

from typing import Any

import yaml

from code_agnostic.agents.models import Agent


def serialize_opencode_agent(agent: Agent) -> str:
    fm: dict[str, Any] = {}
    if agent.metadata.name:
        fm["name"] = agent.metadata.name
    if agent.metadata.description:
        fm["description"] = agent.metadata.description
    if agent.metadata.model:
        fm["model"] = agent.metadata.model
    if agent.metadata.model_reasoning_effort:
        fm["reasoningEffort"] = agent.metadata.model_reasoning_effort

    tools: dict[str, Any] = {}
    if agent.metadata.tools.read is not True:
        tools["read"] = agent.metadata.tools.read
    if agent.metadata.tools.write is not True:
        tools["write"] = agent.metadata.tools.write
    if agent.metadata.tools.mcp:
        tools["mcp"] = agent.metadata.tools.mcp
    if tools:
        fm["tools"] = tools

    parts: list[str] = []
    if fm:
        parts.append("---")
        parts.append(yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip())
        parts.append("---")
        parts.append("")

    parts.append(agent.content)
    return "\n".join(parts)
