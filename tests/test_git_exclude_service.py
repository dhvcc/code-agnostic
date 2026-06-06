"""Tests for GitExcludeService."""

from pathlib import Path

import pytest

from code_agnostic.constants import (
    AGENTS_FILENAME,
    CLAUDE_LOCAL_FILENAME,
    CODEX_AGENTS_OVERRIDE_FILENAME,
)
from code_agnostic.core.repository import CoreRepository
from code_agnostic.git_exclude_service import GitExcludeService
from code_agnostic.utils import write_json


@pytest.fixture
def service_with_workspace(minimal_shared_config: Path, tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    core = CoreRepository()
    core.add_workspace("myws", ws)
    service = GitExcludeService(core)
    return service


def test_defaults_are_exact_generated_artifact_paths(service_with_workspace) -> None:
    core = CoreRepository()
    ws_config = core.workspace_config_dir("myws")
    (ws_config / AGENTS_FILENAME).write_text("rules\n", encoding="utf-8")
    write_json(
        ws_config / "mcp.base.json",
        {"mcpServers": {"demo": {"command": "uvx", "args": ["demo"]}}},
    )
    (ws_config / "skills" / "review").mkdir(parents=True)
    (ws_config / "skills" / "review" / "SKILL.md").write_text(
        "review\n", encoding="utf-8"
    )
    (ws_config / "agents").mkdir(parents=True)
    (ws_config / "agents" / "planner.md").write_text("plan\n", encoding="utf-8")

    entries = service_with_workspace.compute_entries("myws", ["cursor", "codex"])

    assert entries == [
        ".agents/skills/review/SKILL.md",
        ".codex/agents/planner.toml",
        ".codex/config.toml",
        ".cursor/agents/planner.md",
        ".cursor/mcp.json",
        ".cursor/skills/review/SKILL.md",
        AGENTS_FILENAME,
        CODEX_AGENTS_OVERRIDE_FILENAME,
    ]
    assert ".cursor" not in entries
    assert ".codex" not in entries
    assert ".agents" not in entries
    assert CLAUDE_LOCAL_FILENAME not in entries
    assert "CLAUDE.md" not in entries


def test_claude_defaults_include_only_owned_paths(
    service_with_workspace,
    minimal_shared_config: Path,
) -> None:
    core = CoreRepository()
    ws_config = core.workspace_config_dir("myws")
    (ws_config / AGENTS_FILENAME).write_text("rules\n", encoding="utf-8")
    (ws_config / "skills" / "review").mkdir(parents=True)
    (ws_config / "skills" / "review" / "SKILL.md").write_text(
        "review\n", encoding="utf-8"
    )
    (ws_config / "agents").mkdir(parents=True)
    (ws_config / "agents" / "planner.md").write_text("plan\n", encoding="utf-8")

    entries = service_with_workspace.compute_entries("myws", ["claude"])

    assert ".claude" not in entries
    assert CLAUDE_LOCAL_FILENAME in entries
    assert "CLAUDE.md" not in entries
    assert ".claude/skills/review/SKILL.md" in entries
    assert ".claude/agents/planner.md" in entries


def test_custom_patterns_merged(service_with_workspace) -> None:
    service_with_workspace.add_pattern("myws", "*.generated")
    entries = service_with_workspace.compute_entries("myws", ["cursor"])
    assert entries == ["*.generated"]


def test_no_defaults(minimal_shared_config: Path, tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    core = CoreRepository()
    core.add_workspace("myws", ws)
    service = GitExcludeService(core)

    service.add_pattern("myws", "custom-only")

    from code_agnostic.utils import write_json

    config_path = core.workspace_config_dir("myws") / "git-exclude.json"
    write_json(
        config_path, {"include_defaults": False, "extra_patterns": ["custom-only"]}
    )

    entries = service.compute_entries("myws", ["cursor"])
    assert entries == ["custom-only"]
    assert ".cursor" not in entries


def test_add_pattern(service_with_workspace) -> None:
    service_with_workspace.add_pattern("myws", "*.tmp")
    config = service_with_workspace.list_patterns("myws")
    assert "*.tmp" in config["extra_patterns"]


def test_add_pattern_idempotent(service_with_workspace) -> None:
    service_with_workspace.add_pattern("myws", "*.tmp")
    service_with_workspace.add_pattern("myws", "*.tmp")
    config = service_with_workspace.list_patterns("myws")
    assert config["extra_patterns"].count("*.tmp") == 1


def test_remove_pattern(service_with_workspace) -> None:
    service_with_workspace.add_pattern("myws", "*.tmp")
    assert service_with_workspace.remove_pattern("myws", "*.tmp") is True
    config = service_with_workspace.list_patterns("myws")
    assert "*.tmp" not in config["extra_patterns"]


def test_remove_nonexistent_pattern(service_with_workspace) -> None:
    assert service_with_workspace.remove_pattern("myws", "nope") is False


def test_workspace_not_found(minimal_shared_config: Path) -> None:
    core = CoreRepository()
    service = GitExcludeService(core)
    with pytest.raises(ValueError, match="not found"):
        service.add_pattern("nonexistent", "*.tmp")
