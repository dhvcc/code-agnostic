from pathlib import Path

import pytest


@pytest.fixture
def expected_app_config_path(tmp_path: Path):
    def _path_for(app: str) -> Path:
        if app == "opencode":
            return tmp_path / ".config" / "opencode" / "opencode.json"
        if app == "cursor":
            return tmp_path / ".cursor" / "mcp.json"
        if app == "codex":
            return tmp_path / ".codex" / "config.toml"
        raise ValueError(f"unknown app: {app}")

    return _path_for
