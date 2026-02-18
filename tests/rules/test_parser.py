"""Tests for rule parser (YAML frontmatter + markdown)."""

from pathlib import Path

from code_agnostic.rules.models import Rule, RuleMetadata
from code_agnostic.rules.parser import parse_rule, serialize_rule


def test_parse_with_all_fields(tmp_path: Path) -> None:
    path = tmp_path / "python-style.md"
    path.write_text(
        "---\n"
        "description: Python coding standards\n"
        "globs:\n"
        '  - "*.py"\n'
        '  - "src/**/*.py"\n'
        "always_apply: false\n"
        "---\n"
        "\n"
        "Always use type hints.\n",
        encoding="utf-8",
    )
    rule = parse_rule(path)
    assert rule.name == "python-style"
    assert rule.metadata.description == "Python coding standards"
    assert rule.metadata.globs == ["*.py", "src/**/*.py"]
    assert rule.metadata.always_apply is False
    assert "Always use type hints." in rule.content


def test_parse_minimal_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "minimal.md"
    path.write_text(
        "---\n" "description: Minimal rule\n" "---\n" "\n" "Content here.\n",
        encoding="utf-8",
    )
    rule = parse_rule(path)
    assert rule.metadata.description == "Minimal rule"
    assert rule.metadata.globs == []
    assert rule.metadata.always_apply is False


def test_parse_no_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "plain.md"
    path.write_text("# Just Markdown\n\nNo frontmatter here.\n", encoding="utf-8")
    rule = parse_rule(path)
    assert rule.metadata.description == ""
    assert rule.metadata.globs == []
    assert rule.metadata.always_apply is False
    assert "# Just Markdown" in rule.content


def test_parse_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.md"
    path.write_text("", encoding="utf-8")
    rule = parse_rule(path)
    assert rule.name == "empty"
    assert rule.content == ""


def test_parse_always_apply_true(tmp_path: Path) -> None:
    path = tmp_path / "global.md"
    path.write_text(
        "---\n"
        "description: Global rule\n"
        "always_apply: true\n"
        "---\n"
        "\n"
        "Applies everywhere.\n",
        encoding="utf-8",
    )
    rule = parse_rule(path)
    assert rule.metadata.always_apply is True


def test_serialize_roundtrip(tmp_path: Path) -> None:
    metadata = RuleMetadata(
        description="Roundtrip test",
        globs=["*.py"],
        always_apply=True,
    )
    rule = Rule(
        name="roundtrip",
        source_path=tmp_path / "roundtrip.md",
        metadata=metadata,
        content="Body content.\n",
    )
    text = serialize_rule(rule)
    path = tmp_path / "roundtrip.md"
    path.write_text(text, encoding="utf-8")

    parsed = parse_rule(path)
    assert parsed.metadata.description == "Roundtrip test"
    assert parsed.metadata.globs == ["*.py"]
    assert parsed.metadata.always_apply is True
    assert "Body content." in parsed.content
