"""GitHub Copilot custom agent Markdown conversion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from code_agnostic.agents.models import Agent, AgentMetadata, AgentToolPermissions

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_READ_ALIASES = {"read", "notebookread", "view"}
_WRITE_ALIASES = {"edit", "multiedit", "write", "notebookedit"}


@dataclass(frozen=True)
class CopilotAgentParseResult:
    agent: Agent
    warnings: list[str]


def parse_copilot_agent(path: Path) -> CopilotAgentParseResult:
    text = path.read_text(encoding="utf-8")
    raw: dict[str, Any]
    match = _FRONTMATTER_RE.match(text)
    if match:
        raw = yaml.safe_load(match.group(1)) or {}
        content = text[match.end() :]
    else:
        raw = {}
        content = text
    if not isinstance(raw, dict):
        raw = {}

    fallback_name = _copilot_agent_stem(path)
    tools, warnings = _parse_copilot_tools(raw.get("tools"), path)
    agent = Agent(
        name=fallback_name,
        source_path=path,
        metadata=AgentMetadata(
            name=str(raw.get("name", fallback_name)),
            description=str(raw.get("description", "")),
            model=str(raw.get("model", "")),
            tools=tools,
        ),
        content=content,
    )
    return CopilotAgentParseResult(agent=agent, warnings=warnings)


def copilot_agent_filename(path: Path) -> str:
    return f"{_copilot_agent_stem(path)}.agent.md"


def _copilot_agent_stem(path: Path) -> str:
    name = path.name
    if name.endswith(".agent.md"):
        return name[: -len(".agent.md")]
    if name.endswith(".md"):
        return name[: -len(".md")]
    return path.stem


def _parse_copilot_tools(
    raw: Any, path: Path
) -> tuple[AgentToolPermissions, list[str]]:
    if raw is None:
        return AgentToolPermissions(), []

    tokens = _coerce_tool_tokens(raw)
    if tokens is None:
        return AgentToolPermissions(), [
            f"Skipped unrepresentable Copilot tools: {path}"
        ]

    if "*" in tokens:
        return AgentToolPermissions(), []

    read = False
    write = False
    mcp: list[dict[str, str]] = []
    unsupported: list[str] = []
    for token in tokens:
        normalized = token.lower()
        if normalized in _READ_ALIASES:
            read = True
            continue
        if normalized in _WRITE_ALIASES:
            write = True
            continue
        if "/" in token:
            server, tool = token.split("/", 1)
            if server and tool:
                item = {"server": server}
                if tool != "*":
                    item["tool"] = tool
                mcp.append(item)
                continue
        unsupported.append(token)

    if unsupported:
        return AgentToolPermissions(), [
            f"Skipped unrepresentable Copilot tools in {path}: {', '.join(unsupported)}"
        ]

    return AgentToolPermissions(read=read, write=write, mcp=mcp), []


def _coerce_tool_tokens(raw: Any) -> list[str] | None:
    if isinstance(raw, str):
        return [item.strip() for item in raw.split(",") if item.strip()]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, str)]
    return None
