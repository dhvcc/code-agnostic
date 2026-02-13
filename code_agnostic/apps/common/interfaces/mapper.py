from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from code_agnostic.apps.common.models import MCPServerDTO


class IAppMCPMapper(ABC):
    @abstractmethod
    def to_common(self, payload: dict[str, Any]) -> dict[str, MCPServerDTO]:
        raise NotImplementedError

    @abstractmethod
    def from_common(self, servers: dict[str, MCPServerDTO]) -> dict[str, Any]:
        raise NotImplementedError


class IConfigMapper(ABC):
    def map_mcp_servers(self, mcp_servers: dict[str, Any]) -> dict[str, Any]:
        return dict(mcp_servers)

    def map_skill_source(self, source: Path) -> Path:
        return source

    def map_agent_source(self, source: Path) -> Path:
        return source

    def map_workspace_rules_source(self, source: Path) -> Path:
        return source
