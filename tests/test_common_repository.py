import json
from pathlib import Path

import pytest

from code_agnostic.errors import InvalidConfigSchemaError, InvalidJsonFormatError
from code_agnostic.core.repository import CoreRepository


@pytest.fixture
def core_repo(tmp_path: Path) -> CoreRepository:
    return CoreRepository(tmp_path)


def test_load_state_defaults_when_missing(core_repo: CoreRepository) -> None:
    repo = core_repo

    state = repo.load_state()

    assert state == {
        "managed_skill_links": [],
        "managed_agent_links": [],
        "managed_workspace_links": [],
    }


def test_add_and_remove_workspace_persists_config(
    tmp_path: Path, core_repo: CoreRepository
) -> None:
    repo = core_repo
    workspace_dir = tmp_path / "example-workspace"
    workspace_dir.mkdir()

    repo.add_workspace("workspace-example", workspace_dir)
    workspaces = repo.load_workspaces()

    assert workspaces == [
        {"name": "workspace-example", "path": str(workspace_dir.resolve())}
    ]

    removed = repo.remove_workspace("workspace-example")
    assert removed is True
    assert repo.load_workspaces() == []


def test_add_workspace_rejects_duplicates(
    tmp_path: Path, core_repo: CoreRepository
) -> None:
    repo = core_repo
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


def test_load_workspaces_ignores_malformed_entries(
    tmp_path: Path, core_repo: CoreRepository
) -> None:
    repo = core_repo
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

    assert repo.load_workspaces() == [
        {"name": "ok", "path": str((tmp_path / "ok").resolve())}
    ]


def test_load_mcp_base_raises_invalid_json_error(core_repo: CoreRepository) -> None:
    repo = core_repo
    repo.config_dir.mkdir(parents=True, exist_ok=True)
    repo.mcp_base_path.write_text("{bad", encoding="utf-8")
    repo.opencode_base_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(InvalidJsonFormatError):
        repo.load_mcp_base()


def test_load_mcp_base_raises_schema_error(core_repo: CoreRepository) -> None:
    repo = core_repo
    repo.config_dir.mkdir(parents=True, exist_ok=True)
    repo.mcp_base_path.write_text("{}\n", encoding="utf-8")
    repo.opencode_base_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(InvalidConfigSchemaError):
        repo.load_mcp_base()


def test_load_state_with_corrupted_json(
    tmp_path: Path, core_repo: CoreRepository
) -> None:
    repo = core_repo
    repo.state_json.parent.mkdir(parents=True, exist_ok=True)
    repo.state_json.write_text("{bad json", encoding="utf-8")

    state = repo.load_state()

    assert state == {
        "managed_skill_links": [],
        "managed_agent_links": [],
        "managed_workspace_links": [],
    }


def test_load_state_coerces_managed_skill_links_string_to_list(
    tmp_path: Path, core_repo: CoreRepository
) -> None:
    repo = core_repo
    repo.state_json.parent.mkdir(parents=True, exist_ok=True)
    repo.state_json.write_text(
        json.dumps({"managed_skill_links": "not-a-list"}), encoding="utf-8"
    )

    state = repo.load_state()

    assert state["managed_skill_links"] == []


def test_list_skill_sources_when_dir_missing(core_repo: CoreRepository) -> None:
    assert core_repo.list_skill_sources() == []


def test_list_skill_sources_skips_child_without_skill_md(
    core_repo: CoreRepository,
) -> None:
    (core_repo.skills_dir / "valid-skill").mkdir(parents=True)
    (core_repo.skills_dir / "valid-skill" / "SKILL.md").write_text(
        "skill", encoding="utf-8"
    )
    (core_repo.skills_dir / "no-skill-md").mkdir(parents=True)

    sources = core_repo.list_skill_sources()

    assert len(sources) == 1
    assert sources[0].name == "valid-skill"


def test_list_agent_sources_skips_dotfiles(core_repo: CoreRepository) -> None:
    core_repo.agents_dir.mkdir(parents=True)
    (core_repo.agents_dir / "planner.md").write_text("agent", encoding="utf-8")
    (core_repo.agents_dir / ".hidden").write_text("hidden", encoding="utf-8")

    sources = core_repo.list_agent_sources()

    names = [s.name for s in sources]
    assert "planner.md" in names
    assert ".hidden" not in names


def test_list_agent_sources_when_dir_missing(core_repo: CoreRepository) -> None:
    assert core_repo.list_agent_sources() == []


def test_load_opencode_base_missing_file(core_repo: CoreRepository) -> None:
    from code_agnostic.errors import MissingConfigFileError

    with pytest.raises(MissingConfigFileError):
        core_repo.load_opencode_base()


def test_load_opencode_base_invalid_json(core_repo: CoreRepository) -> None:
    core_repo.config_dir.mkdir(parents=True, exist_ok=True)
    core_repo.opencode_base_path.write_text("{bad", encoding="utf-8")

    with pytest.raises(InvalidJsonFormatError):
        core_repo.load_opencode_base()


def test_load_opencode_base_not_a_dict(core_repo: CoreRepository) -> None:
    core_repo.config_dir.mkdir(parents=True, exist_ok=True)
    core_repo.opencode_base_path.write_text('"just a string"', encoding="utf-8")

    with pytest.raises(InvalidConfigSchemaError):
        core_repo.load_opencode_base()


def test_remove_workspace_nonexistent(core_repo: CoreRepository) -> None:
    assert core_repo.remove_workspace("nonexistent") is False
