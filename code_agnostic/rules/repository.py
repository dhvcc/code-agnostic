"""Repository for rule CRUD operations."""

from __future__ import annotations

from pathlib import Path

from code_agnostic.rules.models import Rule, RuleMetadata
from code_agnostic.rules.parser import parse_rule, serialize_rule


class RulesRepository:
    def __init__(self, root: Path) -> None:
        self._rules_dir = root / "rules"

    @property
    def rules_dir(self) -> Path:
        return self._rules_dir

    def list_rules(self) -> list[Rule]:
        if not self._rules_dir.exists():
            return []
        rules: list[Rule] = []
        for child in sorted(self._rules_dir.iterdir()):
            if child.suffix == ".md" and not child.name.startswith("."):
                rules.append(parse_rule(child))
        return rules

    def get_rule(self, name: str) -> Rule | None:
        path = self._rules_dir / f"{name}.md"
        if not path.exists():
            return None
        return parse_rule(path)

    def save_rule(self, name: str, content: str, metadata: RuleMetadata) -> Rule:
        self._rules_dir.mkdir(parents=True, exist_ok=True)
        path = self._rules_dir / f"{name}.md"
        rule = Rule(name=name, source_path=path, metadata=metadata, content=content)
        path.write_text(serialize_rule(rule), encoding="utf-8")
        return rule

    def remove_rule(self, name: str) -> bool:
        path = self._rules_dir / f"{name}.md"
        if not path.exists():
            return False
        path.unlink()
        return True
