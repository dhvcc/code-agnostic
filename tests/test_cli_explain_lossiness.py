from pathlib import Path

from code_agnostic.__main__ import cli


def test_explain_lossiness_reports_documented_rule_and_agent_mappings(
    minimal_shared_config: Path,
    core_root: Path,
    cli_runner,
) -> None:
    rule_dir = core_root / "rules" / "bundle-rule"
    rule_dir.mkdir(parents=True)
    (rule_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: rule\n"
        "description: Shared rule\n"
        "globs:\n"
        "  - '*.py'\n"
        "always_apply: true\n",
        encoding="utf-8",
    )
    (rule_dir / "prompt.md").write_text("Rule body.\n", encoding="utf-8")

    agent_dir = core_root / "agents" / "bundle-agent"
    agent_dir.mkdir(parents=True)
    (agent_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: agent\n"
        "name: bundle-agent\n"
        "sandbox_mode: workspace-write\n"
        "nickname_candidates:\n"
        "  - Atlas\n"
        "codex:\n"
        "  mcp_servers:\n"
        "    docs:\n"
        "      type: streamable-http\n"
        "      url: https://example.com/mcp\n"
        "  skills:\n"
        "    config:\n"
        "      - path: .agents/skills/review.md\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("Agent body.\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["explain-lossiness"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "resource_path\tapp\tproperty\tstatus\treason",
        "agents/bundle-agent\tclaude\tcodex.mcp_servers\tignored\ttarget only supports codex.mcp_servers in Codex output",
        "agents/bundle-agent\tclaude\tcodex.skills.config\tignored\ttarget only supports codex.skills.config in Codex output",
        "agents/bundle-agent\tclaude\tnickname_candidates\tignored\ttarget does not support agent nickname_candidates",
        "agents/bundle-agent\tclaude\tsandbox_mode\tignored\ttarget does not support agent sandbox_mode",
        "agents/bundle-agent\tcopilot\tcodex.mcp_servers\tignored\ttarget only supports codex.mcp_servers in Codex output",
        "agents/bundle-agent\tcopilot\tcodex.skills.config\tignored\ttarget only supports codex.skills.config in Codex output",
        "agents/bundle-agent\tcopilot\tnickname_candidates\tignored\ttarget does not support agent nickname_candidates",
        "agents/bundle-agent\tcopilot\tsandbox_mode\tignored\ttarget does not support agent sandbox_mode",
        "agents/bundle-agent\tcursor\tcodex.mcp_servers\tignored\ttarget only supports codex.mcp_servers in Codex output",
        "agents/bundle-agent\tcursor\tcodex.skills.config\tignored\ttarget only supports codex.skills.config in Codex output",
        "agents/bundle-agent\tcursor\tnickname_candidates\tignored\ttarget does not support agent nickname_candidates",
        "agents/bundle-agent\tcursor\tsandbox_mode\tignored\ttarget does not support agent sandbox_mode",
        "agents/bundle-agent\topencode\tcodex.mcp_servers\tignored\ttarget only supports codex.mcp_servers in Codex output",
        "agents/bundle-agent\topencode\tcodex.skills.config\tignored\ttarget only supports codex.skills.config in Codex output",
        "agents/bundle-agent\topencode\tnickname_candidates\tignored\ttarget does not support agent nickname_candidates",
        "agents/bundle-agent\topencode\tsandbox_mode\tignored\ttarget does not support agent sandbox_mode",
        "rules/bundle-rule\tclaude\talways_apply\tignored\ttarget does not support rule always_apply semantics",
        "rules/bundle-rule\tclaude\tglobs\tignored\ttarget does not support rule globs",
        "rules/bundle-rule\tcodex\talways_apply\tignored\ttarget does not support rule always_apply semantics",
        "rules/bundle-rule\tcodex\tglobs\tignored\ttarget does not support rule globs",
        "rules/bundle-rule\tcopilot\talways_apply\tignored\ttarget does not support rule always_apply semantics",
        "rules/bundle-rule\tcopilot\tglobs\tignored\ttarget does not support rule globs",
        "rules/bundle-rule\topencode\talways_apply\tignored\ttarget does not support rule always_apply semantics",
        "rules/bundle-rule\topencode\tglobs\tignored\ttarget does not support rule globs",
    ]


def test_explain_lossiness_filters_by_app(
    minimal_shared_config: Path,
    core_root: Path,
    cli_runner,
) -> None:
    rule_dir = core_root / "rules" / "bundle-rule"
    rule_dir.mkdir(parents=True)
    (rule_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: rule\n"
        "description: Shared rule\n"
        "globs:\n"
        "  - '*.py'\n"
        "always_apply: true\n",
        encoding="utf-8",
    )
    (rule_dir / "prompt.md").write_text("Rule body.\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["explain-lossiness", "--app", "codex"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "resource_path\tapp\tproperty\tstatus\treason",
        "rules/bundle-rule\tcodex\talways_apply\tignored\ttarget does not support rule always_apply semantics",
        "rules/bundle-rule\tcodex\tglobs\tignored\ttarget does not support rule globs",
    ]


def test_explain_lossiness_reports_skill_tool_mappings(
    minimal_shared_config: Path,
    core_root: Path,
    cli_runner,
) -> None:
    skill_dir = core_root / "skills" / "reviewer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: skill\n"
        "name: reviewer\n"
        "tools:\n"
        "  write: true\n"
        "  mcp:\n"
        "    - server: github\n"
        "      tool: create_review\n",
        encoding="utf-8",
    )
    (skill_dir / "prompt.md").write_text("Review code.\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["explain-lossiness", "--app", "cursor"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "resource_path\tapp\tproperty\tstatus\treason",
        "skills/reviewer\tcursor\ttools.mcp\tignored\ttarget does not support per-skill MCP permissions",
        "skills/reviewer\tcursor\ttools.write\tignored\ttarget does not support per-skill write permissions",
    ]


def test_explain_lossiness_reports_copilot_skill_tool_mappings(
    minimal_shared_config: Path,
    core_root: Path,
    cli_runner,
) -> None:
    skill_dir = core_root / "skills" / "reviewer"
    skill_dir.mkdir(parents=True)
    (skill_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: skill\n"
        "name: reviewer\n"
        "tools:\n"
        "  write: true\n"
        "  mcp:\n"
        "    - server: github\n"
        "      tool: create_review\n",
        encoding="utf-8",
    )
    (skill_dir / "prompt.md").write_text("Review code.\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["explain-lossiness", "--app", "copilot"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "resource_path\tapp\tproperty\tstatus\treason",
        "skills/reviewer\tcopilot\ttools.mcp\tignored\ttarget does not support per-skill MCP permissions",
        "skills/reviewer\tcopilot\ttools.write\tignored\ttarget does not support per-skill write permissions",
    ]


def test_explain_lossiness_reports_mcp_env_file_mappings(
    minimal_shared_config: Path,
    core_root: Path,
    cli_runner,
) -> None:
    source = core_root / "config" / "mcp.base.json"
    source.write_text(
        '{"mcpServers": {"local": {"command": "npx", "envFile": ".env"}}}\n',
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["explain-lossiness"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "resource_path\tapp\tproperty\tstatus\treason",
        "config/mcp.base.json\tclaude\tmcpServers.local.envFile\tignored\ttarget does not support MCP envFile",
        "config/mcp.base.json\tcodex\tmcpServers.local.envFile\tignored\ttarget does not support MCP envFile",
        "config/mcp.base.json\tcopilot\tmcpServers.local.envFile\tignored\ttarget does not support MCP envFile",
        "config/mcp.base.json\topencode\tmcpServers.local.envFile\tignored\ttarget does not support MCP envFile",
    ]


def test_explain_lossiness_reports_codex_agent_tool_mappings(
    minimal_shared_config: Path,
    core_root: Path,
    cli_runner,
) -> None:
    agent_dir = core_root / "agents" / "reviewer"
    agent_dir.mkdir(parents=True)
    (agent_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: agent\n"
        "name: reviewer\n"
        "tools:\n"
        "  read: false\n"
        "  write: false\n"
        "  mcp:\n"
        "    - server: github\n"
        "      tool: create_review\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("Review code.\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["explain-lossiness", "--app", "codex"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "resource_path\tapp\tproperty\tstatus\treason",
        "agents/reviewer\tcodex\ttools.mcp\tignored\ttarget does not support agent MCP permissions",
        "agents/reviewer\tcodex\ttools.read\tignored\ttarget does not support agent read permissions",
        "agents/reviewer\tcodex\ttools.write\tignored\ttarget does not support agent write permissions",
    ]


def test_explain_lossiness_reports_cursor_agent_tool_mappings(
    minimal_shared_config: Path,
    core_root: Path,
    cli_runner,
) -> None:
    agent_dir = core_root / "agents" / "reviewer"
    agent_dir.mkdir(parents=True)
    (agent_dir / "meta.yaml").write_text(
        "spec_version: v1\n"
        "kind: agent\n"
        "name: reviewer\n"
        "reasoning_effort: high\n"
        "tools:\n"
        "  read: false\n"
        "  write: false\n"
        "  mcp:\n"
        "    - server: github\n"
        "      tool: create_review\n",
        encoding="utf-8",
    )
    (agent_dir / "prompt.md").write_text("Review code.\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["explain-lossiness", "--app", "cursor"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "resource_path\tapp\tproperty\tstatus\treason",
        "agents/reviewer\tcursor\treasoning_effort\tignored\ttarget does not support agent reasoning_effort",
        "agents/reviewer\tcursor\ttools.mcp\tignored\ttarget does not support agent MCP permissions",
        "agents/reviewer\tcursor\ttools.read\tignored\ttarget does not support agent read permissions",
    ]


def test_explain_lossiness_reports_workspace_paths(
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

    rule_dir = core_root / "workspaces" / "team" / "rules" / "bundle-rule"
    rule_dir.mkdir(parents=True)
    (rule_dir / "meta.yaml").write_text(
        "spec_version: v1\nkind: rule\ndescription: Shared rule\nglobs:\n  - '*.py'\n",
        encoding="utf-8",
    )
    (rule_dir / "prompt.md").write_text("Rule body.\n", encoding="utf-8")

    result = cli_runner.invoke(cli, ["explain-lossiness", "--workspace", "team"])

    assert result.exit_code == 0
    assert result.output.splitlines() == [
        "resource_path\tapp\tproperty\tstatus\treason",
        "workspaces/team/rules/bundle-rule\tclaude\tglobs\tignored\ttarget does not support rule globs",
        "workspaces/team/rules/bundle-rule\tcodex\tglobs\tignored\ttarget does not support rule globs",
        "workspaces/team/rules/bundle-rule\tcopilot\tglobs\tignored\ttarget does not support rule globs",
        "workspaces/team/rules/bundle-rule\topencode\tglobs\tignored\ttarget does not support rule globs",
    ]


def test_explain_lossiness_reports_when_no_documented_lossiness_exists(
    minimal_shared_config: Path,
    cli_runner,
) -> None:
    result = cli_runner.invoke(cli, ["explain-lossiness"])

    assert result.exit_code == 0
    assert result.output == "No lossy mappings found.\n"
