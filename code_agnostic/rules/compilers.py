"""Rule compiler.

Rules compile to a single `AGENTS.md` section format consumed natively by every
supported editor (Cursor/OpenCode/Codex/Copilot), and mirrored into
`CLAUDE.local.md` for Claude. There is intentionally one compiler — the per-editor
`.mdc`/native variants were removed in favour of the standardized `AGENTS.md` API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from code_agnostic.rules.models import Rule


class IRuleCompiler(ABC):
    @abstractmethod
    def compile(self, rule: Rule) -> tuple[str, str]:
        """Return (filename, compiled_content) for the target editor."""


class AgentsRuleCompiler(IRuleCompiler):
    """Compile a rule to an `AGENTS.md` section."""

    def compile(self, rule: Rule) -> tuple[str, str]:
        filename = "AGENTS.md"
        header = f"## {rule.metadata.description or rule.name}"
        content = f"{header}\n\n{rule.content}"
        return filename, content
