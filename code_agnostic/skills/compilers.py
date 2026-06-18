"""Per-editor skill compilers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import yaml

from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.skills.models import Skill

_CODEX_SKILL_FRONTMATTER_KEYS = frozenset({"name", "description"})
_CURSOR_SKILL_FRONTMATTER_KEYS = frozenset(
    {
        "name",
        "description",
        "paths",
        "globs",
        "disable-model-invocation",
        "metadata",
    }
)
_OPENCODE_SKILL_FRONTMATTER_KEYS = frozenset(
    {"name", "description", "license", "compatibility", "metadata"}
)
_CLAUDE_SKILL_FRONTMATTER_KEYS = frozenset(
    {"name", "description", "when_to_use", "disable-model-invocation", "metadata"}
)
_COPILOT_SKILL_FRONTMATTER_KEYS = frozenset({"name", "description", "license"})


class ISkillCompiler(ABC):
    @abstractmethod
    def compile(self, skill: Skill) -> str:
        """Return compiled SKILL.md content for target editor."""


class OpenCodeSkillCompiler(ISkillCompiler):
    """Cross-compile for OpenCode skills."""

    def compile(self, skill: Skill) -> str:
        return _compile_skill_markdown(
            skill=skill,
            target_app="opencode",
            allowed_override_keys=_OPENCODE_SKILL_FRONTMATTER_KEYS,
        )


def _compile_skill_markdown(
    *,
    skill: Skill,
    target_app: str,
    allowed_override_keys: frozenset[str],
) -> str:
    fm: dict[str, Any] = {}
    if skill.metadata.name:
        fm["name"] = skill.metadata.name
    if skill.metadata.description:
        fm["description"] = skill.metadata.description

    for key, value in skill.metadata.app_overrides.get(target_app, {}).items():
        if key not in allowed_override_keys:
            allowed = ", ".join(sorted(allowed_override_keys))
            raise InvalidConfigSchemaError(
                skill.source_path,
                f"x-{target_app}.{key} is not supported in {target_app} skill "
                f"frontmatter; allowed keys: {allowed}",
            )
        if key in fm:
            continue
        fm[key] = value

    parts: list[str] = []
    if fm:
        parts.append("---")
        parts.append(yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip())
        parts.append("---")
        parts.append("")

    parts.append(skill.content)
    return "\n".join(parts)


class CursorSkillCompiler(ISkillCompiler):
    """Cross-compile for Cursor."""

    def compile(self, skill: Skill) -> str:
        return _compile_skill_markdown(
            skill=skill,
            target_app="cursor",
            allowed_override_keys=_CURSOR_SKILL_FRONTMATTER_KEYS,
        )


class CodexSkillCompiler(ISkillCompiler):
    """Cross-compile for Codex."""

    def compile(self, skill: Skill) -> str:
        return _compile_skill_markdown(
            skill=skill,
            target_app="codex",
            allowed_override_keys=_CODEX_SKILL_FRONTMATTER_KEYS,
        )


class CopilotSkillCompiler(ISkillCompiler):
    """Cross-compile for GitHub Copilot agent skills."""

    def compile(self, skill: Skill) -> str:
        return _compile_skill_markdown(
            skill=skill,
            target_app="copilot",
            allowed_override_keys=_COPILOT_SKILL_FRONTMATTER_KEYS,
        )


class ClaudeSkillCompiler(ISkillCompiler):
    """Cross-compile for Claude Code."""

    def compile(self, skill: Skill) -> str:
        return _compile_skill_markdown(
            skill=skill,
            target_app="claude",
            allowed_override_keys=_CLAUDE_SKILL_FRONTMATTER_KEYS,
        )
