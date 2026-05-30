"""Per-editor skill compilers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import yaml

from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.skills.models import Skill
from code_agnostic.skills.parser import serialize_skill

_OPENCODE_SKILL_FRONTMATTER_KEYS = frozenset(
    {"name", "description", "license", "compatibility", "metadata"}
)


class ISkillCompiler(ABC):
    @abstractmethod
    def compile(self, skill: Skill) -> str:
        """Return compiled SKILL.md content for target editor."""


class OpenCodeSkillCompiler(ISkillCompiler):
    """Cross-compile for OpenCode skills."""

    def compile(self, skill: Skill) -> str:
        fm: dict[str, Any] = {}
        if skill.metadata.name:
            fm["name"] = skill.metadata.name
        if skill.metadata.description:
            fm["description"] = skill.metadata.description

        for key, value in skill.metadata.app_overrides.get("opencode", {}).items():
            if key not in _OPENCODE_SKILL_FRONTMATTER_KEYS:
                allowed = ", ".join(sorted(_OPENCODE_SKILL_FRONTMATTER_KEYS))
                raise InvalidConfigSchemaError(
                    skill.source_path,
                    f"x-opencode.{key} is not supported in OpenCode skill "
                    f"frontmatter; allowed keys: {allowed}",
                )
            if key in fm:
                continue
            fm[key] = value

        parts: list[str] = []
        if fm:
            parts.append("---")
            parts.append(
                yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip()
            )
            parts.append("---")
            parts.append("")

        parts.append(skill.content)
        return "\n".join(parts)


class CursorSkillCompiler(ISkillCompiler):
    """Cross-compile for Cursor.

    Cursor doesn't have tool-level granularity in skills,
    so we keep the content and add a note about permissions.
    """

    def compile(self, skill: Skill) -> str:
        return serialize_skill(skill)


class CodexSkillCompiler(ISkillCompiler):
    """Cross-compile for Codex."""

    def compile(self, skill: Skill) -> str:
        return serialize_skill(skill)
