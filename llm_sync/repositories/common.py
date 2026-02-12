from pathlib import Path
from typing import Any, Optional

from llm_sync.repositories.base import ISourceRepository
from llm_sync.utils import read_json, read_json_safe, write_json


class CommonRepository(ISourceRepository):
    def __init__(self, root: Optional[Path] = None) -> None:
        self._root = root or (Path.home() / ".config" / "llm-sync")

    @property
    def root(self) -> Path:
        return self._root

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def skills_dir(self) -> Path:
        return self.root / "skills"

    @property
    def agents_dir(self) -> Path:
        return self.root / "agents"

    @property
    def state_json(self) -> Path:
        return self.root / ".sync-state.json"

    @property
    def state_md(self) -> Path:
        return self.root / "STATE.md"

    @property
    def mcp_base_path(self) -> Path:
        return self.config_dir / "mcp.base.json"

    @property
    def opencode_base_path(self) -> Path:
        return self.config_dir / "opencode.base.json"

    @property
    def workspaces_path(self) -> Path:
        return self.config_dir / "workspaces.json"

    def load_mcp_base(self) -> dict[str, Any]:
        if not self.mcp_base_path.exists():
            raise ValueError(f"Missing canonical file: {self.mcp_base_path}")
        payload = read_json(self.mcp_base_path)
        if not isinstance(payload, dict) or not isinstance(payload.get("mcpServers"), dict):
            raise ValueError(f"{self.mcp_base_path} must contain object key 'mcpServers'")
        return payload

    def load_opencode_base(self) -> dict[str, Any]:
        if not self.opencode_base_path.exists():
            raise ValueError(f"Missing canonical file: {self.opencode_base_path}")
        payload = read_json(self.opencode_base_path)
        if not isinstance(payload, dict):
            raise ValueError(f"{self.opencode_base_path} must be a JSON object")
        return payload

    def list_skill_sources(self) -> list[Path]:
        if not self.skills_dir.exists():
            return []
        result: list[Path] = []
        for child in sorted(self.skills_dir.iterdir()):
            if child.is_dir() and (child / "SKILL.md").exists():
                result.append(child)
        return result

    def list_agent_sources(self) -> list[Path]:
        if not self.agents_dir.exists():
            return []
        result: list[Path] = []
        for child in sorted(self.agents_dir.iterdir()):
            if child.name.startswith("."):
                continue
            result.append(child)
        return result

    def load_state(self) -> dict[str, Any]:
        payload, error = read_json_safe(self.state_json)
        if error is not None or not isinstance(payload, dict):
            return {
                "managed_skill_links": [],
                "managed_agent_links": [],
                "managed_workspace_links": [],
            }
        payload.setdefault("managed_skill_links", [])
        payload.setdefault("managed_agent_links", [])
        payload.setdefault("managed_workspace_links", [])
        if not isinstance(payload["managed_skill_links"], list):
            payload["managed_skill_links"] = []
        if not isinstance(payload["managed_agent_links"], list):
            payload["managed_agent_links"] = []
        if not isinstance(payload["managed_workspace_links"], list):
            payload["managed_workspace_links"] = []
        return payload

    def save_state(self, data: dict[str, Any]) -> None:
        write_json(self.state_json, data)

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
            raise ValueError(f"Workspace path does not exist or is not a directory: {normalized_path}")

        workspaces = self.load_workspaces()
        for item in workspaces:
            if item["name"] == normalized_name:
                raise ValueError(f"Workspace name already exists: {normalized_name}")
            if Path(item["path"]) == normalized_path:
                raise ValueError(f"Workspace path already exists: {normalized_path}")

        workspaces.append({"name": normalized_name, "path": str(normalized_path)})
        self.save_workspaces(workspaces)

    def remove_workspace(self, name: str) -> bool:
        target_name = name.strip()
        workspaces = self.load_workspaces()
        kept = [item for item in workspaces if item["name"] != target_name]
        if len(kept) == len(workspaces):
            return False
        self.save_workspaces(kept)
        return True
