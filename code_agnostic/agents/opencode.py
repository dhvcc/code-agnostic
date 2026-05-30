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
    model = agent.metadata.effective_value("opencode", "model")
    if model:
        fm["model"] = model
    reasoning_effort = agent.metadata.effective_value("opencode", "reasoning_effort")
    if reasoning_effort:
        fm["reasoningEffort"] = reasoning_effort

    permission = _compile_permission(agent)
    if permission:
        fm["permission"] = permission

    for key, value in agent.metadata.app_passthrough(
        "opencode",
        consumed_keys={
            "model",
            "reasoning_effort",
            "sandbox_mode",
            "nickname_candidates",
        },
    ).items():
        if key in fm:
            continue
        fm[key] = value

    parts: list[str] = []
    if fm:
        parts.append("---")
        parts.append(yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip())
        parts.append("---")
        parts.append("")

    parts.append(agent.content)
    return "\n".join(parts)


def _compile_permission(agent: Agent) -> dict[str, str]:
    permission: dict[str, str] = {}
    permission["read"] = "allow" if agent.metadata.tools.read else "deny"
    permission["edit"] = "allow" if agent.metadata.tools.write else "deny"
    for item in agent.metadata.tools.mcp:
        server = item.get("server")
        if not server:
            continue
        tool = item.get("tool")
        key = f"{server}_{tool}" if tool else f"{server}_*"
        permission[key] = "allow"
    return permission
