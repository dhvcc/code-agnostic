from abc import ABC
from pathlib import Path
from typing import Any


class IConfigMapper(ABC):
    def map_mcp_servers(self, mcp_servers: dict[str, Any]) -> dict[str, Any]:
        return dict(mcp_servers)

    def map_skill_source(self, source: Path) -> Path:
        return source

    def map_agent_source(self, source: Path) -> Path:
        return source

    def map_workspace_rules_source(self, source: Path) -> Path:
        return source
