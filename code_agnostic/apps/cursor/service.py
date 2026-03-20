from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from code_agnostic.apps.app_id import AppId, app_label
from code_agnostic.apps.common.framework import (
    RegisteredAppConfigService,
    format_schema_error,
)
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import (
    IAppConfigRepository,
    ISchemaRepository,
)
from code_agnostic.agents.compilers import CursorAgentCompiler
from code_agnostic.agents.parser import parse_agent
from code_agnostic.apps.cursor.config_repository import CursorConfigRepository
from code_agnostic.apps.cursor.mapper import CursorMCPMapper
from code_agnostic.apps.cursor.schema_repository import CursorSchemaRepository
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import Action, ActionKind, ActionStatus
from code_agnostic.skills.compilers import CursorSkillCompiler
from code_agnostic.skills.parser import parse_skill


class CursorConfigService(RegisteredAppConfigService):
    APP_ID = AppId.CURSOR
    APP_LABEL = app_label(APP_ID)

    def __init__(
        self,
        repository: CursorConfigRepository,
        mapper: IAppMCPMapper,
        schema_repository: ISchemaRepository,
    ) -> None:
        self._repository = repository
        self._cursor_repo = repository
        self._mapper = mapper
        self._schema_repository = schema_repository
        self._validator = Draft202012Validator(self._schema_repository.load_schema())

    @classmethod
    def create_default(cls, root: Path | None = None) -> "CursorConfigService":
        return cls(
            repository=CursorConfigRepository(root=root),
            mapper=CursorMCPMapper(),
            schema_repository=CursorSchemaRepository(),
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

    def validate_config(self, payload: Any) -> None:
        if payload == {}:
            return
        error = next(iter(self._validator.iter_errors(payload)), None)
        if error is not None:
            raise InvalidConfigSchemaError(
                self.repository.config_path, format_schema_error(error)
            )

    def build_action_payload(self, payload: dict[str, Any]) -> Any:
        return payload

    def set_mcp_payload(
        self, merged: dict[str, Any], desired_mcp: dict[str, Any]
    ) -> None:
        merged["mcpServers"] = desired_mcp

    def derive_status(
        self, existing: dict[str, Any], merged: dict[str, Any]
    ) -> ActionStatus:
        existing_mcp = (
            existing.get("mcpServers")
            if isinstance(existing.get("mcpServers"), dict)
            else {}
        )
        desired_mcp = (
            merged.get("mcpServers")
            if isinstance(merged.get("mcpServers"), dict)
            else {}
        )
        if not self.repository.config_path.exists():
            return ActionStatus.CREATE
        if existing_mcp == desired_mcp:
            return ActionStatus.NOOP
        return ActionStatus.UPDATE

    def agent_action_removable_links(self, removable_links: list[Path]) -> list[Path]:
        return removable_links

    def plan_skill_actions(
        self,
        sources: list[Path],
        target_dir: Path,
        scope: str,
        app: str,
        managed_paths: list[Path],
        removable_links: list[Path],
    ) -> tuple[list[Action], list[Path], list[str]]:
        compiler = CursorSkillCompiler()
        return self._plan_compiled_text_actions(
            sources=sources,
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
            create_detail="create compiled cursor skill",
            noop_detail="compiled cursor skill already up to date",
            update_detail="update compiled cursor skill",
            conflict_message="Cursor skill sync skipped (conflict): {target}",
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
        compiler = CursorAgentCompiler()
        return self._plan_compiled_text_actions(
            sources=sources,
            scope=scope,
            app=app,
            managed_paths=managed_paths,
            removable_links=removable_links,
            compile_source=lambda source: (
                target_dir / (source.name if source.is_file() else f"{source.name}.md"),
                compiler.compile(parse_agent(source)),
            ),
            create_detail="create compiled cursor agent",
            noop_detail="compiled cursor agent already up to date",
            update_detail="update compiled cursor agent",
            conflict_message="Cursor agent sync skipped (conflict): {target}",
        )
