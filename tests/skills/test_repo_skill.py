from pathlib import Path

from code_agnostic.skills.parser import parse_skill


def test_code_agnostic_skill_is_installable() -> None:
    skill_path = Path(__file__).parents[2] / "skills" / "code-agnostic" / "SKILL.md"

    skill = parse_skill(skill_path)

    assert skill.metadata.name == "code-agnostic"
    assert "MCP" in skill.metadata.description
    assert "plan" in skill.content
    assert "apply" in skill.content
