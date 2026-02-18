"""Parse and serialize skills with YAML frontmatter."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from code_agnostic.skills.models import Skill, SkillMetadata, SkillToolPermissions

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_skill(path: Path) -> Skill:
    text = path.read_text(encoding="utf-8")
    name = path.parent.name if path.name == "SKILL.md" else path.stem

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

    tools = SkillToolPermissions(
        read=bool(tools_raw.get("read", True)),
        write=bool(tools_raw.get("write", False)),
        mcp=[m for m in mcp_raw if isinstance(m, dict)],
    )

    metadata = SkillMetadata(
        name=str(raw.get("name", name)),
        description=str(raw.get("description", "")),
        tools=tools,
    )
    return Skill(name=name, source_path=path, metadata=metadata, content=content)


def serialize_skill(skill: Skill) -> str:
    fm: dict = {}
    if skill.metadata.name:
        fm["name"] = skill.metadata.name
    if skill.metadata.description:
        fm["description"] = skill.metadata.description

    tools: dict = {}
    if skill.metadata.tools.read is not True:
        tools["read"] = skill.metadata.tools.read
    if skill.metadata.tools.write is not False:
        tools["write"] = skill.metadata.tools.write
    if skill.metadata.tools.mcp:
        tools["mcp"] = skill.metadata.tools.mcp
    if tools:
        fm["tools"] = tools

    parts: list[str] = []
    if fm:
        parts.append("---")
        parts.append(yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip())
        parts.append("---")
        parts.append("")

    parts.append(skill.content)
    return "\n".join(parts)
