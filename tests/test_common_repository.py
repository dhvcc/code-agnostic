import json
from pathlib import Path

import pytest

from llm_sync.repositories.common import CommonRepository


@pytest.fixture
def common_repo(tmp_path: Path) -> CommonRepository:
    return CommonRepository(tmp_path)


def test_load_state_defaults_when_missing(common_repo: CommonRepository) -> None:
    repo = common_repo

    state = repo.load_state()

    assert state == {
        "managed_skill_links": [],
        "managed_agent_links": [],
        "managed_workspace_links": [],
    }


def test_add_and_remove_workspace_persists_config(tmp_path: Path, common_repo: CommonRepository) -> None:
    repo = common_repo
    workspace_dir = tmp_path / "example-workspace"
    workspace_dir.mkdir()

    repo.add_workspace("workspace-example", workspace_dir)
    workspaces = repo.load_workspaces()

    assert workspaces == [{"name": "workspace-example", "path": str(workspace_dir.resolve())}]

    removed = repo.remove_workspace("workspace-example")
    assert removed is True
    assert repo.load_workspaces() == []


def test_add_workspace_rejects_duplicates(tmp_path: Path, common_repo: CommonRepository) -> None:
    repo = common_repo
    workspace_dir = tmp_path / "example-workspace"
    workspace_dir.mkdir()
    repo.add_workspace("workspace-example", workspace_dir)
    another_workspace_dir = tmp_path / "another-example-workspace"
    another_workspace_dir.mkdir()

    with pytest.raises(ValueError, match="Workspace name already exists"):
        repo.add_workspace("workspace-example", another_workspace_dir)

    duplicate_path_name = tmp_path / "second"
    duplicate_path_name.mkdir()
    with pytest.raises(ValueError, match="Workspace path already exists"):
        repo.add_workspace("second", workspace_dir)


def test_load_workspaces_ignores_malformed_entries(tmp_path: Path, common_repo: CommonRepository) -> None:
    repo = common_repo
    repo.config_dir.mkdir(parents=True, exist_ok=True)

    payload = [
        {"name": "ok", "path": str((tmp_path / "ok").resolve())},
        {"name": "ok", "path": str((tmp_path / "dup").resolve())},
        {"name": "", "path": str((tmp_path / "empty").resolve())},
        {"name": "missing_path"},
        "bad-item",
    ]
    (tmp_path / "ok").mkdir()
    repo.workspaces_path.write_text(json.dumps(payload), encoding="utf-8")

    assert repo.load_workspaces() == [{"name": "ok", "path": str((tmp_path / "ok").resolve())}]
