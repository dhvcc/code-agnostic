from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from code_agnostic.agents.parser import parse_agent
from code_agnostic.core.repository import CoreRepository
from code_agnostic.core.workspace_repository import WorkspaceConfigRepository
from code_agnostic.rules.parser import parse_rule
from code_agnostic.spec.loaders import load_rule_bundle
from code_agnostic.skills.parser import parse_skill


@dataclass(frozen=True)
class ValidationIssue:
    path: Path
    message: str


@dataclass(frozen=True)
class ValidationResult:
    validated: int
    issues: list[ValidationIssue]


class ConfigValidator:
    def validate_core_root(self, root: Path) -> ValidationResult:
        return self._validate_repository(CoreRepository(root))

    def validate_workspace_root(self, root: Path) -> ValidationResult:
        return self._validate_repository(WorkspaceConfigRepository(root))

    def _validate_repository(
        self, repository: CoreRepository | WorkspaceConfigRepository
    ) -> ValidationResult:
        validated = 0
        issues: list[ValidationIssue] = []

        if repository.mcp_base_path.exists() or repository.mcp_base_yaml_path.exists():
            try:
                repository.load_mcp_base()
                validated += 1
            except Exception as exc:
                issues.append(ValidationIssue(repository.mcp_base_path, str(exc)))

        validated, issues = self._validate_rules(
            repository.root / "rules", validated, issues
        )
        validated, issues = self._validate_skills(
            repository.root / "skills", validated, issues
        )
        validated, issues = self._validate_agents(
            repository.root / "agents", validated, issues
        )

        return ValidationResult(validated=validated, issues=issues)

    def _validate_rules(
        self, rules_dir: Path, validated: int, issues: list[ValidationIssue]
    ) -> tuple[int, list[ValidationIssue]]:
        if not rules_dir.exists():
            return validated, issues

        for child in sorted(rules_dir.iterdir()):
            if child.name.startswith("."):
                continue
            try:
                if child.is_file() and child.suffix == ".md":
                    parse_rule(child)
                    validated += 1
                    continue
                if child.is_dir() and (
                    (child / "meta.yaml").exists() or (child / "prompt.md").exists()
                ):
                    load_rule_bundle(child)
                    validated += 1
            except Exception as exc:
                issues.append(ValidationIssue(child, str(exc)))
        return validated, issues

    def _validate_skills(
        self, skills_dir: Path, validated: int, issues: list[ValidationIssue]
    ) -> tuple[int, list[ValidationIssue]]:
        if not skills_dir.exists():
            return validated, issues

        for child in sorted(skills_dir.iterdir()):
            if child.name.startswith(".") or not child.is_dir():
                continue
            try:
                if (child / "SKILL.md").exists():
                    parse_skill(child / "SKILL.md")
                    validated += 1
                    continue
                if (child / "meta.yaml").exists() or (child / "prompt.md").exists():
                    parse_skill(child)
                    validated += 1
            except Exception as exc:
                issues.append(ValidationIssue(child, str(exc)))
        return validated, issues

    def _validate_agents(
        self, agents_dir: Path, validated: int, issues: list[ValidationIssue]
    ) -> tuple[int, list[ValidationIssue]]:
        if not agents_dir.exists():
            return validated, issues

        for child in sorted(agents_dir.iterdir()):
            if child.name.startswith("."):
                continue
            try:
                if child.is_file():
                    parse_agent(child)
                    validated += 1
                    continue
                if child.is_dir() and (
                    (child / "meta.yaml").exists() or (child / "prompt.md").exists()
                ):
                    parse_agent(child)
                    validated += 1
            except Exception as exc:
                issues.append(ValidationIssue(child, str(exc)))
        return validated, issues
