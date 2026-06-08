"""OpenCode agent markdown conversion."""

from __future__ import annotations

from typing import Any

import yaml

from code_agnostic.agents.models import Agent
from code_agnostic.errors import InvalidConfigSchemaError


def serialize_opencode_agent(agent: Agent) -> str:
    fm: dict[str, Any] = {}
    if agent.metadata.name:
        fm["name"] = agent.metadata.name
    if not agent.metadata.description:
        raise InvalidConfigSchemaError(
            agent.source_path,
            "OpenCode agents require a description",
        )
    fm["description"] = agent.metadata.description
    model = agent.metadata.effective_value("opencode", "model")
    if model:
        fm["model"] = model
    reasoning_effort = agent.metadata.effective_value("opencode", "reasoning_effort")
    if reasoning_effort:
        fm["reasoningEffort"] = reasoning_effort

    passthrough = agent.metadata.app_passthrough(
        "opencode",
        consumed_keys={
            "model",
            "reasoning_effort",
            "sandbox_mode",
            "nickname_candidates",
            "permission",
        },
    )

    permission = _merge_permission(
        _compile_permission(agent),
        agent.metadata.app_overrides.get("opencode", {}).get("permission"),
    )
    if permission:
        fm["permission"] = permission

    for key, value in passthrough.items():
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


def _compile_permission(agent: Agent) -> dict[str, Any]:
    permission: dict[str, Any] = {}
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


def _merge_permission(
    generated: dict[str, Any], override: Any | None
) -> dict[str, Any] | Any:
    if override is None:
        return generated
    if isinstance(override, dict):
        return {**generated, **override}
    return override
