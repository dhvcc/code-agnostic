from abc import ABC, abstractmethod
from typing import Any

from code_agnostic.apps.common.models import MCPServerDTO


class IAppMCPMapper(ABC):
    @abstractmethod
    def to_common(self, payload: dict[str, Any]) -> dict[str, MCPServerDTO]:
        raise NotImplementedError

    @abstractmethod
    def from_common(self, servers: dict[str, MCPServerDTO]) -> dict[str, Any]:
        raise NotImplementedError
