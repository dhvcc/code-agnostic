import pytest

from code_agnostic.apps.app_id import AppId, app_metadata, app_scope


@pytest.mark.parametrize(
    ("app_id", "project_dir_name", "config_filename", "workspace_propagation"),
    [
        (AppId.OPENCODE, ".opencode", "opencode.json", True),
        (AppId.CURSOR, ".cursor", "mcp.json", True),
        (AppId.CODEX, ".codex", "config.toml", True),
        (AppId.CLAUDE, ".claude", ".claude.json", True),
        (AppId.COPILOT, ".github", "mcp.json", True),
    ],
)
def test_app_metadata_exposes_project_and_config_names(
    app_id: AppId,
    project_dir_name: str,
    config_filename: str,
    workspace_propagation: bool,
) -> None:
    metadata = app_metadata(app_id)

    assert metadata.project_dir_name == project_dir_name
    assert metadata.config_filename == config_filename
    assert metadata.supports_workspace_propagation is workspace_propagation


@pytest.mark.parametrize(
    ("app_id", "resource", "expected"),
    [
        (AppId.OPENCODE, "skills", "app:opencode:skills"),
        (AppId.CURSOR, "agents", "app:cursor:agents"),
        (AppId.CODEX, "skills", "app:codex:skills"),
        (AppId.CLAUDE, "agents", "app:claude:agents"),
        (AppId.COPILOT, "agents", "app:copilot:agents"),
    ],
)
def test_app_scope_builds_consistent_scope_names(
    app_id: AppId, resource: str, expected: str
) -> None:
    assert app_scope(app_id, resource) == expected
