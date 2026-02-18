"""Tests for RulesRepository."""

from pathlib import Path

from code_agnostic.rules.models import RuleMetadata
from code_agnostic.rules.repository import RulesRepository


def test_list_empty(tmp_path: Path) -> None:
    repo = RulesRepository(tmp_path)
    assert repo.list_rules() == []


def test_list_populated(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "alpha.md").write_text(
        "---\ndescription: Alpha\n---\n\nAlpha content.\n", encoding="utf-8"
    )
    (rules_dir / "beta.md").write_text(
        "---\ndescription: Beta\n---\n\nBeta content.\n", encoding="utf-8"
    )
    repo = RulesRepository(tmp_path)
    rules = repo.list_rules()
    assert len(rules) == 2
    assert rules[0].name == "alpha"
    assert rules[1].name == "beta"


def test_save_and_get(tmp_path: Path) -> None:
    repo = RulesRepository(tmp_path)
    metadata = RuleMetadata(description="Test rule", globs=["*.py"])
    repo.save_rule("test-rule", "Rule body.\n", metadata)

    rule = repo.get_rule("test-rule")
    assert rule is not None
    assert rule.metadata.description == "Test rule"
    assert rule.metadata.globs == ["*.py"]
    assert "Rule body." in rule.content


def test_get_nonexistent(tmp_path: Path) -> None:
    repo = RulesRepository(tmp_path)
    assert repo.get_rule("nope") is None


def test_remove_existing(tmp_path: Path) -> None:
    repo = RulesRepository(tmp_path)
    metadata = RuleMetadata(description="Remove me")
    repo.save_rule("removable", "content", metadata)
    assert repo.remove_rule("removable") is True
    assert repo.get_rule("removable") is None


def test_remove_nonexistent(tmp_path: Path) -> None:
    repo = RulesRepository(tmp_path)
    assert repo.remove_rule("nope") is False


def test_ignores_dotfiles(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / ".hidden.md").write_text("hidden", encoding="utf-8")
    (rules_dir / "visible.md").write_text("visible", encoding="utf-8")
    repo = RulesRepository(tmp_path)
    rules = repo.list_rules()
    assert len(rules) == 1
    assert rules[0].name == "visible"


def test_ignores_non_md_files(tmp_path: Path) -> None:
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "readme.txt").write_text("text", encoding="utf-8")
    (rules_dir / "rule.md").write_text(
        "---\ndescription: Real\n---\n\nContent.\n", encoding="utf-8"
    )
    repo = RulesRepository(tmp_path)
    rules = repo.list_rules()
    assert len(rules) == 1
    assert rules[0].name == "rule"
