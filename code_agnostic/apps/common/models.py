from dataclasses import dataclass, field
from enum import Enum


class MCPServerType(str, Enum):
    STDIO = "stdio"
    HTTP = "http"
    OAUTH = "oauth"


@dataclass(frozen=True)
class MCPAuthDTO:
    client_id: str
    client_secret: str
    scopes: list[str] = field(default_factory=list)
    token_endpoint: str | None = None


@dataclass(frozen=True)
class MCPServerDTO:
    name: str
    type: MCPServerType
    command: str | None = None
    args: list[str] = field(default_factory=list)
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    auth: MCPAuthDTO | None = None
