"""Codex subagent TOML conversion."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

import tomlkit

from code_agnostic.agents.models import (
    Agent,
    AgentCodexConfig,
    AgentMetadata,
    AgentSkillConfig,
    AgentToolPermissions,
    normalize_agent_override_key,
)

_SAFE_FILE_STEM_RE = re.compile(r"[^A-Za-z0-9_-]+")


def normalize_codex_agent_filename(name: str, fallback: str) -> str:
    candidate = name.strip() or fallback.strip()
    normalized = _SAFE_FILE_STEM_RE.sub("-", candidate).strip("-_")
    return normalized or fallback


def parse_codex_agent(path: Path) -> Agent:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    name = str(payload.get("name", path.stem))

    nickname_candidates = payload.get("nickname_candidates", [])
    if not isinstance(nickname_candidates, list):
        nickname_candidates = []

    codex = AgentCodexConfig(
        mcp_servers=_coerce_mcp_servers(payload.get("mcp_servers")),
        skills_config=_coerce_skills_config(payload.get("skills")),
    )

    metadata = AgentMetadata(
        name=name,
        description=str(payload.get("description", "")),
        model=str(payload.get("model", "")),
        model_reasoning_effort=str(payload.get("model_reasoning_effort", "")),
        sandbox_mode=str(payload.get("sandbox_mode", "")),
        nickname_candidates=[
            str(item) for item in nickname_candidates if isinstance(item, str)
        ],
        tools=AgentToolPermissions(),
        app_overrides={"codex": _coerce_codex_app_overrides(payload)},
        codex=codex,
    )
    content = str(payload.get("developer_instructions", ""))
    return Agent(name=path.stem, source_path=path, metadata=metadata, content=content)


def serialize_codex_agent(agent: Agent) -> str:
    instructions = agent.content
    if not instructions.strip():
        raise ValueError(f"Codex subagent requires instructions: {agent.source_path}")

    description = agent.metadata.description or agent.metadata.name or agent.name

    doc = tomlkit.document()
    doc.add("name", agent.metadata.name or agent.name)
    doc.add("description", description)
    if agent.metadata.nickname_candidates:
        doc.add("nickname_candidates", list(agent.metadata.nickname_candidates))
    model = agent.metadata.effective_value("codex", "model")
    if model:
        doc.add("model", model)
    reasoning_effort = agent.metadata.effective_value("codex", "reasoning_effort")
    if reasoning_effort:
        doc.add("model_reasoning_effort", reasoning_effort)
    sandbox_mode = agent.metadata.effective_value("codex", "sandbox_mode")
    if sandbox_mode:
        doc.add("sandbox_mode", sandbox_mode)
    doc.add("developer_instructions", tomlkit.string(instructions, multiline=True))

    if agent.metadata.codex.mcp_servers:
        doc.add("mcp_servers", _toml_item(agent.metadata.codex.mcp_servers))

    if agent.metadata.codex.skills_config:
        skills = tomlkit.table()
        skills.add(
            "config",
            _toml_item(
                [
                    _skill_config_to_dict(item)
                    for item in agent.metadata.codex.skills_config
                ]
            ),
        )
        doc.add("skills", skills)

    for key, value in agent.metadata.app_passthrough(
        "codex",
        consumed_keys={
            "model",
            "reasoning_effort",
            "sandbox_mode",
            "nickname_candidates",
        },
    ).items():
        if key in doc:
            continue
        doc.add(key, _toml_item(value))

    return tomlkit.dumps(doc)


def _coerce_mcp_servers(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for key, value in raw.items():
        if isinstance(key, str) and isinstance(value, dict):
            result[key] = value
    return result


def _coerce_skills_config(raw: Any) -> list[AgentSkillConfig]:
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


def _skill_config_to_dict(item: AgentSkillConfig) -> dict[str, Any]:
    payload: dict[str, Any] = {"path": item.path}
    if item.enabled is not None:
        payload["enabled"] = item.enabled
    return payload


def _toml_item(value: Any) -> Any:
    if isinstance(value, dict):
        table = tomlkit.table()
        for key, child in value.items():
            table.add(key, _toml_item(child))
        return table
    if isinstance(value, list):
        array = tomlkit.array()
        for item in value:
            if isinstance(item, dict):
                inline = tomlkit.inline_table()
                for key, child in item.items():
                    inline[key] = _toml_item(child)
                array.append(inline)
            else:
                array.append(_toml_item(item))
        return array
    return value


def _coerce_codex_app_overrides(payload: dict[str, Any]) -> dict[str, Any]:
    known_keys = {
        "name",
        "description",
        "model",
        "model_reasoning_effort",
        "sandbox_mode",
        "nickname_candidates",
        "developer_instructions",
        "mcp_servers",
        "skills",
    }
    return {
        normalize_agent_override_key(str(key)): value
        for key, value in payload.items()
        if key not in known_keys
    }
