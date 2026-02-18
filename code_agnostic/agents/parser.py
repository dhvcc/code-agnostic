"""Parse and serialize agents with YAML frontmatter."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from code_agnostic.agents.models import Agent, AgentMetadata, AgentToolPermissions

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_agent(path: Path) -> Agent:
    text = path.read_text(encoding="utf-8")
    name = path.stem

    match = _FRONTMATTER_RE.match(text)
    if match:
        raw = yaml.safe_load(match.group(1)) or {}
        content = text[match.end() :]
    else:
        raw = {}
        content = text

    tools_raw = raw.get("tools", {})
    if not isinstance(tools_raw, dict):
        tools_raw = {}

    mcp_raw = tools_raw.get("mcp", [])
    if not isinstance(mcp_raw, list):
        mcp_raw = []

    tools = AgentToolPermissions(
        read=bool(tools_raw.get("read", True)),
        write=bool(tools_raw.get("write", True)),
        mcp=[m for m in mcp_raw if isinstance(m, dict)],
    )

    metadata = AgentMetadata(
        name=str(raw.get("name", name)),
        description=str(raw.get("description", "")),
        model=str(raw.get("model", "")),
        tools=tools,
    )
    return Agent(name=name, source_path=path, metadata=metadata, content=content)


def serialize_agent(agent: Agent) -> str:
    fm: dict = {}
    if agent.metadata.name:
        fm["name"] = agent.metadata.name
    if agent.metadata.description:
        fm["description"] = agent.metadata.description
    if agent.metadata.model:
        fm["model"] = agent.metadata.model

    tools: dict = {}
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
