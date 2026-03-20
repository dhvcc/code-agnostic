import pytest

from code_agnostic.apps.app_id import AppId, app_metadata, app_scope


@pytest.mark.parametrize(
    ("app_id", "project_dir_name", "config_filename"),
    [
        (AppId.OPENCODE, ".opencode", "opencode.json"),
        (AppId.CURSOR, ".cursor", "mcp.json"),
        (AppId.CODEX, ".codex", "config.toml"),
    ],
)
def test_app_metadata_exposes_project_and_config_names(
    app_id: AppId, project_dir_name: str, config_filename: str
) -> None:
    metadata = app_metadata(app_id)

    assert metadata.project_dir_name == project_dir_name
    assert metadata.config_filename == config_filename


@pytest.mark.parametrize(
    ("app_id", "resource", "expected"),
    [
        (AppId.OPENCODE, "skills", "app:opencode:skills"),
        (AppId.CURSOR, "agents", "app:cursor:agents"),
        (AppId.CODEX, "skills", "app:codex:skills"),
    ],
)
def test_app_scope_builds_consistent_scope_names(
    app_id: AppId, resource: str, expected: str
) -> None:
    assert app_scope(app_id, resource) == expected
