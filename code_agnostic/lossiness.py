from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from code_agnostic.agents.parser import parse_agent
from code_agnostic.rules.parser import parse_rule
from code_agnostic.spec.loaders import load_rule_bundle


@dataclass(frozen=True)
class LossinessFinding:
    resource_path: str
    app: str
    property: str
    status: str
    reason: str


class LossinessExplainer:
    def explain_core_root(self, root: Path, app: str = "all") -> list[LossinessFinding]:
        return self._explain_root(root=root, app=app, prefix=None)

    def explain_workspace_root(
        self, root: Path, workspace: str, app: str = "all"
    ) -> list[LossinessFinding]:
        return self._explain_root(
            root=root,
            app=app,
            prefix=Path("workspaces") / workspace,
        )

    def _explain_root(
        self, root: Path, app: str, prefix: Path | None
    ) -> list[LossinessFinding]:
        findings: list[LossinessFinding] = []
        findings.extend(self._explain_rules(root / "rules", app=app, prefix=prefix))
        findings.extend(self._explain_agents(root / "agents", app=app, prefix=prefix))
        return sorted(
            findings,
            key=lambda item: (
                item.resource_path,
                item.app,
                item.property,
                item.status,
                item.reason,
            ),
        )

    def _explain_rules(
        self, rules_dir: Path, app: str, prefix: Path | None
    ) -> list[LossinessFinding]:
        if not rules_dir.exists():
            return []

        findings: list[LossinessFinding] = []
        for child in sorted(rules_dir.iterdir()):
            if child.name.startswith("."):
                continue

            if child.is_file() and child.suffix == ".md":
                rule = parse_rule(child)
            elif child.is_dir() and (
                (child / "meta.yaml").exists() or (child / "prompt.md").exists()
            ):
                rule = load_rule_bundle(child)
            else:
                continue

            resource_path = self._resource_path(
                root=rules_dir.parent, child=child, prefix=prefix
            )
            if rule.metadata.always_apply:
                findings.extend(
                    self._findings_for_targets(
                        resource_path=resource_path,
                        property_name="always_apply",
                        targets=("codex", "opencode"),
                        app=app,
                        reason="target does not support rule always_apply semantics",
                    )
                )
            if rule.metadata.globs:
                findings.extend(
                    self._findings_for_targets(
                        resource_path=resource_path,
                        property_name="globs",
                        targets=("codex", "opencode"),
                        app=app,
                        reason="target does not support rule globs",
                    )
                )

        return findings

    def _explain_agents(
        self, agents_dir: Path, app: str, prefix: Path | None
    ) -> list[LossinessFinding]:
        if not agents_dir.exists():
            return []

        findings: list[LossinessFinding] = []
        for child in sorted(agents_dir.iterdir()):
            if child.name.startswith("."):
                continue
            if not child.is_file() and not child.is_dir():
                continue

            agent = parse_agent(child)
            resource_path = self._resource_path(
                root=agents_dir.parent,
                child=child,
                prefix=prefix,
            )

            if agent.metadata.codex.mcp_servers:
                findings.extend(
                    self._findings_for_targets(
                        resource_path=resource_path,
                        property_name="codex.mcp_servers",
                        targets=("cursor", "opencode"),
                        app=app,
                        reason="target only supports codex.mcp_servers in Codex output",
                    )
                )
            if agent.metadata.codex.skills_config:
                findings.extend(
                    self._findings_for_targets(
                        resource_path=resource_path,
                        property_name="codex.skills.config",
                        targets=("cursor", "opencode"),
                        app=app,
                        reason="target only supports codex.skills.config in Codex output",
                    )
                )
            if agent.metadata.nickname_candidates:
                findings.extend(
                    self._findings_for_targets(
                        resource_path=resource_path,
                        property_name="nickname_candidates",
                        targets=("cursor", "opencode"),
                        app=app,
                        reason="target does not support agent nickname_candidates",
                    )
                )
            if agent.metadata.sandbox_mode:
                findings.extend(
                    self._findings_for_targets(
                        resource_path=resource_path,
                        property_name="sandbox_mode",
                        targets=("cursor", "opencode"),
                        app=app,
                        reason="target does not support agent sandbox_mode",
                    )
                )

        return findings

    def _findings_for_targets(
        self,
        *,
        resource_path: str,
        property_name: str,
        targets: tuple[str, ...],
        app: str,
        reason: str,
    ) -> list[LossinessFinding]:
        normalized_app = app.lower()
        selected_targets = [
            target
            for target in targets
            if normalized_app == "all" or target == normalized_app
        ]
        return [
            LossinessFinding(
                resource_path=resource_path,
                app=target,
                property=property_name,
                status="ignored",
                reason=reason,
            )
            for target in selected_targets
        ]

    def _resource_path(self, root: Path, child: Path, prefix: Path | None) -> str:
        relative = child.relative_to(root)
        if prefix is None:
            return relative.as_posix()
        return (prefix / relative).as_posix()
