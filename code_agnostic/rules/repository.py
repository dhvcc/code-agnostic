"""Repository for rule CRUD operations."""

from __future__ import annotations

import shutil
from pathlib import Path

from code_agnostic.rules.models import Rule, RuleMetadata
from code_agnostic.rules.parser import parse_rule, serialize_rule
from code_agnostic.spec.loaders import load_rule_bundle


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
            if child.name.startswith("."):
                continue
            if child.suffix == ".md":
                rules.append(parse_rule(child))
                continue
            if _is_rule_bundle_dir(child):
                rules.append(load_rule_bundle(child))
        return rules

    def get_rule(self, name: str) -> Rule | None:
        bundle_path = self._rules_dir / name
        if _is_rule_bundle_dir(bundle_path):
            return load_rule_bundle(bundle_path)
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
        bundle_path = self._rules_dir / name
        if _is_rule_bundle_dir(bundle_path):
            shutil.rmtree(bundle_path)
            return True
        path = self._rules_dir / f"{name}.md"
        if not path.exists():
            return False
        path.unlink()
        return True


def _is_rule_bundle_dir(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "meta.yaml").exists()
        and (path / "prompt.md").exists()
    )
