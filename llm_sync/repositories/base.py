from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional, Tuple


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

    @property
    @abstractmethod
    def state_md(self) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_mcp_base(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def load_opencode_base(self) -> dict[str, Any]:
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


class ITargetRepository(ABC):
    @property
    @abstractmethod
    def root(self) -> Path:
        raise NotImplementedError

    @property
    @abstractmethod
    def config_path(self) -> Path:
        raise NotImplementedError

    @property
    @abstractmethod
    def skills_dir(self) -> Path:
        raise NotImplementedError

    @property
    @abstractmethod
    def agents_dir(self) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_config_object(self) -> Tuple[dict[str, Any], Optional[Exception]]:
        raise NotImplementedError

    @abstractmethod
    def merge_config(self, existing: dict[str, Any], base: dict[str, Any], mapped_mcp: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError
