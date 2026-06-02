"""Tests for skill compilers."""

from pathlib import Path

import pytest
import yaml

from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.skills.compilers import (
    ClaudeSkillCompiler,
    CodexSkillCompiler,
    CursorSkillCompiler,
    OpenCodeSkillCompiler,
)
from code_agnostic.skills.models import Skill, SkillMetadata, SkillToolPermissions


def _make_skill(
    name: str = "test-skill",
    description: str = "Test skill",
    read: bool = True,
    write: bool = False,
    content: str = "Skill body.\n",
) -> Skill:
    return Skill(
        name=name,
        source_path=Path(f"/fake/{name}/SKILL.md"),
        metadata=SkillMetadata(
            name=name,
            description=description,
            tools=SkillToolPermissions(read=read, write=write),
        ),
        content=content,
    )


def test_opencode_compiler_identity() -> None:
    skill = _make_skill()
    compiler = OpenCodeSkillCompiler()
    result = compiler.compile(skill)
    assert "test-skill" in result
    assert "Test skill" in result
    assert "Skill body." in result


def test_cursor_compiler() -> None:
    skill = _make_skill(write=True)
    compiler = CursorSkillCompiler()
    result = compiler.compile(skill)
    raw, body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert "test-skill" in result
    assert "tools" not in payload
    assert body.strip() == "Skill body."


def test_cursor_compiler_preserves_native_skill_overrides() -> None:
    skill = Skill(
        name="react-patterns",
        source_path=Path("/fake/react-patterns/SKILL.md"),
        metadata=SkillMetadata(
            name="react-patterns",
            description="React patterns",
            app_overrides={
                "cursor": {
                    "paths": ["**/*.tsx"],
                    "disable-model-invocation": True,
                    "metadata": {"team": "frontend"},
                }
            },
        ),
        content="Body.\n",
    )

    result = CursorSkillCompiler().compile(skill)
    raw, _body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload["paths"] == ["**/*.tsx"]
    assert payload["disable-model-invocation"] is True
    assert payload["metadata"] == {"team": "frontend"}


def test_cursor_compiler_rejects_unsupported_skill_overrides() -> None:
    skill = Skill(
        name="react-patterns",
        source_path=Path("/fake/react-patterns/SKILL.md"),
        metadata=SkillMetadata(
            name="react-patterns",
            description="React patterns",
            app_overrides={"cursor": {"permission": {"edit": False}}},
        ),
        content="Body.\n",
    )

    with pytest.raises(InvalidConfigSchemaError) as exc_info:
        CursorSkillCompiler().compile(skill)

    assert "x-cursor.permission is not supported" in exc_info.value.detail


def test_codex_compiler() -> None:
    skill = _make_skill(write=True)
    compiler = CodexSkillCompiler()
    result = compiler.compile(skill)
    raw, body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert "test-skill" in result
    assert "tools" not in payload
    assert body.strip() == "Skill body."


def test_codex_compiler_rejects_unsupported_skill_overrides() -> None:
    skill = Skill(
        name="docs-helper",
        source_path=Path("/fake/docs-helper/SKILL.md"),
        metadata=SkillMetadata(
            name="docs-helper",
            description="Docs helper",
            app_overrides={"codex": {"metadata": {"team": "docs"}}},
        ),
        content="Body.\n",
    )

    with pytest.raises(InvalidConfigSchemaError) as exc_info:
        CodexSkillCompiler().compile(skill)

    assert "x-codex.metadata is not supported" in exc_info.value.detail


def test_claude_compiler_preserves_native_skill_overrides() -> None:
    skill = Skill(
        name="reviewer",
        source_path=Path("/fake/reviewer/SKILL.md"),
        metadata=SkillMetadata(
            name="reviewer",
            description="Review code",
            app_overrides={
                "claude": {
                    "when_to_use": "Use for code review.",
                    "disable-model-invocation": True,
                }
            },
        ),
        content="Body.\n",
    )

    result = ClaudeSkillCompiler().compile(skill)
    raw, body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload["name"] == "reviewer"
    assert payload["description"] == "Review code"
    assert payload["when_to_use"] == "Use for code review."
    assert payload["disable-model-invocation"] is True
    assert body.strip() == "Body."


def test_opencode_compiler_omits_unsupported_tool_permissions() -> None:
    skill = Skill(
        name="mcp-skill",
        source_path=Path("/fake/mcp-skill/SKILL.md"),
        metadata=SkillMetadata(
            name="mcp-skill",
            description="MCP skill",
            tools=SkillToolPermissions(
                read=True,
                write=False,
                mcp=[{"server": "github", "tool": "create_pr"}],
            ),
        ),
        content="Body.\n",
    )
    compiler = OpenCodeSkillCompiler()
    result = compiler.compile(skill)
    raw, body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert "tools" not in payload
    assert body.strip() == "Body."


def test_opencode_compiler_preserves_native_skill_overrides() -> None:
    skill = Skill(
        name="release-helper",
        source_path=Path("/fake/release-helper/SKILL.md"),
        metadata=SkillMetadata(
            name="release-helper",
            description="Release helper",
            app_overrides={
                "opencode": {
                    "license": "MIT",
                    "compatibility": "opencode",
                    "metadata": {"audience": "maintainers"},
                }
            },
        ),
        content="Body.\n",
    )

    result = OpenCodeSkillCompiler().compile(skill)
    raw, _body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload["license"] == "MIT"
    assert payload["compatibility"] == "opencode"
    assert payload["metadata"] == {"audience": "maintainers"}


def test_opencode_compiler_rejects_unsupported_skill_overrides() -> None:
    skill = Skill(
        name="release-helper",
        source_path=Path("/fake/release-helper/SKILL.md"),
        metadata=SkillMetadata(
            name="release-helper",
            description="Release helper",
            app_overrides={
                "opencode": {
                    "permission": {"skill": {"secret-*": "deny"}},
                }
            },
        ),
        content="Body.\n",
    )

    with pytest.raises(InvalidConfigSchemaError) as exc_info:
        OpenCodeSkillCompiler().compile(skill)

    assert "x-opencode.permission is not supported" in exc_info.value.detail
