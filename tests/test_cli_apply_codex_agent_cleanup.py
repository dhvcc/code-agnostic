"""Codex agent-registry ownership: an agent removed from the source is pruned
from `[agents.*]` in ~/.codex/config.toml on the next apply, while base-config
agent settings and user-added entries survive."""

from pathlib import Path

from code_agnostic.__main__ import cli

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def _write_agent(core_root: Path, name: str) -> None:
    agent = core_root / "agents" / f"{name}.md"
    agent.parent.mkdir(parents=True, exist_ok=True)
    agent.write_text(
        f"---\nname: {name}\ndescription: {name} specialist\n---\n\nDo {name}.\n",
        encoding="utf-8",
    )


def test_apply_codex_prunes_removed_agent_from_registry(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("codex")
    # Base-config agent settings + a user-managed agent entry must be preserved.
    (core_root / "config" / "codex.base.json").write_text(
        '{"agents": {"max_depth": 2}}', encoding="utf-8"
    )
    (tmp_path / ".codex").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".codex" / "config.toml").write_text(
        '[agents.mine]\ndescription = "user agent"\nconfig_file = "agents/mine.toml"\n',
        encoding="utf-8",
    )
    _write_agent(core_root, "planner")
    _write_agent(core_root, "reviewer")

    assert cli_runner.invoke(cli, ["apply", "-a", "codex"]).exit_code == 0
    cfg = tomllib.loads(
        (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    assert cfg["agents"]["max_depth"] == 2
    assert set(cfg["agents"]) >= {"planner", "reviewer", "mine", "max_depth"}

    state_path = core_root / ".sync-state.json"
    import json

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["managed_mcp"]["app:codex:agents_registry"] == ["planner", "reviewer"]

    # Remove reviewer from the source and re-apply.
    (core_root / "agents" / "reviewer.md").unlink()
    assert cli_runner.invoke(cli, ["apply", "-a", "codex"]).exit_code == 0

    cfg = tomllib.loads(
        (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    agents = cfg["agents"]
    assert "reviewer" not in agents, "our removed agent must be pruned from registry"
    assert "planner" in agents
    assert agents["mine"]["description"] == "user agent", "user entry preserved"
    assert agents["max_depth"] == 2, "base-config agent settings preserved"

    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["managed_mcp"]["app:codex:agents_registry"] == ["planner"]
