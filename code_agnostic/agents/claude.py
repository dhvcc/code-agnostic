"""Claude Code subagent Markdown conversion."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from code_agnostic.agents.models import Agent

_SAFE_FILE_STEM_RE = re.compile(r"[^A-Za-z0-9_-]+")


def normalize_claude_agent_filename(name: str, fallback: str) -> str:
    candidate = name.strip() or fallback.strip()
    normalized = _SAFE_FILE_STEM_RE.sub("-", candidate).strip("-_")
    return normalized or fallback


def serialize_claude_agent(agent: Agent) -> str:
    fm: dict[str, Any] = {}
    if agent.metadata.name:
        fm["name"] = agent.metadata.name
    else:
        fm["name"] = agent.name

    description = agent.metadata.description or agent.metadata.name or agent.name
    if description:
        fm["description"] = description

    model = agent.metadata.effective_value("claude", "model")
    if model:
        fm["model"] = model
    reasoning_effort = agent.metadata.effective_value("claude", "reasoning_effort")
    if reasoning_effort:
        fm["effort"] = reasoning_effort

    for key, value in agent.metadata.app_passthrough(
        "claude",
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

    parts = [
        "---",
        yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip(),
        "---",
        "",
        agent.content,
    ]
    return "\n".join(parts)


def claude_agent_target_path(target_dir: Path, agent: Agent) -> Path:
    return (
        target_dir
        / f"{normalize_claude_agent_filename(agent.metadata.name, agent.name)}.md"
    )
