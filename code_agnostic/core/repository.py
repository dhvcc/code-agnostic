from abc import abstractmethod
from pathlib import Path
from typing import Any

from code_agnostic.apps.common.interfaces.repositories import ISourceRepository
from code_agnostic.apps.common.utils import dto_to_common_mcp
from code_agnostic.errors import (
    InvalidConfigSchemaError,
    InvalidJsonFormatError,
    MissingConfigFileError,
)
from code_agnostic.spec.loaders import load_mcp_base as load_mcp_bundle
from code_agnostic.utils import read_json_safe, write_json


class BaseSourceRepository(ISourceRepository):
    """Source repository that reads MCP, skills, agents from a root directory."""

    def __init__(self, root: Path) -> None:
        self._root = root

    @property
    def root(self) -> Path:
        return self._root

    @property
    @abstractmethod
    def mcp_base_path(self) -> Path:
        raise NotImplementedError

    @property
    def mcp_base_yaml_path(self) -> Path:
        return self.mcp_base_path.with_suffix(".yaml")

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def agents_dir(self) -> Path:
        return self.root / "agents"

    @property
    def state_json(self) -> Path:
        return self.root / ".sync-state.json"

    def load_mcp_base(self) -> dict[str, Any]:
        if self.mcp_base_path.exists():
            payload, error = read_json_safe(self.mcp_base_path)
            if error is not None:
                raise InvalidJsonFormatError(self.mcp_base_path, error)
            if not isinstance(payload, dict) or not isinstance(
                payload.get("mcpServers"), dict
            ):
                raise InvalidConfigSchemaError(
                    self.mcp_base_path, "must contain object key 'mcpServers'"
                )
            return payload

        if self.mcp_base_yaml_path.exists():
            servers = load_mcp_bundle(self.mcp_base_yaml_path)
            return {"mcpServers": dto_to_common_mcp(servers)}

        raise MissingConfigFileError(self.mcp_base_path)

    def list_skill_sources(self) -> list[Path]:
        if not self.skills_dir.exists():
            return []
        result: list[Path] = []
        for child in sorted(self.skills_dir.iterdir()):
            if child.is_dir() and (
                (child / "SKILL.md").exists()
                or ((child / "meta.yaml").exists() and (child / "prompt.md").exists())
            ):
                result.append(child)
        return result

    def list_agent_sources(self) -> list[Path]:
        if not self.agents_dir.exists():
            return []
        result: list[Path] = []
        for child in sorted(self.agents_dir.iterdir()):
            if child.name.startswith("."):
                continue
            if child.is_file():
                result.append(child)
                continue
            if (
                child.is_dir()
                and (child / "meta.yaml").exists()
                and (child / "prompt.md").exists()
            ):
                result.append(child)
        return result

    def load_state(self) -> dict[str, Any]:
        payload, error = read_json_safe(self.state_json)
        if error is not None or not isinstance(payload, dict):
            return {
                "managed_skill_links": [],
                "managed_agent_links": [],
                "managed_workspace_links": [],
                "managed_links": {},
                "managed_paths": {},
            }
        payload.setdefault("managed_skill_links", [])
        payload.setdefault("managed_agent_links", [])
        payload.setdefault("managed_workspace_links", [])
        payload.setdefault("managed_links", {})
        payload.setdefault("managed_paths", {})
        if not isinstance(payload["managed_skill_links"], list):
            payload["managed_skill_links"] = []
        if not isinstance(payload["managed_agent_links"], list):
            payload["managed_agent_links"] = []
        if not isinstance(payload["managed_workspace_links"], list):
            payload["managed_workspace_links"] = []
        if not isinstance(payload["managed_links"], dict):
            payload["managed_links"] = {}
        if not isinstance(payload["managed_paths"], dict):
            payload["managed_paths"] = {}
        return payload

    def save_state(self, data: dict[str, Any]) -> None:
        write_json(self.state_json, data)

    def load_workspaces(self) -> list[dict[str, str]]:
        return []


class CoreRepository(BaseSourceRepository):
    def __init__(self, root: Path | None = None) -> None:
        super().__init__(root or (Path.home() / ".config" / "code-agnostic"))

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def mcp_base_path(self) -> Path:
        return self.config_dir / "mcp.base.json"

    @property
    def opencode_base_path(self) -> Path:
        return self.config_dir / "opencode.base.json"

    @property
    def codex_base_path(self) -> Path:
        return self.config_dir / "codex.base.json"

    @property
    def workspaces_path(self) -> Path:
        return self.config_dir / "workspaces.json"

    @property
    def workspaces_dir(self) -> Path:
        return self.root / "workspaces"

    def workspace_config_dir(self, name: str) -> Path:
        return self.workspaces_dir / name

    def load_opencode_base(self) -> dict[str, Any]:
        if not self.opencode_base_path.exists():
            raise MissingConfigFileError(self.opencode_base_path)
        payload, error = read_json_safe(self.opencode_base_path)
        if error is not None:
            raise InvalidJsonFormatError(self.opencode_base_path, error)
        if not isinstance(payload, dict):
            raise InvalidConfigSchemaError(
                self.opencode_base_path, "must be a JSON object"
            )
        return payload

    def load_codex_base(self) -> dict[str, Any]:
        if not self.codex_base_path.exists():
            raise MissingConfigFileError(self.codex_base_path)
        payload, error = read_json_safe(self.codex_base_path)
        if error is not None:
            raise InvalidJsonFormatError(self.codex_base_path, error)
        if not isinstance(payload, dict):
            raise InvalidConfigSchemaError(
                self.codex_base_path, "must be a JSON object"
            )
        return payload

    def load_workspaces(self) -> list[dict[str, str]]:
        payload, error = read_json_safe(self.workspaces_path)
        if error is not None or payload is None:
            return []
        if not isinstance(payload, list):
            return []

        result: list[dict[str, str]] = []
        seen_names: set[str] = set()
        for item in payload:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            path = item.get("path")
            if not isinstance(name, str) or not isinstance(path, str):
                continue
            normalized_name = name.strip()
            normalized_path = str(Path(path).expanduser().resolve())
            if not normalized_name or normalized_name in seen_names:
                continue
            result.append({"name": normalized_name, "path": normalized_path})
            seen_names.add(normalized_name)
        return result

    def save_workspaces(self, workspaces: list[dict[str, str]]) -> None:
        serialized = sorted(
            [{"name": item["name"], "path": item["path"]} for item in workspaces],
            key=lambda item: item["name"].lower(),
        )
        write_json(self.workspaces_path, serialized)

    def add_workspace(self, name: str, path: Path) -> None:
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Workspace name cannot be empty")
        normalized_path = path.expanduser().resolve()
        if not normalized_path.exists() or not normalized_path.is_dir():
            raise ValueError(
                f"Workspace path does not exist or is not a directory: {normalized_path}"
            )

        workspaces = self.load_workspaces()
        for item in workspaces:
            if item["name"] == normalized_name:
                raise ValueError(f"Workspace name already exists: {normalized_name}")
            if Path(item["path"]) == normalized_path:
                raise ValueError(f"Workspace path already exists: {normalized_path}")

        workspaces.append({"name": normalized_name, "path": str(normalized_path)})
        self.save_workspaces(workspaces)
        self.workspace_config_dir(normalized_name).mkdir(parents=True, exist_ok=True)

    def remove_workspace(self, name: str) -> bool:
        target_name = name.strip()
        workspaces = self.load_workspaces()
        kept = [item for item in workspaces if item["name"] != target_name]
        if len(kept) == len(workspaces):
            return False
        self.save_workspaces(kept)
        return True
