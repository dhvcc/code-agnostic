"""Parse and serialize rules with YAML frontmatter."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from code_agnostic.rules.models import Rule, RuleMetadata

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_rule(path: Path) -> Rule:
    text = path.read_text(encoding="utf-8")
    name = path.stem

    match = _FRONTMATTER_RE.match(text)
    if match:
        raw = yaml.safe_load(match.group(1)) or {}
        content = text[match.end() :]
    else:
        raw = {}
        content = text

    globs = raw.get("globs", [])
    if not isinstance(globs, list):
        globs = []

    metadata = RuleMetadata(
        description=str(raw.get("description", "")),
        globs=[str(g) for g in globs],
        always_apply=bool(raw.get("always_apply", False)),
    )
    return Rule(name=name, source_path=path, metadata=metadata, content=content)


def serialize_rule(rule: Rule) -> str:
    fm: dict = {}
    if rule.metadata.description:
        fm["description"] = rule.metadata.description
    if rule.metadata.globs:
        fm["globs"] = rule.metadata.globs
    if rule.metadata.always_apply:
        fm["always_apply"] = True

    parts: list[str] = []
    if fm:
        parts.append("---")
        parts.append(yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip())
        parts.append("---")
        parts.append("")

    parts.append(rule.content)
    return "\n".join(parts)
