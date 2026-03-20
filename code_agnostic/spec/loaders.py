from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from code_agnostic.agents.models import (
    Agent,
    AgentCodexConfig,
    AgentMetadata,
    AgentSkillConfig,
    AgentToolPermissions,
)
from code_agnostic.apps.common.framework import format_schema_error
from code_agnostic.apps.common.models import MCPAuthDTO, MCPServerDTO, MCPServerType
from code_agnostic.errors import InvalidConfigSchemaError, MissingConfigFileError
from code_agnostic.rules.models import Rule, RuleMetadata
from code_agnostic.skills.models import Skill, SkillMetadata, SkillToolPermissions

_SCHEMA_DIR = Path(__file__).with_name("schemas")


def load_rule_bundle(path: Path) -> Rule:
    meta_path = path / "meta.yaml"
    prompt_path = path / "prompt.md"
    payload = _load_yaml(meta_path)
    _validate(meta_path, "rule.v1.schema.json", payload)
    prompt = _load_prompt(prompt_path)

    return Rule(
        name=path.name,
        source_path=prompt_path,
        metadata=RuleMetadata(
            description=str(payload.get("description", "")),
            globs=[str(item) for item in payload.get("globs", [])],
            always_apply=bool(payload.get("always_apply", False)),
        ),
        content=prompt,
    )


def load_skill_bundle(path: Path) -> Skill:
    meta_path = path / "meta.yaml"
    prompt_path = path / "prompt.md"
    payload = _load_yaml(meta_path)
    _validate(meta_path, "skill.v1.schema.json", payload)
    prompt = _load_prompt(prompt_path)

    tools = payload.get("tools", {})
    mcp_items = tools.get("mcp", [])

    return Skill(
        name=path.name,
        source_path=prompt_path,
        metadata=SkillMetadata(
            name=str(payload["name"]),
            description=str(payload.get("description", "")),
            tools=SkillToolPermissions(
                read=bool(tools.get("read", True)),
                write=bool(tools.get("write", False)),
                mcp=[dict(item) for item in mcp_items],
            ),
        ),
        content=prompt,
    )


def load_agent_bundle(path: Path) -> Agent:
    meta_path = path / "meta.yaml"
    prompt_path = path / "prompt.md"
    payload = _load_yaml(meta_path)
    _validate(meta_path, "agent.v1.schema.json", payload)
    prompt = _load_prompt(prompt_path)

    tools = payload.get("tools", {})
    codex = payload.get("codex", {})
    skills = codex.get("skills", {})

    return Agent(
        name=path.name,
        source_path=prompt_path,
        metadata=AgentMetadata(
            name=str(payload["name"]),
            description=str(payload.get("description", "")),
            model=str(payload.get("model", "")),
            model_reasoning_effort=str(payload.get("reasoning_effort", "")),
            sandbox_mode=str(payload.get("sandbox_mode", "")),
            nickname_candidates=[
                str(item) for item in payload.get("nickname_candidates", [])
            ],
            tools=AgentToolPermissions(
                read=bool(tools.get("read", True)),
                write=bool(tools.get("write", True)),
                mcp=[dict(item) for item in tools.get("mcp", [])],
            ),
            codex=AgentCodexConfig(
                mcp_servers={
                    str(name): dict(config)
                    for name, config in codex.get("mcp_servers", {}).items()
                },
                skills_config=[
                    AgentSkillConfig(
                        path=str(item["path"]),
                        enabled=(
                            bool(item["enabled"])
                            if "enabled" in item and item["enabled"] is not None
                            else None
                        ),
                    )
                    for item in skills.get("config", [])
                ],
            ),
        ),
        content=prompt,
    )


def load_mcp_base(path: Path) -> dict[str, MCPServerDTO]:
    payload = _load_yaml(path)
    _validate(path, "mcp.v1.schema.json", payload)

    result: dict[str, MCPServerDTO] = {}
    for name, config in payload.get("mcp_servers", {}).items():
        auth_raw = config.get("auth")
        auth = None
        if isinstance(auth_raw, dict):
            auth = MCPAuthDTO(
                client_id=str(auth_raw["client_id"]),
                client_secret=str(auth_raw["client_secret"]),
                scopes=[str(item) for item in auth_raw.get("scopes", [])],
                token_endpoint=(
                    str(auth_raw["token_endpoint"])
                    if auth_raw.get("token_endpoint")
                    else None
                ),
            )

        result[str(name)] = MCPServerDTO(
            name=str(name),
            type=MCPServerType(str(config["type"])),
            command=str(config["command"]) if config.get("command") else None,
            args=[str(item) for item in config.get("args", [])],
            url=str(config["url"]) if config.get("url") else None,
            headers={
                str(key): str(value) for key, value in config.get("headers", {}).items()
            },
            env={str(key): str(value) for key, value in config.get("env", {}).items()},
            auth=auth,
        )
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise MissingConfigFileError(path)
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise InvalidConfigSchemaError(path, str(exc)) from exc
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise InvalidConfigSchemaError(path, "must be a YAML object")
    return payload


def _load_prompt(path: Path) -> str:
    if not path.exists():
        raise MissingConfigFileError(path)
    return path.read_text(encoding="utf-8")


def _validate(path: Path, schema_name: str, payload: dict[str, Any]) -> None:
    schema = json.loads((_SCHEMA_DIR / schema_name).read_text(encoding="utf-8"))
    error = next(iter(Draft202012Validator(schema).iter_errors(payload)), None)
    if error is not None:
        raise InvalidConfigSchemaError(path, format_schema_error(error))
