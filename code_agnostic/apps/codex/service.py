from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

from code_agnostic.agents.codex import normalize_codex_agent_filename
from code_agnostic.agents.compilers import CodexAgentCompiler
from code_agnostic.agents.parser import parse_agent
from code_agnostic.apps.app_id import AppId, app_label
from code_agnostic.apps.common.framework import (
    RegisteredAppConfigService,
    format_schema_error,
)
from code_agnostic.apps.codex.config_repository import CodexConfigRepository
from code_agnostic.apps.codex.mapper import CodexMCPMapper
from code_agnostic.apps.codex.schema_repository import CodexSchemaRepository
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import (
    IAppConfigRepository,
    ISchemaRepository,
)
from code_agnostic.apps.common.models import MCPServerDTO
from code_agnostic.errors import (
    InvalidConfigSchemaError,
    InvalidJsonFormatError,
)
from code_agnostic.models import Action, ActionKind, ActionStatus
from code_agnostic.utils import merge_dict_overlay, read_json_safe
from code_agnostic.skills.compilers import CodexSkillCompiler
from code_agnostic.skills.parser import parse_skill


class CodexConfigService(RegisteredAppConfigService):
    APP_ID = AppId.CODEX
    APP_LABEL = app_label(APP_ID)

    def __init__(
        self,
        repository: CodexConfigRepository,
        mapper: IAppMCPMapper,
        schema_repository: ISchemaRepository,
        base_config_path: Path | None = None,
    ) -> None:
        self._repository = repository
        self._codex_repo = repository
        self._mapper = mapper
        self._schema_repository = schema_repository
        self._base_config_path = base_config_path
        self._validator = Draft7Validator(self._schema_repository.load_schema())

    @classmethod
    def create_default(cls, root: Path | None = None) -> "CodexConfigService":
        if root is not None:
            return cls(
                repository=CodexConfigRepository(root=root),
                mapper=CodexMCPMapper(),
                schema_repository=CodexSchemaRepository(),
                base_config_path=None,
            )
        from code_agnostic.core.repository import CoreRepository

        core = CoreRepository()
        return cls(
            repository=CodexConfigRepository(root=root),
            mapper=CodexMCPMapper(),
            schema_repository=CodexSchemaRepository(),
            base_config_path=core.codex_base_path,
        )

    @property
    def app_id(self) -> AppId:
        return self.APP_ID

    @property
    def action_kind(self) -> ActionKind:
        return ActionKind.WRITE_TEXT

    @property
    def repository(self) -> IAppConfigRepository:
        return self._repository

    @property
    def mapper(self) -> IAppMCPMapper:
        return self._mapper

    def validate_config(self, payload: Any) -> None:
        error = next(iter(self._validator.iter_errors(payload)), None)
        if error is not None:
            raise InvalidConfigSchemaError(
                self.repository.config_path, format_schema_error(error)
            )

    def build_action_payload(self, payload: dict[str, Any]) -> Any:
        return self.repository.serialize_config(payload)

    def set_mcp_payload(
        self, merged: dict[str, Any], desired_mcp: dict[str, Any]
    ) -> None:
        merged["mcp_servers"] = desired_mcp

    def derive_status(
        self, existing: dict[str, Any], merged: dict[str, Any]
    ) -> ActionStatus:
        rendered = self.repository.serialize_config(merged)
        existing_text = (
            self.repository.config_path.read_text(encoding="utf-8")
            if self.repository.config_path.exists()
            else ""
        )
        if not self.repository.config_path.exists():
            return ActionStatus.CREATE
        if existing_text == rendered:
            return ActionStatus.NOOP
        return ActionStatus.UPDATE

    def build_action(
        self,
        common_servers: dict[str, MCPServerDTO],
        agent_sources: list[Path] | None = None,
    ) -> Action:
        existing = self._codex_repo.load_config()
        if existing or self._codex_repo.config_path.exists():
            self.validate_config(existing)

        desired_mcp = self.mapper.from_common(common_servers)
        merged = dict(existing)
        base = self._load_base_config()
        for key, value in base.items():
            if key == "mcp_servers":
                continue
            if key == "agents" and isinstance(value, dict):
                merged["agents"] = self._merge_agents_payload(
                    merged.get("agents"), value
                )
                continue
            current = merged.get(key)
            if isinstance(current, dict) and isinstance(value, dict):
                merged[key] = merge_dict_overlay(current, value)
                continue
            merged[key] = deepcopy(value)
        self.set_mcp_payload(merged, desired_mcp)
        if agent_sources:
            merged["agents"] = self._merge_agents_payload(
                merged.get("agents"),
                self._build_agent_registry(agent_sources),
            )
        self.validate_config(merged)

        return Action(
            kind=self.action_kind,
            path=self.repository.config_path,
            status=self.derive_status(existing, merged),
            detail=f"sync {self.app_id.value} config from common mcp base",
            payload=self.build_action_payload(merged),
            app=self.app_id.value,
        )

    def _merge_agents_payload(
        self, existing: Any, overlay: dict[str, Any]
    ) -> dict[str, Any]:
        merged = dict(existing) if isinstance(existing, dict) else {}
        for key, value in overlay.items():
            merged[key] = deepcopy(value)
        return merged

    def _build_agent_registry(self, sources: list[Path]) -> dict[str, dict[str, Any]]:
        registry: dict[str, dict[str, Any]] = {}
        for source in sources:
            try:
                agent = parse_agent(source)
            except InvalidConfigSchemaError:
                raise
            except Exception as exc:
                raise InvalidConfigSchemaError(source, str(exc)) from exc

            agent_name = agent.metadata.name or agent.name
            target_name = (
                normalize_codex_agent_filename(agent.metadata.name, agent.name)
                + ".toml"
            )
            entry: dict[str, Any] = {
                "description": agent.metadata.description or agent_name,
                "config_file": (Path("agents") / target_name).as_posix(),
            }
            if agent.metadata.nickname_candidates:
                entry["nickname_candidates"] = list(agent.metadata.nickname_candidates)
            registry[agent_name] = entry
        return registry

    def plan_skill_actions(
        self,
        sources: list[Path],
        target_dir: Path,
        scope: str,
        app: str,
        managed_paths: list[Path],
        removable_links: list[Path],
    ) -> tuple[list[Action], list[Path], list[str]]:
        compiler = CodexSkillCompiler()
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
            create_detail="create compiled codex skill",
            noop_detail="compiled codex skill already up to date",
            update_detail="update compiled codex skill",
            conflict_message="Codex skill sync skipped (conflict): {target}",
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
        compiler = CodexAgentCompiler()

        def compile_source(source: Path) -> tuple[Path, str]:
            try:
                agent = parse_agent(source)
                payload = compiler.compile(agent)
            except InvalidConfigSchemaError:
                raise
            except Exception as exc:
                raise InvalidConfigSchemaError(source, str(exc)) from exc

            target_name = (
                normalize_codex_agent_filename(agent.metadata.name, agent.name)
                + ".toml"
            )
            return target_dir / target_name, payload

        return self._plan_compiled_text_actions(
            sources=sources,
            target_dir=target_dir,
            scope=scope,
            app=app,
            managed_paths=managed_paths,
            removable_links=removable_links,
            compile_source=compile_source,
            create_detail="create compiled codex agent",
            noop_detail="compiled codex agent already up to date",
            update_detail="update compiled codex agent",
            conflict_message="Codex agent sync skipped (conflict): {target}",
        )

    def _load_base_config(self) -> dict[str, Any]:
        if self._base_config_path is None or not self._base_config_path.exists():
            return {}
        payload, error = read_json_safe(self._base_config_path)
        if error is not None:
            raise InvalidJsonFormatError(self._base_config_path, error)
        if not isinstance(payload, dict):
            raise InvalidConfigSchemaError(
                self._base_config_path, "must be a JSON object"
            )
        return payload
