"""Parse and serialize agents with YAML frontmatter."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from code_agnostic.agents.models import (
    Agent,
    AgentCodexConfig,
    AgentMetadata,
    AgentSkillConfig,
    AgentToolPermissions,
)
from code_agnostic.spec.loaders import load_agent_bundle

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_agent(path: Path) -> Agent:
    if _is_agent_bundle_dir(path):
        return load_agent_bundle(path)

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

    nickname_candidates_raw = raw.get("nickname_candidates", [])
    if not isinstance(nickname_candidates_raw, list):
        nickname_candidates_raw = []

    codex_raw = raw.get("codex", {})
    if not isinstance(codex_raw, dict):
        codex_raw = {}

    tools = AgentToolPermissions(
        read=bool(tools_raw.get("read", True)),
        write=bool(tools_raw.get("write", True)),
        mcp=[m for m in mcp_raw if isinstance(m, dict)],
    )

    metadata = AgentMetadata(
        name=str(raw.get("name", name)),
        description=str(raw.get("description", "")),
        model=str(raw.get("model", "")),
        model_reasoning_effort=str(
            raw.get("model_reasoning_effort", raw.get("reasoningEffort", ""))
        ),
        sandbox_mode=str(raw.get("sandbox_mode", "")),
        nickname_candidates=[
            str(item) for item in nickname_candidates_raw if isinstance(item, str)
        ],
        tools=tools,
        codex=AgentCodexConfig(
            mcp_servers=_coerce_mcp_servers(codex_raw.get("mcp_servers")),
            skills_config=_coerce_skill_configs(codex_raw.get("skills")),
        ),
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
    if agent.metadata.model_reasoning_effort:
        fm["model_reasoning_effort"] = agent.metadata.model_reasoning_effort
    if agent.metadata.sandbox_mode:
        fm["sandbox_mode"] = agent.metadata.sandbox_mode
    if agent.metadata.nickname_candidates:
        fm["nickname_candidates"] = list(agent.metadata.nickname_candidates)

    tools: dict = {}
    if agent.metadata.tools.read is not True:
        tools["read"] = agent.metadata.tools.read
    if agent.metadata.tools.write is not True:
        tools["write"] = agent.metadata.tools.write
    if agent.metadata.tools.mcp:
        tools["mcp"] = agent.metadata.tools.mcp
    if tools:
        fm["tools"] = tools

    codex = _serialize_codex(agent.metadata.codex)
    if codex:
        fm["codex"] = codex

    parts: list[str] = []
    if fm:
        parts.append("---")
        parts.append(yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip())
        parts.append("---")
        parts.append("")

    parts.append(agent.content)
    return "\n".join(parts)


def _coerce_mcp_servers(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, dict):
            result[key] = value
    return result


def _coerce_skill_configs(raw: Any) -> list[AgentSkillConfig]:
    if not isinstance(raw, dict):
        return []
    config = raw.get("config")
    if not isinstance(config, list):
        return []

    result: list[AgentSkillConfig] = []
    for item in config:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        enabled = item.get("enabled")
        if not isinstance(path, str):
            continue
        if enabled is not None and not isinstance(enabled, bool):
            enabled = None
        result.append(AgentSkillConfig(path=path, enabled=enabled))
    return result


def _serialize_codex(codex: AgentCodexConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if codex.mcp_servers:
        payload["mcp_servers"] = codex.mcp_servers
    if codex.skills_config:
        payload["skills"] = {
            "config": [_serialize_skill_config(item) for item in codex.skills_config]
        }
    return payload


def _serialize_skill_config(item: AgentSkillConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {"path": item.path}
    if item.enabled is not None:
        payload["enabled"] = item.enabled
    return payload


def _is_agent_bundle_dir(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "meta.yaml").exists()
        and (path / "prompt.md").exists()
    )
