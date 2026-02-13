from typing import Any

from code_agnostic.apps.sync.apps.opencode.mapper import OpenCodeMCPMapper
from code_agnostic.apps.sync.common import common_mcp_to_dto
from code_agnostic.mappers.base import IConfigMapper


class OpenCodeMapper(IConfigMapper):
    def map_mcp_servers(self, mcp_servers: dict[str, Any]) -> dict[str, Any]:
        dto = common_mcp_to_dto(mcp_servers)
        mapped = OpenCodeMCPMapper().from_common(dto)
        for name, raw in mcp_servers.items():
            if not isinstance(raw, dict) or name not in mapped:
                continue
            for key in ["enabled", "timeout"]:
                if key in raw:
                    mapped[name][key] = raw[key]
        return mapped


def map_mcp_servers_to_opencode(mcp_servers: dict[str, Any]) -> dict[str, Any]:
    return OpenCodeMapper().map_mcp_servers(mcp_servers)
