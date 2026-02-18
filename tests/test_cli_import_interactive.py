"""Tests that the --interactive / -i flag is accepted on import commands."""

from pathlib import Path

from code_agnostic.__main__ import cli


def _write_codex_source(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    lines = [
        "[mcp_servers.demo]",
        'command = "uvx"',
        "",
    ]
    (root / "config.toml").write_text("\n".join(lines), encoding="utf-8")
    skill_dir = root / "skills" / "imported-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("from codex", encoding="utf-8")


def test_import_plan_accepts_interactive_flag(cli_runner, tmp_path: Path) -> None:
    """Verify -i flag is accepted (doesn't error on 'no such option')."""
    _write_codex_source(tmp_path / ".codex")

    # We can't actually run the TUI in a test runner, so we check
    # that the help text includes the option.
    result = cli_runner.invoke(cli, ["import", "plan", "--help"])
    assert result.exit_code == 0
    assert "--interactive" in result.output
    assert "-i" in result.output


def test_import_apply_accepts_interactive_flag(cli_runner, tmp_path: Path) -> None:
    """Verify -i flag is accepted (doesn't error on 'no such option')."""
    _write_codex_source(tmp_path / ".codex")

    result = cli_runner.invoke(cli, ["import", "apply", "--help"])
    assert result.exit_code == 0
    assert "--interactive" in result.output
    assert "-i" in result.output
