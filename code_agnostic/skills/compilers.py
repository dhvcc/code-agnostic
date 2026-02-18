"""Per-editor skill compilers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from code_agnostic.skills.models import Skill
from code_agnostic.skills.parser import serialize_skill


class ISkillCompiler(ABC):
    @abstractmethod
    def compile(self, skill: Skill) -> str:
        """Return compiled SKILL.md content for target editor."""


class OpenCodeSkillCompiler(ISkillCompiler):
    """Near-identity: OpenCode format IS the canonical format."""

    def compile(self, skill: Skill) -> str:
        return serialize_skill(skill)


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
