"""Tests for rule compilers."""

from pathlib import Path

from code_agnostic.rules.compilers import (
    CodexRuleCompiler,
    CursorRuleCompiler,
    OpenCodeRuleCompiler,
)
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


def test_cursor_compiler_always_apply() -> None:
    rule = _make_rule(always_apply=True)
    compiler = CursorRuleCompiler()
    filename, content = compiler.compile(rule)
    assert filename == "test-rule.mdc"
    assert "alwaysApply: true" in content
    assert "Rule body content." in content


def test_cursor_compiler_not_always_apply() -> None:
    rule = _make_rule(always_apply=False)
    compiler = CursorRuleCompiler()
    filename, content = compiler.compile(rule)
    assert "alwaysApply: false" in content


def test_cursor_compiler_with_globs() -> None:
    rule = _make_rule(globs=["*.py", "src/**/*.py"])
    compiler = CursorRuleCompiler()
    filename, content = compiler.compile(rule)
    assert "*.py" in content
    assert "src/**/*.py" in content


def test_cursor_compiler_with_description() -> None:
    rule = _make_rule(description="Python style guide")
    compiler = CursorRuleCompiler()
    _, content = compiler.compile(rule)
    assert "Python style guide" in content


def test_opencode_compiler() -> None:
    rule = _make_rule(description="Python standards")
    compiler = OpenCodeRuleCompiler()
    filename, content = compiler.compile(rule)
    assert filename == "AGENTS.md"
    assert "## Python standards" in content
    assert "Rule body content." in content


def test_opencode_compiler_no_description_uses_name() -> None:
    rule = _make_rule(description="")
    compiler = OpenCodeRuleCompiler()
    _, content = compiler.compile(rule)
    assert "## test-rule" in content


def test_codex_compiler() -> None:
    rule = _make_rule(description="Codex standards")
    compiler = CodexRuleCompiler()
    filename, content = compiler.compile(rule)
    assert filename == "AGENTS.md"
    assert "## Codex standards" in content
    assert "Rule body content." in content
