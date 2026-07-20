"""P0-1/P0-2: MCP servers removed from the source are pruned from targets on the
next apply, while servers the user added by hand are preserved. Ownership is
tracked in sync_state.json (managed_mcp)."""

import json
from pathlib import Path

from code_agnostic.__main__ import cli

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def _write_mcp_base(core_root: Path, servers: dict) -> None:
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps({"mcpServers": servers}), encoding="utf-8"
    )


def test_apply_claude_prunes_removed_server_keeps_user_server(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("claude")
    # User added their own server directly in ~/.claude.json.
    (tmp_path / ".claude.json").write_text(
        json.dumps(
            {"mcpServers": {"personal": {"type": "http", "url": "https://p/mcp"}}}
        ),
        encoding="utf-8",
    )
    _write_mcp_base(
        core_root,
        {
            "alpha": {"command": "uvx", "args": ["alpha"]},
            "beta": {"command": "uvx", "args": ["beta"]},
        },
    )

    assert cli_runner.invoke(cli, ["apply", "-a", "claude"]).exit_code == 0

    payload = json.loads((tmp_path / ".claude.json").read_text(encoding="utf-8"))
    assert set(payload["mcpServers"]) == {"personal", "alpha", "beta"}

    state = json.loads((core_root / ".sync-state.json").read_text(encoding="utf-8"))
    assert state["managed_mcp"]["app:claude:mcp"] == ["alpha", "beta"]

    # Remove beta from the source and re-apply.
    _write_mcp_base(core_root, {"alpha": {"command": "uvx", "args": ["alpha"]}})
    assert cli_runner.invoke(cli, ["apply", "-a", "claude"]).exit_code == 0

    payload = json.loads((tmp_path / ".claude.json").read_text(encoding="utf-8"))
    assert set(payload["mcpServers"]) == {
        "personal",
        "alpha",
    }, "beta (ours, removed from source) must be pruned; personal (user's) kept"
    state = json.loads((core_root / ".sync-state.json").read_text(encoding="utf-8"))
    assert state["managed_mcp"]["app:claude:mcp"] == ["alpha"]


def test_apply_codex_prunes_removed_server_keeps_user_server(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("codex")
    (tmp_path / ".codex").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".codex" / "config.toml").write_text(
        '[mcp_servers.personal]\ncommand = "uvx"\nargs = ["personal"]\n',
        encoding="utf-8",
    )
    _write_mcp_base(
        core_root,
        {
            "alpha": {"command": "uvx", "args": ["alpha"]},
            "beta": {"command": "uvx", "args": ["beta"]},
        },
    )

    assert cli_runner.invoke(cli, ["apply", "-a", "codex"]).exit_code == 0
    payload = tomllib.loads(
        (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    assert set(payload["mcp_servers"]) == {"personal", "alpha", "beta"}

    _write_mcp_base(core_root, {"alpha": {"command": "uvx", "args": ["alpha"]}})
    assert cli_runner.invoke(cli, ["apply", "-a", "codex"]).exit_code == 0

    payload = tomllib.loads(
        (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    assert set(payload["mcp_servers"]) == {
        "personal",
        "alpha",
    }, "beta must be pruned from ~/.codex; personal must survive"
