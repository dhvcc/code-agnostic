"""Tests for skill parser."""

from pathlib import Path

from code_agnostic.skills.models import Skill, SkillMetadata, SkillToolPermissions
from code_agnostic.skills.parser import parse_skill, serialize_skill


def test_parse_full_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "code-reviewer"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: code-reviewer\n"
        "description: Reviews code for quality\n"
        "tools:\n"
        "  read: true\n"
        "  write: false\n"
        "  mcp:\n"
        "    - server: github\n"
        "      tool: create_pull_request_review\n"
        "---\n"
        "\n"
        "# Code Reviewer\n\n"
        "Review all code changes.\n",
        encoding="utf-8",
    )
    skill = parse_skill(skill_dir / "SKILL.md")
    assert skill.name == "code-reviewer"
    assert skill.metadata.description == "Reviews code for quality"
    assert skill.metadata.tools.read is True
    assert skill.metadata.tools.write is False
    assert len(skill.metadata.tools.mcp) == 1
    assert skill.metadata.tools.mcp[0]["server"] == "github"
    assert "Review all code changes." in skill.content


def test_parse_no_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "simple"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "# Simple Skill\n\nJust content.\n",
        encoding="utf-8",
    )
    skill = parse_skill(skill_dir / "SKILL.md")
    assert skill.name == "simple"
    assert skill.metadata.description == ""
    assert skill.metadata.tools.read is True
    assert skill.metadata.tools.write is False
    assert "# Simple Skill" in skill.content


def test_parse_minimal_frontmatter(tmp_path: Path) -> None:
    skill_dir = tmp_path / "minimal"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: minimal\n---\n\nContent.\n",
        encoding="utf-8",
    )
    skill = parse_skill(skill_dir / "SKILL.md")
    assert skill.metadata.name == "minimal"
    assert skill.metadata.tools.mcp == []


def test_serialize_roundtrip(tmp_path: Path) -> None:
    skill = Skill(
        name="test-skill",
        source_path=tmp_path / "test-skill" / "SKILL.md",
        metadata=SkillMetadata(
            name="test-skill",
            description="A test skill",
            tools=SkillToolPermissions(read=True, write=True),
        ),
        content="Skill body.\n",
    )
    text = serialize_skill(skill)
    path = tmp_path / "test-skill"
    path.mkdir(parents=True)
    (path / "SKILL.md").write_text(text, encoding="utf-8")

    parsed = parse_skill(path / "SKILL.md")
    assert parsed.metadata.name == "test-skill"
    assert parsed.metadata.description == "A test skill"
    assert parsed.metadata.tools.write is True
    assert "Skill body." in parsed.content
