"""Tests for skill compilers."""

from pathlib import Path

import pytest
import yaml

from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.skills.compilers import (
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
    assert "test-skill" in result
    assert "Skill body." in result


def test_codex_compiler() -> None:
    skill = _make_skill()
    compiler = CodexSkillCompiler()
    result = compiler.compile(skill)
    assert "test-skill" in result
    assert "Skill body." in result


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
