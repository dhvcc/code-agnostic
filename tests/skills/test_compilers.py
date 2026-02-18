"""Tests for skill compilers."""

from pathlib import Path

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


def test_opencode_compiler_preserves_mcp_tools() -> None:
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
    assert "github" in result
    assert "create_pr" in result
