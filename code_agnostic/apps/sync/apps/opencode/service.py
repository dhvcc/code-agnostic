import json
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator

from code_agnostic.apps.sync.base import IAppConfigRepository, IAppMCPMapper
from code_agnostic.apps.sync.framework import RegisteredAppConfigService
from code_agnostic.apps.sync.apps.opencode.mapper import OpenCodeMCPMapper
from code_agnostic.apps.sync.apps.opencode.repository import OpenCodeRepository
from code_agnostic.errors import InvalidConfigSchemaError
from code_agnostic.models import ActionKind, ActionStatus, AppId

OPENCODE_SCHEMA_URL = "https://opencode.ai/config.json"
_FALLBACK_OPENCODE_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "$schema": {"type": "string"},
        "theme": {"type": "string"},
        "mcp": {"type": "object"},
    },
    "additionalProperties": True,
}


def _schema_error_message(error: Any) -> str:
    path = ".".join([str(part) for part in error.path])
    return f"{error.message} at {path}" if path else str(error.message)


@lru_cache(maxsize=1)
def _opencode_validator() -> Draft202012Validator:
    request = Request(OPENCODE_SCHEMA_URL, headers={"User-Agent": "code-agnostic"})
    try:
        with urlopen(request, timeout=20) as response:
            payload = response.read().decode("utf-8")
        schema = json.loads(payload)
    except Exception:
        schema = _FALLBACK_OPENCODE_SCHEMA
    return Draft202012Validator(schema)


def validate_opencode_config(payload: Any, config_path: Path) -> None:
    if not isinstance(payload, dict):
        raise InvalidConfigSchemaError(config_path, "must be a JSON object")
    error = next(iter(_opencode_validator().iter_errors(payload)), None)
    if error is not None:
        raise InvalidConfigSchemaError(config_path, _schema_error_message(error))


class OpenCodeConfigService(RegisteredAppConfigService):
    APP_ID = AppId.OPENCODE

    def __init__(self, repository: IAppConfigRepository, mapper: IAppMCPMapper) -> None:
        self._repository = repository
        self._mapper = mapper

    @classmethod
    def create_default(cls) -> "OpenCodeConfigService":
        return cls(repository=OpenCodeRepository(), mapper=OpenCodeMCPMapper())

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
            payload=payload, config_path=self.repository.config_path
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
