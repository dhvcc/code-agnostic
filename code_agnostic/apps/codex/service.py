from typing import Any

from jsonschema import Draft7Validator

from code_agnostic.apps.app_id import AppId
from code_agnostic.apps.common.framework import (
    RegisteredAppConfigService,
    format_schema_error,
)
from code_agnostic.apps.codex.config_repository import CodexConfigRepository
from code_agnostic.apps.codex.mapper import CodexMCPMapper
from code_agnostic.apps.codex.schema_repository import CodexSchemaRepository
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import IAppConfigRepository
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import ActionKind, ActionStatus


class CodexConfigService(RegisteredAppConfigService):
    APP_ID = AppId.CODEX

    def __init__(
        self,
        repository: CodexConfigRepository,
        mapper: IAppMCPMapper,
        schema_repository: CodexSchemaRepository,
    ) -> None:
        self._repository = repository
        self._mapper = mapper
        self._schema_repository = schema_repository
        self._validator = Draft7Validator(self._schema_repository.load_schema())

    @classmethod
    def create_default(cls) -> "CodexConfigService":
        return cls(
            repository=CodexConfigRepository(),
            mapper=CodexMCPMapper(),
            schema_repository=CodexSchemaRepository(),
        )

    @property
    def app_id(self) -> AppId:
        return AppId.CODEX

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
        if not isinstance(self.repository, CodexConfigRepository):
            raise InvalidConfigSchemaError(
                self.repository.config_path, "invalid codex repository"
            )
        return self.repository.serialize_config(payload)

    def set_mcp_payload(
        self, merged: dict[str, Any], desired_mcp: dict[str, Any]
    ) -> None:
        merged["mcp_servers"] = desired_mcp

    def derive_status(
        self, existing: dict[str, Any], merged: dict[str, Any]
    ) -> ActionStatus:
        if not isinstance(self.repository, CodexConfigRepository):
            return ActionStatus.UPDATE
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
