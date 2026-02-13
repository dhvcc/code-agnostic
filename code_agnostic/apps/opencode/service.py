from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from code_agnostic.apps.common.framework import RegisteredAppConfigService
from code_agnostic.apps.common.interfaces.mapper import IAppMCPMapper
from code_agnostic.apps.common.interfaces.repositories import IAppConfigRepository
from code_agnostic.apps.opencode.config_repository import OpenCodeConfigRepository
from code_agnostic.apps.opencode.mapper import OpenCodeMCPMapper
from code_agnostic.apps.opencode.schema_repository import OpenCodeSchemaRepository
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import ActionKind, ActionStatus, AppId


def _schema_error_message(error: Any) -> str:
    path = ".".join([str(part) for part in error.path])
    return f"{error.message} at {path}" if path else str(error.message)


def validate_opencode_config(
    payload: Any, config_path: Path, validator: Draft202012Validator
) -> None:
    if not isinstance(payload, dict):
        raise InvalidConfigSchemaError(config_path, "must be a JSON object")
    error = next(iter(validator.iter_errors(payload)), None)
    if error is not None:
        raise InvalidConfigSchemaError(config_path, _schema_error_message(error))


class OpenCodeConfigService(RegisteredAppConfigService):
    APP_ID = AppId.OPENCODE

    def __init__(
        self,
        repository: OpenCodeConfigRepository,
        mapper: IAppMCPMapper,
        schema_repository: OpenCodeSchemaRepository,
    ) -> None:
        self._repository = repository
        self._mapper = mapper
        self._schema_repository = schema_repository
        self._validator = Draft202012Validator(self._schema_repository.load_schema())

    @classmethod
    def create_default(cls) -> "OpenCodeConfigService":
        return cls(
            repository=OpenCodeConfigRepository(),
            mapper=OpenCodeMCPMapper(),
            schema_repository=OpenCodeSchemaRepository(),
        )

    @property
    def app_id(self) -> AppId:
        return AppId.OPENCODE

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
        validate_opencode_config(
            payload=payload,
            config_path=self.repository.config_path,
            validator=self._validator,
        )

    def build_action_payload(self, payload: dict[str, Any]) -> Any:
        return payload

    def set_mcp_payload(
        self, merged: dict[str, Any], desired_mcp: dict[str, Any]
    ) -> None:
        merged["mcp"] = desired_mcp

    def derive_status(
        self, existing: dict[str, Any], merged: dict[str, Any]
    ) -> ActionStatus:
        existing_mcp = (
            existing.get("mcp") if isinstance(existing.get("mcp"), dict) else {}
        )
        desired_mcp = merged.get("mcp") if isinstance(merged.get("mcp"), dict) else {}
        if not self.repository.config_path.exists():
            return ActionStatus.CREATE
        if existing_mcp == desired_mcp:
            return ActionStatus.NOOP
        return ActionStatus.UPDATE
