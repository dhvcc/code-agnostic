"""Tests for rule compilers."""

from pathlib import Path

from code_agnostic.rules.compilers import AgentsRuleCompiler
from code_agnostic.rules.models import Rule, RuleMetadata


def _make_rule(
    name: str = "test-rule",
    description: str = "Test rule",
    globs: list[str] | None = None,
    always_apply: bool = False,
    content: str = "Rule body content.\n",
) -> Rule:
    return Rule(
        name=name,
        source_path=Path(f"/fake/{name}.md"),
        metadata=RuleMetadata(
            description=description,
            globs=globs or [],
            always_apply=always_apply,
        ),
        content=content,
    )


def test_agents_compiler() -> None:
    rule = _make_rule(description="Python standards")
    compiler = AgentsRuleCompiler()
    filename, content = compiler.compile(rule)
    assert filename == "AGENTS.md"
    assert "## Python standards" in content
    assert "Rule body content." in content


def test_agents_compiler_no_description_uses_name() -> None:
    rule = _make_rule(description="")
    compiler = AgentsRuleCompiler()
    _, content = compiler.compile(rule)
    assert "## test-rule" in content
