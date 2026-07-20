from pathlib import Path
from typing import Any

from code_agnostic.agents.compilers import CopilotAgentCompiler
from code_agnostic.agents.copilot import copilot_agent_filename
from code_agnostic.agents.parser import parse_agent
from code_agnostic.apps.app_id import AppId, app_label
from code_agnostic.apps.common.framework import RegisteredAppConfigService
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import IAppConfigRepository
from code_agnostic.apps.copilot.config_repository import CopilotConfigRepository
from code_agnostic.apps.copilot.mapper import CopilotMCPMapper
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import Action, ActionKind, ActionStatus
from code_agnostic.skills.compilers import CopilotSkillCompiler
from code_agnostic.skills.parser import parse_skill


class CopilotConfigService(RegisteredAppConfigService):
    APP_ID = AppId.COPILOT
    APP_LABEL = app_label(APP_ID)

    def __init__(
        self,
        repository: CopilotConfigRepository,
        mapper: IAppMCPMapper,
    ) -> None:
        self._repository = repository
        self._mapper = mapper

    @classmethod
    def create_default(cls, root: Path | None = None) -> "CopilotConfigService":
        return cls(
            repository=CopilotConfigRepository(root=root),
            mapper=CopilotMCPMapper(),
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
        mcp_servers = payload.get("mcpServers")
        if mcp_servers is not None and not isinstance(mcp_servers, dict):
            raise InvalidConfigSchemaError(
                self.repository.config_path, "mcpServers must be a JSON object"
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

    def plan_skill_actions(
        self,
        sources: list[Path],
        target_dir: Path,
        scope: str,
        app: str,
        managed_paths: list[Path],
        removable_links: list[Path],
    ) -> tuple[list[Action], list[Path], list[str]]:
        compiler = CopilotSkillCompiler()
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
            create_detail="create compiled copilot skill",
            noop_detail="compiled copilot skill already up to date",
            update_detail="update compiled copilot skill",
            conflict_message="Copilot skill sync skipped (conflict): {target}",
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
        compiler = CopilotAgentCompiler()
        return self._plan_compiled_text_actions(
            sources=sources,
            target_dir=target_dir,
            scope=scope,
            app=app,
            managed_paths=managed_paths,
            removable_links=removable_links,
            compile_source=lambda source: (
                target_dir / copilot_agent_filename(source),
                compiler.compile(parse_agent(source)),
            ),
            create_detail="create compiled copilot agent",
            noop_detail="compiled copilot agent already up to date",
            update_detail="update compiled copilot agent",
            conflict_message="Copilot agent sync skipped (conflict): {target}",
        )
