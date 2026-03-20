from pathlib import Path

from code_agnostic.__main__ import cli


def test_validate_succeeds_for_mixed_legacy_and_bundle_sources(
    minimal_shared_config: Path,
    core_root: Path,
    cli_runner,
) -> None:
    (core_root / "rules").mkdir(parents=True)
    (core_root / "rules" / "legacy.md").write_text(
        "---\ndescription: Legacy rule\n---\n\nRule body.\n", encoding="utf-8"
    )

    skill_dir = core_root / "skills" / "bundle-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "meta.yaml").write_text(
        "spec_version: v1\nkind: skill\nname: bundle-skill\n", encoding="utf-8"
    )
    (skill_dir / "prompt.md").write_text("Skill body.\n", encoding="utf-8")

    agent_dir = core_root / "agents" / "bundle-agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "meta.yaml").write_text(
        "spec_version: v1\nkind: agent\nname: bundle-agent\n", encoding="utf-8"
    )
    (agent_dir / "prompt.md").write_text("Agent body.\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["validate"])

    assert result.exit_code == 0
    assert "Validated 4 resources." in result.output


def test_validate_fails_for_unknown_bundle_key(
    minimal_shared_config: Path,
    core_root: Path,
    cli_runner,
) -> None:
    skill_dir = core_root / "skills" / "bundle-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: skill\n"
        "name: bundle-skill\n"
        "unsupported: true\n",
        encoding="utf-8",
    )
    (skill_dir / "prompt.md").write_text("Skill body.\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["validate"])

    assert result.exit_code != 0
    assert "bundle-skill" in result.output
    assert "Invalid config schema" in result.output


def test_validate_fails_for_missing_bundle_prompt(
    minimal_shared_config: Path,
    core_root: Path,
    cli_runner,
) -> None:
    agent_dir = core_root / "agents" / "bundle-agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "meta.yaml").write_text(
        "spec_version: v1\nkind: agent\nname: bundle-agent\n", encoding="utf-8"
    )

    result = cli_runner.invoke(cli, ["validate"])

    assert result.exit_code != 0
    assert "bundle-agent" in result.output
    assert "Missing required config file" in result.output


def test_validate_workspace_sources(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "team", "--path", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    ws_config_dir = core_root / "workspaces" / "team"
    rule_dir = ws_config_dir / "rules" / "bundle-rule"
    rule_dir.mkdir(parents=True)
    (rule_dir / "meta.yaml").write_text(
        "spec_version: v1\nkind: rule\ndescription: Shared rule\n", encoding="utf-8"
    )
    (rule_dir / "prompt.md").write_text("Rule body.\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["validate", "-w", "team"])

    assert result.exit_code == 0
    assert "Validated 1 resources." in result.output
