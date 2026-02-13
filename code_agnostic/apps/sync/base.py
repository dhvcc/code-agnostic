from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from code_agnostic.apps.sync.models import MCPServerDTO


class IAppMCPMapper(ABC):
    @abstractmethod
    def to_common(self, payload: dict[str, Any]) -> dict[str, MCPServerDTO]:
        raise NotImplementedError

    @abstractmethod
    def from_common(self, servers: dict[str, MCPServerDTO]) -> dict[str, Any]:
        raise NotImplementedError


class IAppConfigRepository(ABC):
    @property
    @abstractmethod
    def root(self) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_mcp_payload(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def save_mcp_payload(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError
