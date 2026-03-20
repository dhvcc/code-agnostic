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
from code_agnostic.apps.common.compiled_planning import plan_compiled_text_action
from code_agnostic.apps.codex.config_repository import CodexConfigRepository
from code_agnostic.apps.codex.mapper import CodexMCPMapper
from code_agnostic.apps.codex.schema_repository import CodexSchemaRepository
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import (
    IAppConfigRepository,
    ISchemaRepository,
    ISourceRepository,
)
from code_agnostic.apps.common.models import MCPServerDTO
from code_agnostic.apps.common.symlink_planning import (
    load_state_links,
    load_state_paths,
    plan_stale_files_group,
    plan_stale_group,
)
from code_agnostic.errors import (
    InvalidConfigSchemaError,
    InvalidJsonFormatError,
)
from code_agnostic.models import Action, ActionKind, ActionStatus, SyncPlan
from code_agnostic.utils import read_json_safe
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

    def build_action(self, common_servers: dict[str, MCPServerDTO]) -> Action:
        existing = self._codex_repo.load_config()
        if existing or self._codex_repo.config_path.exists():
            self.validate_config(existing)

        desired_mcp = self.mapper.from_common(common_servers)
        merged = dict(existing)
        base = self._load_base_config()
        for key, value in base.items():
            if key == "mcp_servers":
                continue
            merged[key] = deepcopy(value)
        self.set_mcp_payload(merged, desired_mcp)
        self.validate_config(merged)

        return Action(
            kind=self.action_kind,
            path=self.repository.config_path,
            status=self.derive_status(existing, merged),
            detail=f"sync {self.app_id.value} config from common mcp base",
            payload=self.build_action_payload(merged),
            app=self.app_id.value,
        )

    def build_plan(
        self,
        common_servers: dict[str, MCPServerDTO],
        source_repository: ISourceRepository,
    ) -> SyncPlan:
        config_action = self.build_action(common_servers)
        actions: list[Action] = [config_action]
        skipped: list[str] = []

        skill_sources = source_repository.list_skill_sources()

        state = source_repository.load_state()
        managed_links = state.get("managed_links", {})
        if not isinstance(managed_links, dict):
            managed_links = {}
        managed_paths = state.get("managed_paths", {})
        if not isinstance(managed_paths, dict):
            managed_paths = {}

        skill_link_actions = plan_stale_group(
            old_links=load_state_links(managed_links, "app:codex:skills"),
            desired_links=[],
            remove_detail="remove stale managed skill symlink",
            conflict_detail="stale managed path is not a symlink",
            noop_detail="stale symlink already absent",
            app=AppId.CODEX.value,
            scope="app:codex:skills",
            skipped=skipped,
            skipped_message="Stale link cleanup skipped (not symlink): {path}",
        )
        actions.extend(skill_link_actions)

        compiled_skill_actions, desired_skill_paths, compiled_skill_skipped = (
            self.plan_skill_actions(
                skill_sources,
                self._codex_repo.skills_dir,
                scope="app:codex:skills",
                app=AppId.CODEX.value,
                managed_paths=load_state_paths(managed_paths, "app:codex:skills"),
                removable_links=load_state_links(managed_links, "app:codex:skills"),
            )
        )
        actions.extend(compiled_skill_actions)
        skipped.extend(compiled_skill_skipped)

        agent_actions, desired_agent_paths, agent_skipped = self.plan_agent_actions(
            source_repository.list_agent_sources(),
            self._codex_repo.agents_dir,
            scope="app:codex:agents",
            app=AppId.CODEX.value,
            managed_paths=load_state_paths(managed_paths, "app:codex:agents"),
        )
        actions.extend(agent_actions)
        skipped.extend(agent_skipped)

        actions.extend(
            plan_stale_files_group(
                old_paths=load_state_paths(managed_paths, "app:codex:skills"),
                desired_paths=desired_skill_paths,
                remove_detail="remove stale managed skill file",
                conflict_detail="stale managed path is not a file",
                noop_detail="stale managed file already absent",
                app=AppId.CODEX.value,
                scope="app:codex:skills",
                skipped=skipped,
                skipped_message="Stale file cleanup skipped (not file): {path}",
            )
        )
        actions.extend(
            plan_stale_group(
                old_links=load_state_links(managed_links, "app:codex:agents"),
                desired_links=[],
                remove_detail="remove stale managed agent symlink",
                conflict_detail="stale managed path is not a symlink",
                noop_detail="stale symlink already absent",
                app=AppId.CODEX.value,
                scope="app:codex:agents",
                skipped=skipped,
                skipped_message="Stale link cleanup skipped (not symlink): {path}",
            )
        )
        actions.extend(
            plan_stale_files_group(
                old_paths=load_state_paths(managed_paths, "app:codex:agents"),
                desired_paths=desired_agent_paths,
                remove_detail="remove stale managed agent file",
                conflict_detail="stale managed path is not a file",
                noop_detail="stale managed file already absent",
                app=AppId.CODEX.value,
                scope="app:codex:agents",
                skipped=skipped,
                skipped_message="Stale file cleanup skipped (not file): {path}",
            )
        )

        return SyncPlan(actions=actions, errors=[], skipped=skipped)

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
        managed_path_set = {path.resolve(strict=False) for path in managed_paths}
        removable_link_set = {path.resolve(strict=False) for path in removable_links}
        actions: list[Action] = []
        desired_paths: list[Path] = []
        skipped: list[str] = []

        for source in sources:
            skill = parse_skill(
                source / "SKILL.md" if (source / "SKILL.md").exists() else source
            )
            target = target_dir / source.name / "SKILL.md"
            desired_paths.append(target)
            payload = compiler.compile(skill)
            action = plan_compiled_text_action(
                target=target,
                payload=payload,
                managed_paths=managed_path_set,
                removable_link_paths=removable_link_set,
                scope=scope,
                app=app,
                create_detail="create compiled codex skill",
                noop_detail="compiled codex skill already up to date",
                update_detail="update compiled codex skill",
            )
            actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                skipped.append(f"Codex skill sync skipped (conflict): {target}")

        return actions, desired_paths, skipped

    def plan_agent_actions(
        self,
        sources: list[Path],
        target_dir: Path,
        scope: str,
        app: str,
        managed_paths: list[Path],
    ) -> tuple[list[Action], list[Path], list[str]]:
        compiler = CodexAgentCompiler()
        managed_path_set = {path.resolve(strict=False) for path in managed_paths}
        actions: list[Action] = []
        desired_paths: list[Path] = []
        skipped: list[str] = []

        for source in sources:
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
            target = target_dir / target_name
            desired_paths.append(target)
            action = self._plan_compiled_agent_action(
                target=target,
                payload=payload,
                managed_paths=managed_path_set,
                scope=scope,
                app=app,
            )
            actions.append(action)
            if action.status == ActionStatus.CONFLICT:
                skipped.append(f"Codex agent sync skipped (conflict): {target}")

        return actions, desired_paths, skipped

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

    @staticmethod
    def _plan_compiled_agent_action(
        *,
        target: Path,
        payload: str,
        managed_paths: set[Path],
        scope: str,
        app: str,
    ) -> Action:
        return plan_compiled_text_action(
            target=target,
            payload=payload,
            managed_paths=managed_paths,
            scope=scope,
            app=app,
            create_detail="create compiled codex agent",
            noop_detail="compiled codex agent already up to date",
            update_detail="update compiled codex agent",
        )
