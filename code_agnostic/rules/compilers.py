"""Per-editor rule compilers."""

from __future__ import annotations

from abc import ABC, abstractmethod

import yaml

from code_agnostic.rules.models import Rule


class IRuleCompiler(ABC):
    @abstractmethod
    def compile(self, rule: Rule) -> tuple[str, str]:
        """Return (filename, compiled_content) for target editor."""


class CursorRuleCompiler(IRuleCompiler):
    """Compile to Cursor .mdc format with camelCase frontmatter."""

    def compile(self, rule: Rule) -> tuple[str, str]:
        filename = f"{rule.name}.mdc"
        fm: dict = {}
        if rule.metadata.description:
            fm["description"] = rule.metadata.description
        if rule.metadata.globs:
            fm["globs"] = rule.metadata.globs
        fm["alwaysApply"] = rule.metadata.always_apply

        parts: list[str] = []
        parts.append("---")
        parts.append(yaml.dump(fm, default_flow_style=False, sort_keys=False).rstrip())
        parts.append("---")
        parts.append("")
        parts.append(rule.content)
        return filename, "\n".join(parts)


class OpenCodeRuleCompiler(IRuleCompiler):
    """Compile to AGENTS.md section for OpenCode."""

    def compile(self, rule: Rule) -> tuple[str, str]:
        filename = "AGENTS.md"
        header = f"## {rule.metadata.description or rule.name}"
        content = f"{header}\n\n{rule.content}"
        return filename, content


class CodexRuleCompiler(IRuleCompiler):
    """Compile to AGENTS.md section for Codex."""

    def compile(self, rule: Rule) -> tuple[str, str]:
        filename = "AGENTS.md"
        header = f"## {rule.metadata.description or rule.name}"
        content = f"{header}\n\n{rule.content}"
        return filename, content
