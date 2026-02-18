import json
from pathlib import Path

from code_agnostic.__main__ import cli


def _write_codex_source(root: Path, mcp_servers: dict, with_skill: bool = True) -> None:
    root.mkdir(parents=True, exist_ok=True)
    lines = []
    for name, payload in mcp_servers.items():
        lines.append(f"[mcp_servers.{name}]")
        if "command" in payload:
            lines.append(f'command = "{payload["command"]}"')
        if "url" in payload:
            lines.append(f'url = "{payload["url"]}"')
        lines.append("")
    (root / "config.toml").write_text("\n".join(lines), encoding="utf-8")
    if with_skill:
        skill_dir = root / "skills" / "imported-skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("from codex", encoding="utf-8")


def test_import_plan_codex_shows_sections(cli_runner, tmp_path: Path) -> None:
    _write_codex_source(
        tmp_path / ".codex",
        {"demo": {"command": "uvx"}},
    )

    result = cli_runner.invoke(cli, ["import", "plan", "-a", "codex"])

    assert result.exit_code == 0
    assert "import overview" in result.output
    assert "codex" in result.output
    assert "mcp" in result.output
    assert "skills" in result.output


def test_import_apply_codex_imports_mcp_and_skills(cli_runner, tmp_path: Path) -> None:
    _write_codex_source(
        tmp_path / ".codex",
        {"demo": {"command": "uvx"}},
    )

    result = cli_runner.invoke(cli, ["import", "apply", "-a", "codex"])

    assert result.exit_code == 0
    mcp_base = json.loads(
        (tmp_path / ".config" / "code-agnostic" / "config" / "mcp.base.json").read_text(
            encoding="utf-8"
        )
    )
    assert "demo" in mcp_base["mcpServers"]
    assert (
        tmp_path
        / ".config"
        / "code-agnostic"
        / "skills"
        / "imported-skill"
        / "SKILL.md"
    ).exists()


def test_import_apply_honors_include_filter(cli_runner, tmp_path: Path) -> None:
    _write_codex_source(
        tmp_path / ".codex",
        {"demo": {"command": "uvx"}},
    )

    result = cli_runner.invoke(
        cli, ["import", "apply", "-a", "codex", "--include", "mcp"]
    )

    assert result.exit_code == 0
    assert (
        tmp_path / ".config" / "code-agnostic" / "config" / "mcp.base.json"
    ).exists()
    assert not (
        tmp_path / ".config" / "code-agnostic" / "skills" / "imported-skill"
    ).exists()


def test_import_apply_honors_exclude_filter(cli_runner, tmp_path: Path) -> None:
    _write_codex_source(
        tmp_path / ".codex",
        {"demo": {"command": "uvx"}},
    )

    result = cli_runner.invoke(
        cli,
        ["import", "apply", "-a", "codex", "--exclude", "skills"],
    )

    assert result.exit_code == 0
    assert (
        tmp_path / ".config" / "code-agnostic" / "config" / "mcp.base.json"
    ).exists()
    assert not (
        tmp_path / ".config" / "code-agnostic" / "skills" / "imported-skill"
    ).exists()


def test_import_plan_reports_unsupported_section(cli_runner, tmp_path: Path) -> None:
    _write_codex_source(tmp_path / ".codex", {"demo": {"command": "uvx"}})

    result = cli_runner.invoke(
        cli,
        ["import", "plan", "-a", "codex", "--include", "agents"],
    )

    assert result.exit_code == 0
    assert "unsupported" in result.output.lower()


def test_import_apply_conflict_policy_skip_is_default(
    cli_runner, tmp_path: Path
) -> None:
    _write_codex_source(
        tmp_path / ".codex",
        {"demo": {"command": "uvx"}},
        with_skill=False,
    )
    core_mcp_path = tmp_path / ".config" / "code-agnostic" / "config" / "mcp.base.json"
    core_mcp_path.parent.mkdir(parents=True, exist_ok=True)
    core_mcp_path.write_text(
        json.dumps({"mcpServers": {"demo": {"url": "https://existing"}}}),
        encoding="utf-8",
    )

    result = cli_runner.invoke(
        cli, ["import", "apply", "-a", "codex", "--include", "mcp"]
    )

    assert result.exit_code == 0
    payload = json.loads(core_mcp_path.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["demo"] == {"url": "https://existing"}


def test_import_apply_conflict_policy_overwrite(cli_runner, tmp_path: Path) -> None:
    _write_codex_source(
        tmp_path / ".codex",
        {"demo": {"command": "uvx"}},
        with_skill=False,
    )
    core_mcp_path = tmp_path / ".config" / "code-agnostic" / "config" / "mcp.base.json"
    core_mcp_path.parent.mkdir(parents=True, exist_ok=True)
    core_mcp_path.write_text(
        json.dumps({"mcpServers": {"demo": {"url": "https://existing"}}}),
        encoding="utf-8",
    )

    result = cli_runner.invoke(
        cli,
        [
            "import",
            "apply",
            "-a",
            "codex",
            "--include",
            "mcp",
            "--on-conflict",
            "overwrite",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(core_mcp_path.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["demo"] == {"command": "uvx", "args": []}


def test_import_apply_conflict_policy_fail(cli_runner, tmp_path: Path) -> None:
    _write_codex_source(
        tmp_path / ".codex",
        {"demo": {"command": "uvx"}},
        with_skill=False,
    )
    core_mcp_path = tmp_path / ".config" / "code-agnostic" / "config" / "mcp.base.json"
    core_mcp_path.parent.mkdir(parents=True, exist_ok=True)
    core_mcp_path.write_text(
        json.dumps({"mcpServers": {"demo": {"url": "https://existing"}}}),
        encoding="utf-8",
    )

    result = cli_runner.invoke(
        cli,
        [
            "import",
            "apply",
            "-a",
            "codex",
            "--include",
            "mcp",
            "--on-conflict",
            "fail",
        ],
    )

    assert result.exit_code != 0
    assert "conflict" in result.output.lower()


def test_import_plan_default_view_shows_app_labels(cli_runner, tmp_path: Path) -> None:
    _write_codex_source(tmp_path / ".codex", {"demo": {"command": "uvx"}})

    result = cli_runner.invoke(cli, ["import", "plan", "-a", "codex"])

    assert result.exit_code == 0
    assert "Codex" in result.output
    assert "Code Agnostic" in result.output
    assert "Source Path" not in result.output
    assert "Target Path" not in result.output


def test_import_plan_verbose_view_shows_source_and_target_paths(
    cli_runner, tmp_path: Path
) -> None:
    _write_codex_source(tmp_path / ".codex", {"demo": {"command": "uvx"}})

    result = cli_runner.invoke(cli, ["import", "plan", "-a", "codex", "-v"])

    assert result.exit_code == 0
    assert "Path" in result.output
    assert "~/" in result.output
