"""Tests for GitExcludeService."""

from pathlib import Path

import pytest

from code_agnostic.constants import AGENTS_FILENAME, CLAUDE_FILENAME
from code_agnostic.core.repository import CoreRepository
from code_agnostic.git_exclude_service import GitExcludeService


@pytest.fixture
def service_with_workspace(minimal_shared_config: Path, tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    core = CoreRepository()
    core.add_workspace("myws", ws)
    service = GitExcludeService(core)
    return service


def test_defaults_only(service_with_workspace) -> None:
    entries = service_with_workspace.compute_entries("myws", ["cursor", "codex"])
    assert ".cursor" not in entries
    assert ".codex" in entries
    assert AGENTS_FILENAME in entries
    assert CLAUDE_FILENAME in entries


def test_custom_patterns_merged(service_with_workspace) -> None:
    service_with_workspace.add_pattern("myws", "*.generated")
    entries = service_with_workspace.compute_entries("myws", ["cursor"])
    assert ".cursor" not in entries
    assert AGENTS_FILENAME in entries
    assert "*.generated" in entries


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
