from copy import deepcopy
from pathlib import Path
from typing import Any

from code_agnostic.agents.claude import claude_agent_target_path
from code_agnostic.agents.compilers import ClaudeAgentCompiler
from code_agnostic.agents.parser import parse_agent
from code_agnostic.apps.app_id import AppId, app_label
from code_agnostic.apps.claude.config_repository import ClaudeConfigRepository
from code_agnostic.apps.claude.mapper import ClaudeMCPMapper
from code_agnostic.apps.common.framework import RegisteredAppConfigService
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import IAppConfigRepository
from code_agnostic.apps.common.models import MCPServerDTO
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import Action, ActionKind, ActionStatus
from code_agnostic.skills.compilers import ClaudeSkillCompiler
from code_agnostic.skills.parser import parse_skill


class ClaudeConfigService(RegisteredAppConfigService):
    APP_ID = AppId.CLAUDE
    APP_LABEL = app_label(APP_ID)

    def __init__(
        self,
        repository: ClaudeConfigRepository,
        mapper: IAppMCPMapper,
    ) -> None:
        self._repository = repository
        self._mapper = mapper

    @classmethod
    def create_default(cls, root: Path | None = None) -> "ClaudeConfigService":
        return cls(
            repository=ClaudeConfigRepository(root=root),
            mapper=ClaudeMCPMapper(),
        )

    @property
    def app_id(self) -> AppId:
        return self.APP_ID

    @property
    def action_kind(self) -> ActionKind:
        return ActionKind.WRITE_JSON

    @property
    def repository(self) -> IAppConfigRepository:
        return self._repository

    @property
    def mapper(self) -> IAppMCPMapper:
        return self._mapper

    @property
    def mcp_config_key(self) -> str:
        return "mcpServers"

    def validate_config(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            raise InvalidConfigSchemaError(
                self.repository.config_path, "must be a JSON object"
            )

    def build_action_payload(self, payload: dict[str, Any]) -> Any:
        return payload

    def derive_status(
        self, existing: dict[str, Any], merged: dict[str, Any]
    ) -> ActionStatus:
        if not self.repository.config_path.exists():
            return ActionStatus.CREATE
        if existing == merged:
            return ActionStatus.NOOP
        return ActionStatus.UPDATE

    def build_project_mcp_action(
        self,
        project_servers: dict[Path, dict[str, MCPServerDTO]],
        base_payload: dict[str, Any] | None = None,
    ) -> Action:
        existing = self._repository.load_config()
        if existing or self.repository.config_path.exists():
            self.validate_config(existing)

        merged = (
            deepcopy(base_payload) if base_payload is not None else deepcopy(existing)
        )
        projects = merged.get("projects")
        if not isinstance(projects, dict):
            projects = {}
        else:
            projects = deepcopy(projects)

        for project_path, servers in project_servers.items():
            key = str(project_path.resolve())
            project = projects.get(key)
            if not isinstance(project, dict):
                project = {}
            else:
                project = deepcopy(project)
            project["mcpServers"] = self.mapper.from_common(servers)
            projects[key] = project

        merged["projects"] = projects
        self.validate_config(merged)

        return Action(
            kind=self.action_kind,
            path=self.repository.config_path,
            status=self.derive_status(existing, merged),
            detail="sync claude project mcp config from workspace mcp base",
            payload=merged,
            app=self.app_id.value,
        )

    def plan_skill_actions(
        self,
        sources: list[Path],
        target_dir: Path,
        scope: str,
        app: str,
        managed_paths: list[Path],
        removable_links: list[Path],
    ) -> tuple[list[Action], list[Path], list[str]]:
        compiler = ClaudeSkillCompiler()
        return self._plan_compiled_text_actions(
            sources=sources,
            target_dir=target_dir,
            scope=scope,
            app=app,
            managed_paths=managed_paths,
            removable_links=removable_links,
            compile_source=lambda source: (
                target_dir / source.name / "SKILL.md",
                compiler.compile(
                    parse_skill(
                        source / "SKILL.md"
                        if (source / "SKILL.md").exists()
                        else source
                    )
                ),
            ),
            create_detail="create compiled claude skill",
            noop_detail="compiled claude skill already up to date",
            update_detail="update compiled claude skill",
            conflict_message="Claude skill sync skipped (conflict): {target}",
        )

    def plan_agent_actions(
        self,
        sources: list[Path],
        target_dir: Path,
        scope: str,
        app: str,
        managed_paths: list[Path],
        removable_links: list[Path],
    ) -> tuple[list[Action], list[Path], list[str]]:
        compiler = ClaudeAgentCompiler()

        def compile_source(source: Path) -> tuple[Path, str]:
            agent = parse_agent(source)
            return claude_agent_target_path(target_dir, agent), compiler.compile(agent)

        return self._plan_compiled_text_actions(
            sources=sources,
            target_dir=target_dir,
            scope=scope,
            app=app,
            managed_paths=managed_paths,
            removable_links=removable_links,
            compile_source=compile_source,
            create_detail="create compiled claude agent",
            noop_detail="compiled claude agent already up to date",
            update_detail="update compiled claude agent",
            conflict_message="Claude agent sync skipped (conflict): {target}",
        )
