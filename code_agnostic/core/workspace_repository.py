from pathlib import Path

from code_agnostic.core.repository import BaseSourceRepository


class WorkspaceConfigRepository(BaseSourceRepository):
    """Source repository for workspace-level config."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)

    @property
    def mcp_base_path(self) -> Path:
        return self.root / "mcp.base.json"

    @property
    def rules_file(self) -> Path:
        return self.root / "AGENTS.md"

    @property
    def rules_dir(self) -> Path:
        return self.root / "rules"

    def has_mcp(self) -> bool:
        return self.mcp_base_path.exists() or self.mcp_base_yaml_path.exists()

    @property
    def codex_base_path(self) -> Path:
        return self.root / "codex.base.json"

    def has_rules(self) -> bool:
        if self.rules_dir.exists():
            return any(
                (
                    f.suffix == ".md"
                    or (
                        f.is_dir()
                        and (f / "meta.yaml").exists()
                        and (f / "prompt.md").exists()
                    )
                )
                and not f.name.startswith(".")
                for f in self.rules_dir.iterdir()
            )
        return self.rules_file.exists()

    def has_skills(self) -> bool:
        return self.skills_dir.exists() and bool(self.list_skill_sources())

    def has_agents(self) -> bool:
        return self.agents_dir.exists() and bool(self.list_agent_sources())

    def has_any_config(self) -> bool:
        return (
            self.has_mcp()
            or self.has_rules()
            or self.has_skills()
            or self.has_agents()
            or self.codex_base_path.exists()
        )
