from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ISchemaRepository(ABC):
    @abstractmethod
    def load_schema(self) -> dict[str, Any]:
        raise NotImplementedError


class IAppConfigRepository(ABC):
    @property
    @abstractmethod
    def root(self) -> Path:
        raise NotImplementedError

    @property
    @abstractmethod
    def config_path(self) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_config(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_config(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_mcp_payload(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_mcp_payload(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    def serialize_config(self, payload: dict[str, Any]) -> str:
        import json

        return json.dumps(payload, indent=2) + "\n"


class IConfigRepository(ABC):
    @property
    @abstractmethod
    def root(self) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_state(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_state(self, data: dict[str, Any]) -> None:
        raise NotImplementedError


class ISourceRepository(IConfigRepository):
    @property
    @abstractmethod
    def skills_dir(self) -> Path:
        raise NotImplementedError

    @property
    @abstractmethod
    def agents_dir(self) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_mcp_base(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_skill_sources(self) -> list[Path]:
        raise NotImplementedError

    @abstractmethod
    def list_agent_sources(self) -> list[Path]:
        raise NotImplementedError

    @abstractmethod
    def load_workspaces(self) -> list[dict[str, str]]:
        raise NotImplementedError

    def workspace_config_dir(self, name: str) -> Path:
        return self.root / "workspaces" / name
