"""P0-3: `apps disable` cleans up everything the app previously synced (compiled
skills/agents and the MCP servers we own) and clears the tracked state, instead
of stranding orphans on disk."""

import json
from pathlib import Path

from code_agnostic.__main__ import cli


def _write_skill(core_root: Path, name: str) -> None:
    skill = core_root / "skills" / name / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text(
        f"---\nname: {name}\ndescription: {name} skill\n---\n\nDo {name}.\n",
        encoding="utf-8",
    )


def test_disable_cursor_removes_skill_and_prunes_owned_mcp(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")
    _write_skill(core_root, "reviewer")
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps({"mcpServers": {"team": {"command": "uvx", "args": ["team"]}}}),
        encoding="utf-8",
    )
    # User's own server, added directly.
    (tmp_path / ".cursor").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".cursor" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"personal": {"url": "https://p/mcp"}}}),
        encoding="utf-8",
    )

    assert cli_runner.invoke(cli, ["apply", "-a", "cursor"]).exit_code == 0

    skill_file = tmp_path / ".cursor" / "skills" / "reviewer" / "SKILL.md"
    mcp_file = tmp_path / ".cursor" / "mcp.json"
    assert skill_file.exists()
    assert set(json.loads(mcp_file.read_text())["mcpServers"]) == {"personal", "team"}

    state = json.loads((core_root / ".sync-state.json").read_text())
    assert state["managed_mcp"]["app:cursor:mcp"] == ["team"]
    assert any(
        scope.startswith("app:cursor:") for scope in state.get("managed_paths", {})
    )

    # Disable → everything cursor-synced must be reclaimed.
    result = cli_runner.invoke(cli, ["apps", "disable", "-a", "cursor"])
    assert result.exit_code == 0

    assert not skill_file.exists(), "compiled skill must be removed on disable"
    remaining = json.loads(mcp_file.read_text())["mcpServers"]
    assert set(remaining) == {"personal"}, "our server pruned, user's kept"

    state = json.loads((core_root / ".sync-state.json").read_text())
    assert not any(
        scope.startswith("app:cursor:") for scope in state.get("managed_paths", {})
    ), "cursor state must be cleared after disable"
    assert "app:cursor:mcp" not in state.get("managed_mcp", {})

    # Flag is off.
    apps_cfg = json.loads((core_root / "config" / "apps.json").read_text())
    assert apps_cfg["cursor"] is False
