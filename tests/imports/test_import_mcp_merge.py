import json
from pathlib import Path

from code_agnostic.core.repository import CoreRepository
from code_agnostic.imports.models import ConflictPolicy, ImportSection
from code_agnostic.imports.service import ImportService


def _write_codex_config(root: Path, payload: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "config.toml").write_text(payload, encoding="utf-8")


def test_mcp_import_creates_new_entries(tmp_path: Path) -> None:
    _write_codex_config(
        tmp_path / ".codex",
        "\n".join(["[mcp_servers.demo]", 'command = "uvx"', ""]),
    )
    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    service = ImportService(core)

    plan = service.plan(
        source_app="codex",
        include=[ImportSection.MCP],
        conflict_policy=ConflictPolicy.SKIP,
    )
    result = service.apply(plan)

    assert result.failed == 0
    payload = json.loads(core.mcp_base_path.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["demo"] == {"command": "uvx", "args": []}


def test_mcp_import_codex_env_vars_object_local_source(tmp_path: Path) -> None:
    _write_codex_config(
        tmp_path / ".codex",
        "\n".join(
            [
                "[mcp_servers.demo]",
                'command = "uvx"',
                'env_vars = [{ name = "LOCAL_TOKEN", source = "local" }]',
                "",
            ]
        ),
    )
    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    service = ImportService(core)

    plan = service.plan(
        source_app="codex",
        include=[ImportSection.MCP],
        conflict_policy=ConflictPolicy.SKIP,
    )
    result = service.apply(plan)

    assert result.failed == 0
    payload = json.loads(core.mcp_base_path.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["demo"] == {
        "command": "uvx",
        "args": [],
        "env": {"LOCAL_TOKEN": "${LOCAL_TOKEN}"},
    }


def test_mcp_import_codex_remote_env_vars_object_fails_closed(
    tmp_path: Path,
) -> None:
    _write_codex_config(
        tmp_path / ".codex",
        "\n".join(
            [
                "[mcp_servers.demo]",
                'command = "uvx"',
                'env_vars = [{ name = "REMOTE_TOKEN", source = "remote" }]',
                "",
            ]
        ),
    )
    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    service = ImportService(core)

    plan = service.plan(
        source_app="codex",
        include=[ImportSection.MCP],
        conflict_policy=ConflictPolicy.SKIP,
    )
    result = service.apply(plan)

    assert plan.actions == []
    assert any("source = 'remote'" in error for error in plan.errors)
    assert result.applied == 0
    assert result.failed == 1
    assert not core.mcp_base_path.exists()


def test_mcp_import_is_noop_for_identical_server(tmp_path: Path) -> None:
    _write_codex_config(
        tmp_path / ".codex",
        "\n".join(["[mcp_servers.demo]", 'command = "uvx"', ""]),
    )
    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    core.mcp_base_path.parent.mkdir(parents=True, exist_ok=True)
    core.mcp_base_path.write_text(
        json.dumps({"mcpServers": {"demo": {"command": "uvx", "args": []}}}),
        encoding="utf-8",
    )
    service = ImportService(core)

    plan = service.plan(
        source_app="codex",
        include=[ImportSection.MCP],
        conflict_policy=ConflictPolicy.SKIP,
    )

    statuses = [
        action.status.value for action in plan.actions if action.section == "mcp"
    ]
    assert "noop" in statuses


def test_mcp_import_conflict_skip_keeps_existing(tmp_path: Path) -> None:
    _write_codex_config(
        tmp_path / ".codex",
        "\n".join(["[mcp_servers.demo]", 'command = "uvx"', ""]),
    )
    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    core.mcp_base_path.parent.mkdir(parents=True, exist_ok=True)
    core.mcp_base_path.write_text(
        json.dumps({"mcpServers": {"demo": {"url": "https://existing"}}}),
        encoding="utf-8",
    )
    service = ImportService(core)

    plan = service.plan(
        source_app="codex",
        include=[ImportSection.MCP],
        conflict_policy=ConflictPolicy.SKIP,
    )
    service.apply(plan)

    payload = json.loads(core.mcp_base_path.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["demo"] == {"url": "https://existing"}


def test_mcp_import_conflict_overwrite_replaces_existing(tmp_path: Path) -> None:
    _write_codex_config(
        tmp_path / ".codex",
        "\n".join(["[mcp_servers.demo]", 'command = "uvx"', ""]),
    )
    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    core.mcp_base_path.parent.mkdir(parents=True, exist_ok=True)
    core.mcp_base_path.write_text(
        json.dumps({"mcpServers": {"demo": {"url": "https://existing"}}}),
        encoding="utf-8",
    )
    service = ImportService(core)

    plan = service.plan(
        source_app="codex",
        include=[ImportSection.MCP],
        conflict_policy=ConflictPolicy.OVERWRITE,
    )
    service.apply(plan)

    payload = json.loads(core.mcp_base_path.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["demo"] == {"command": "uvx", "args": []}


def test_mcp_import_preserves_existing_schema_metadata(tmp_path: Path) -> None:
    _write_codex_config(
        tmp_path / ".codex",
        "\n".join(["[mcp_servers.demo]", 'command = "uvx"', ""]),
    )
    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    core.mcp_base_path.parent.mkdir(parents=True, exist_ok=True)
    core.mcp_base_path.write_text(
        json.dumps(
            {
                "$schema": "https://example.test/mcp.base.schema.json",
                "mcpServers": {
                    "existing": {"command": "existing", "args": []},
                },
            }
        ),
        encoding="utf-8",
    )
    service = ImportService(core)

    plan = service.plan(
        source_app="codex",
        include=[ImportSection.MCP],
        conflict_policy=ConflictPolicy.SKIP,
    )
    service.apply(plan)

    payload = json.loads(core.mcp_base_path.read_text(encoding="utf-8"))
    assert payload["$schema"] == "https://example.test/mcp.base.schema.json"
    assert payload["mcpServers"]["existing"] == {"command": "existing", "args": []}
    assert payload["mcpServers"]["demo"] == {"command": "uvx", "args": []}


def test_mcp_import_bootstraps_missing_hub_file(tmp_path: Path) -> None:
    _write_codex_config(
        tmp_path / ".codex",
        "\n".join(["[mcp_servers.demo]", 'command = "uvx"', ""]),
    )
    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    service = ImportService(core)

    plan = service.plan(
        source_app="codex",
        include=[ImportSection.MCP],
        conflict_policy=ConflictPolicy.SKIP,
    )
    service.apply(plan)

    assert core.mcp_base_path.exists()


def test_mcp_import_skips_missing_source_config_instead_of_writing_empty_hub(
    tmp_path: Path,
) -> None:
    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    service = ImportService(core)

    plan = service.plan(
        source_app="codex",
        include=[ImportSection.MCP],
        conflict_policy=ConflictPolicy.SKIP,
    )
    result = service.apply(plan)

    assert plan.actions == []
    assert "Source MCP config missing" in plan.skipped[0]
    assert result.applied == 0
    assert result.failed == 0
    assert not core.mcp_base_path.exists()


def test_mcp_import_skips_source_config_without_mcp_entries(tmp_path: Path) -> None:
    _write_codex_config(tmp_path / ".codex", 'model = "gpt-5"\n')
    core = CoreRepository(tmp_path / ".config" / "code-agnostic")
    service = ImportService(core)

    plan = service.plan(
        source_app="codex",
        include=[ImportSection.MCP],
        conflict_policy=ConflictPolicy.SKIP,
    )

    assert plan.actions == []
    assert "No MCP servers found in source config" in plan.skipped[0]
    assert not core.mcp_base_path.exists()
