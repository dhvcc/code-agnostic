import json
from pathlib import Path

from code_agnostic.__main__ import cli
from code_agnostic.apps.common.models import MCPServerDTO, MCPServerType
from code_agnostic.apps.codex.config_repository import CodexConfigRepository
from code_agnostic.apps.codex.mapper import CodexMCPMapper
from code_agnostic.apps.codex.schema_repository import CodexSchemaRepository
from code_agnostic.apps.codex.service import CodexConfigService
from code_agnostic.models import ActionStatus

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


def _escape_toml_basic_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def test_apply_cursor_target_writes_only_cursor_config(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")

    result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])

    assert result.exit_code == 0
    assert (tmp_path / ".cursor" / "mcp.json").exists()
    assert not (tmp_path / ".config" / "opencode" / "opencode.json").exists()


def test_apply_target_does_not_show_plan_next_steps(
    minimal_shared_config: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")

    result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])

    assert result.exit_code == 0
    assert "Enable a target app" not in result.output
    assert "Review the planned changes" not in result.output


def test_apply_opencode_does_not_require_base_config(
    minimal_shared_config: Path, core_root: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    enable_app("opencode")
    (core_root / "config" / "opencode.base.json").unlink()

    result = cli_runner.invoke(cli, ["apply", "-a", "opencode"])

    assert result.exit_code == 0
    assert (tmp_path / ".config" / "opencode" / "opencode.json").exists()


def test_apply_syncs_git_excludes_for_target_workspace_app(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
    write_json,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git" / "info").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "myws", "--path", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    write_json(
        core_root / "workspaces" / "myws" / "git-exclude.json",
        {"include_defaults": True, "extra_patterns": ["*.generated"]},
    )
    ws_config = core_root / "workspaces" / "myws"
    (ws_config / "AGENTS.md").write_text("workspace rules\n", encoding="utf-8")
    write_json(
        ws_config / "mcp.base.json",
        {"mcpServers": {"demo": {"command": "uvx", "args": ["demo"]}}},
    )
    (ws_config / "skills" / "review").mkdir(parents=True)
    (ws_config / "skills" / "review" / "SKILL.md").write_text(
        "review\n", encoding="utf-8"
    )
    (ws_config / "agents").mkdir(parents=True)
    (ws_config / "agents" / "planner.md").write_text("plan\n", encoding="utf-8")
    enable_app("codex")
    enable_app("cursor")

    result = cli_runner.invoke(cli, ["apply", "-a", "codex", "--apply-excludes"])

    assert result.exit_code == 0
    content = set(
        (workspace_root / "repo-a" / ".git" / "info" / "exclude")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert ".codex/config.toml" in content
    assert ".codex/agents/planner.toml" in content
    assert ".agents/skills/review/SKILL.md" in content
    assert "AGENTS.override.md" in content
    assert "*.generated" in content
    assert "CLAUDE.md" not in content
    assert "AGENTS.md" not in content
    assert ".codex" not in content
    assert ".agents" not in content
    assert ".cursor" not in content


def test_apply_does_not_touch_git_excludes_without_flag(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
    write_json,
) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir()
    (workspace_root / "repo-a" / ".git" / "info").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "myws", "--path", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    write_json(
        core_root / "workspaces" / "myws" / "git-exclude.json",
        {"include_defaults": True, "extra_patterns": ["*.generated"]},
    )
    ws_config = core_root / "workspaces" / "myws"
    (ws_config / "AGENTS.md").write_text("workspace rules\n", encoding="utf-8")
    enable_app("codex")

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code == 0
    exclude_path = workspace_root / "repo-a" / ".git" / "info" / "exclude"
    assert not exclude_path.exists()


def test_apply_codex_target_writes_toml_config(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    enable_app("codex")

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code == 0
    codex_config = tmp_path / ".codex" / "config.toml"
    assert codex_config.exists()
    assert "[mcp_servers]" not in codex_config.read_text(encoding="utf-8")


def test_apply_copilot_target_writes_global_mcp_config(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("copilot")
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "local": {
                        "command": "uvx",
                        "args": ["tool"],
                        "env": {"TOKEN": "${TOKEN}"},
                        "timeout": 3000,
                    },
                    "remote": {
                        "url": "https://example.com/mcp",
                        "headers": {"Authorization": "Bearer ${API_KEY}"},
                        "timeout": 5000,
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "copilot"])

    assert result.exit_code == 0
    copilot_config = tmp_path / ".copilot" / "mcp-config.json"
    assert copilot_config.exists()
    payload = json.loads(copilot_config.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["local"] == {
        "tools": ["*"],
        "type": "local",
        "command": "uvx",
        "args": ["tool"],
        "env": {"TOKEN": "${TOKEN}"},
        "timeout": 3000,
    }
    assert payload["mcpServers"]["remote"] == {
        "tools": ["*"],
        "type": "http",
        "url": "https://example.com/mcp",
        "headers": {"Authorization": "Bearer ${API_KEY}"},
        "timeout": 5000,
    }
    assert not (tmp_path / ".copilot" / "mcp.json").exists()


def test_apply_still_rejects_invalid_existing_global_mcp_source(
    minimal_shared_config: Path, core_root: Path, cli_runner, enable_app
) -> None:
    enable_app("codex")
    (core_root / "config" / "mcp.base.json").write_text("{}", encoding="utf-8")

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code == 1
    assert "Invalid config schema" in result.output


def test_apply_codex_preserves_project_trust_settings(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    enable_app("codex")
    codex_path = tmp_path / ".codex" / "config.toml"
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    project_a = str(tmp_path / "repo-a")
    project_b = str(tmp_path / "repo-b")
    escaped_project_a = _escape_toml_basic_string(project_a)
    escaped_project_b = _escape_toml_basic_string(project_b)
    codex_path.write_text(
        "\n".join(
            [
                f'[projects."{escaped_project_a}"]',
                'trust_level = "trusted"',
                "",
                f'[projects."{escaped_project_b}"]',
                'trust_level = "trusted"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code == 0
    payload = tomllib.loads(codex_path.read_text(encoding="utf-8"))
    assert payload["projects"][project_a]["trust_level"] == "trusted"
    assert payload["projects"][project_b]["trust_level"] == "trusted"


def test_apply_codex_deep_merges_custom_config_tables(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("codex")
    codex_path = tmp_path / ".codex" / "config.toml"
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    project_a = str(tmp_path / "repo-a")
    project_b = str(tmp_path / "repo-b")
    escaped_project_a = _escape_toml_basic_string(project_a)
    escaped_project_b = _escape_toml_basic_string(project_b)
    codex_path.write_text(
        "\n".join(
            [
                f'[projects."{escaped_project_a}"]',
                'trust_level = "untrusted"',
                "",
                f'[projects."{escaped_project_b}"]',
                'trust_level = "trusted"',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (core_root / "config" / "codex.base.json").write_text(
        json.dumps(
            {
                "projects": {
                    project_a: {"trust_level": "trusted"},
                }
            }
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code == 0
    payload = tomllib.loads(codex_path.read_text(encoding="utf-8"))
    assert payload["projects"][project_a]["trust_level"] == "trusted"
    assert payload["projects"][project_b]["trust_level"] == "trusted"


def test_apply_codex_preserves_unmanaged_mcp_servers_when_syncing_managed_mcp(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("codex")
    codex_path = tmp_path / ".codex" / "config.toml"
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text(
        "\n".join(
            [
                "[mcp_servers.personal]",
                'command = "uvx"',
                'args = ["personal-tool"]',
                "",
                "[mcp_servers.managed]",
                'command = "uvx"',
                'args = ["old-managed-tool"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "managed": {"command": "uvx", "args": ["new-managed-tool"]}
                }
            }
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code == 0
    payload = tomllib.loads(codex_path.read_text(encoding="utf-8"))
    assert payload["mcp_servers"]["personal"] == {
        "command": "uvx",
        "args": ["personal-tool"],
    }
    assert payload["mcp_servers"]["managed"] == {
        "command": "uvx",
        "args": ["new-managed-tool"],
    }


def test_apply_codex_preserves_unmanaged_mcp_servers_when_no_mcp_is_synced(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("codex")
    codex_path = tmp_path / ".codex" / "config.toml"
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text(
        "\n".join(
            [
                "[mcp_servers.personal]",
                'command = "uvx"',
                'args = ["personal-tool"]',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code == 0
    payload = tomllib.loads(codex_path.read_text(encoding="utf-8"))
    assert payload["mcp_servers"]["personal"] == {
        "command": "uvx",
        "args": ["personal-tool"],
    }


def test_codex_mcp_plan_ignores_unmanaged_mcp_drift(tmp_path: Path) -> None:
    codex_path = tmp_path / ".codex" / "config.toml"
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text(
        "\n".join(
            [
                "[mcp_servers.personal]",
                'command = "uvx"',
                'args = ["personal-tool"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    service = CodexConfigService(
        repository=CodexConfigRepository(root=tmp_path / ".codex"),
        mapper=CodexMCPMapper(),
        schema_repository=CodexSchemaRepository(),
    )

    action = service.build_action(common_servers={})

    assert action.status == ActionStatus.NOOP
    payload = tomllib.loads(action.payload)
    assert payload["mcp_servers"]["personal"] == {
        "command": "uvx",
        "args": ["personal-tool"],
    }


def test_codex_mcp_plan_updates_only_same_named_managed_mcp(
    tmp_path: Path,
) -> None:
    codex_path = tmp_path / ".codex" / "config.toml"
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text(
        "\n".join(
            [
                "[mcp_servers.personal]",
                'command = "uvx"',
                'args = ["personal-tool"]',
                "",
                "[mcp_servers.managed]",
                'command = "uvx"',
                'args = ["old-managed-tool"]',
                "",
            ]
        ),
        encoding="utf-8",
    )
    service = CodexConfigService(
        repository=CodexConfigRepository(root=tmp_path / ".codex"),
        mapper=CodexMCPMapper(),
        schema_repository=CodexSchemaRepository(),
    )

    action = service.build_action(
        common_servers={
            "managed": MCPServerDTO(
                name="managed",
                type=MCPServerType.STDIO,
                command="uvx",
                args=["new-managed-tool"],
            )
        }
    )

    assert action.status == ActionStatus.UPDATE
    payload = tomllib.loads(action.payload)
    assert payload["mcp_servers"]["personal"] == {
        "command": "uvx",
        "args": ["personal-tool"],
    }
    assert payload["mcp_servers"]["managed"] == {
        "command": "uvx",
        "args": ["new-managed-tool"],
    }


def test_apply_all_with_cursor_and_codex_writes_both(
    minimal_shared_config: Path, tmp_path: Path, cli_runner, enable_app
) -> None:
    enable_app("cursor")
    enable_app("codex")

    result = cli_runner.invoke(cli, ["apply", "-a", "all"])

    assert result.exit_code == 0
    cursor_payload = json.loads(
        (tmp_path / ".cursor" / "mcp.json").read_text(encoding="utf-8")
    )
    assert "mcpServers" in cursor_payload
    assert (tmp_path / ".codex" / "config.toml").exists()


def test_apply_all_preserves_mcp_timeout_for_generated_app_configs(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")
    enable_app("codex")
    enable_app("opencode")
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "demo": {
                        "command": "uvx",
                        "args": ["tool"],
                        "timeout": 900000,
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "all"])

    assert result.exit_code == 0
    cursor_payload = json.loads(
        (tmp_path / ".cursor" / "mcp.json").read_text(encoding="utf-8")
    )
    opencode_payload = json.loads(
        (tmp_path / ".config" / "opencode" / "opencode.json").read_text(
            encoding="utf-8"
        )
    )
    codex_payload = tomllib.loads(
        (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    )
    assert cursor_payload["mcpServers"]["demo"]["timeout"] == 900000
    assert opencode_payload["mcp"]["demo"]["timeout"] == 900000
    assert codex_payload["mcp_servers"]["demo"]["tool_timeout_sec"] == 900.0


def test_apply_all_respects_targeted_mcp_server_keys(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")
    enable_app("codex")
    enable_app("opencode")
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "@opencode-playwright": {"command": "npx", "args": ["playwright"]},
                    "!codex-shared": {"url": "https://example.com/mcp"},
                    "all-apps": {"command": "uvx", "args": ["demo"]},
                }
            }
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "all"])

    assert result.exit_code == 0
    cursor_payload = json.loads(
        (tmp_path / ".cursor" / "mcp.json").read_text(encoding="utf-8")
    )
    opencode_payload = json.loads(
        (tmp_path / ".config" / "opencode" / "opencode.json").read_text(
            encoding="utf-8"
        )
    )
    codex_payload = tomllib.loads(
        (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    )

    assert set(cursor_payload["mcpServers"]) == {"shared", "all-apps"}
    assert set(opencode_payload["mcp"]) == {"playwright", "shared", "all-apps"}
    assert set(codex_payload["mcp_servers"]) == {"all-apps"}


def test_apply_cursor_target_does_not_apply_workspace_links(
    minimal_shared_config: Path,
    tmp_path: Path,
    core_root: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli,
        [
            "workspaces",
            "add",
            "--name",
            "workspace-example",
            "--path",
            str(workspace_root),
        ],
    )
    assert add_result.exit_code == 0

    # Create workspace config with rules in rules/ directory
    ws_config_dir = core_root / "workspaces" / "workspace-example"
    (ws_config_dir / "rules").mkdir(parents=True, exist_ok=True)
    (ws_config_dir / "rules" / "shared.md").write_text("rules", encoding="utf-8")

    apply_result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])
    assert apply_result.exit_code == 0

    repo_rules_link = workspace_root / "service-a" / ".cursor" / "rules"
    assert not repo_rules_link.exists()


def test_apply_cursor_writes_workspace_mcp_json(
    minimal_shared_config: Path,
    tmp_path: Path,
    core_root: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

    assert (
        cli_runner.invoke(
            cli,
            [
                "workspaces",
                "add",
                "--name",
                "workspace-example",
                "--path",
                str(workspace_root),
            ],
        ).exit_code
        == 0
    )

    ws_config_dir = core_root / "workspaces" / "workspace-example"
    (ws_config_dir / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "ws-only": {"url": "https://ws.example.com/mcp"},
                }
            }
        ),
        encoding="utf-8",
    )

    apply_result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])
    assert apply_result.exit_code == 0

    mcp_path = workspace_root / ".cursor" / "mcp.json"
    assert (
        json.loads(mcp_path.read_text(encoding="utf-8"))["mcpServers"]["ws-only"]["url"]
        == "https://ws.example.com/mcp"
    )
    sub_mcp = workspace_root / "service-a" / ".cursor" / "mcp.json"
    assert (
        json.loads(sub_mcp.read_text(encoding="utf-8"))["mcpServers"]["ws-only"]["url"]
        == "https://ws.example.com/mcp"
    )


def test_apply_cursor_writes_subrepo_mcp_json(
    minimal_shared_config: Path,
    tmp_path: Path,
    core_root: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

    assert (
        cli_runner.invoke(
            cli,
            [
                "workspaces",
                "add",
                "--name",
                "workspace-example",
                "--path",
                str(workspace_root),
            ],
        ).exit_code
        == 0
    )

    ws_config_dir = core_root / "workspaces" / "workspace-example"
    (ws_config_dir / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "ws-only": {"url": "https://ws.example.com/mcp"},
                }
            }
        ),
        encoding="utf-8",
    )

    apply_result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])
    assert apply_result.exit_code == 0

    sub_mcp = workspace_root / "service-a" / ".cursor" / "mcp.json"
    assert (
        json.loads(sub_mcp.read_text(encoding="utf-8"))["mcpServers"]["ws-only"]["url"]
        == "https://ws.example.com/mcp"
    )


def test_apply_copilot_writes_workspace_and_repo_github_mcp_json(
    minimal_shared_config: Path,
    tmp_path: Path,
    core_root: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("copilot")

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / "service-a" / ".git" / "info").mkdir(parents=True)

    add_result = cli_runner.invoke(
        cli,
        [
            "workspaces",
            "add",
            "--name",
            "workspace-example",
            "--path",
            str(workspace_root),
        ],
    )
    assert add_result.exit_code == 0

    ws_config_dir = core_root / "workspaces" / "workspace-example"
    (ws_config_dir / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "ws-only": {"url": "https://ws.example.com/mcp"},
                }
            }
        ),
        encoding="utf-8",
    )

    apply_result = cli_runner.invoke(
        cli, ["apply", "-a", "copilot", "--apply-excludes"]
    )

    assert apply_result.exit_code == 0
    workspace_mcp = workspace_root / ".github" / "mcp.json"
    repo_mcp = workspace_root / "service-a" / ".github" / "mcp.json"
    assert (
        json.loads(workspace_mcp.read_text(encoding="utf-8"))["mcpServers"]["ws-only"][
            "url"
        ]
        == "https://ws.example.com/mcp"
    )
    assert (
        json.loads(repo_mcp.read_text(encoding="utf-8"))["mcpServers"]["ws-only"]["url"]
        == "https://ws.example.com/mcp"
    )
    assert not (workspace_root / ".mcp.json").exists()
    assert not (workspace_root / "service-a" / ".mcp.json").exists()
    exclude = workspace_root / "service-a" / ".git" / "info" / "exclude"
    assert ".github/mcp.json" in exclude.read_text(encoding="utf-8").splitlines()


def test_apply_copilot_writes_project_github_mcp_json(
    minimal_shared_config: Path,
    tmp_path: Path,
    core_root: Path,
    cli_runner,
    enable_app,
    write_json,
) -> None:
    enable_app("copilot")
    project_root = tmp_path / "service-api"
    project_root.mkdir()
    write_json(
        core_root / "config" / "projects.json",
        [{"name": "service-api", "path": str(project_root)}],
    )
    write_json(
        core_root / "projects" / "service-api" / "mcp.base.json",
        {"mcpServers": {"project-only": {"command": "uvx", "args": ["project"]}}},
    )

    apply_result = cli_runner.invoke(cli, ["apply", "-a", "copilot"])

    assert apply_result.exit_code == 0
    project_mcp = project_root / ".github" / "mcp.json"
    payload = json.loads(project_mcp.read_text(encoding="utf-8"))
    assert payload["mcpServers"]["project-only"] == {
        "tools": ["*"],
        "type": "local",
        "command": "uvx",
        "args": ["project"],
    }
    assert not (project_root / ".mcp.json").exists()


def test_apply_cursor_does_not_write_workspace_mcp_from_global_config_only(
    minimal_shared_config: Path,
    tmp_path: Path,
    core_root: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")

    workspace_root = tmp_path / "microservice-workspace"
    workspace_root.mkdir()
    (workspace_root / "service-a" / ".git").mkdir(parents=True)

    assert (
        cli_runner.invoke(
            cli,
            [
                "workspaces",
                "add",
                "--name",
                "workspace-example",
                "--path",
                str(workspace_root),
            ],
        ).exit_code
        == 0
    )

    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "global-only": {"command": "npx", "args": ["-y", "global-server"]},
                }
            }
        ),
        encoding="utf-8",
    )

    apply_result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])
    assert apply_result.exit_code == 0

    assert (tmp_path / ".cursor" / "mcp.json").is_file()
    assert not (workspace_root / ".cursor" / "mcp.json").exists()
    assert not (workspace_root / "service-a" / ".cursor" / "mcp.json").exists()


def test_apply_cursor_aborts_on_invalid_cursor_json(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")
    cursor_path = tmp_path / ".cursor" / "mcp.json"
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text("{oops", encoding="utf-8")

    result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])

    assert result.exit_code != 0
    assert "Apply aborted" in result.output
    assert "Invalid JSON format" in result.output


def test_apply_codex_aborts_on_invalid_toml(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("codex")
    codex_path = tmp_path / ".codex" / "config.toml"
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text("[mcp_servers.demo\nurl='x'", encoding="utf-8")

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code != 0
    assert "Apply aborted" in result.output


def test_apply_opencode_deep_merges_permission_config(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("opencode")
    opencode_path = tmp_path / ".config" / "opencode" / "opencode.json"
    opencode_path.parent.mkdir(parents=True, exist_ok=True)
    opencode_path.write_text(
        json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "permission": {
                    "read": "allow",
                    "glob": {"**/*.secret": "deny"},
                },
            }
        ),
        encoding="utf-8",
    )
    (core_root / "config" / "opencode.base.json").write_text(
        json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "permission": {"edit": "deny"},
            }
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "opencode"])

    assert result.exit_code == 0
    payload = json.loads(opencode_path.read_text(encoding="utf-8"))
    assert payload["permission"]["read"] == "allow"
    assert payload["permission"]["edit"] == "deny"
    assert payload["permission"]["glob"] == {"**/*.secret": "deny"}


def test_apply_opencode_legacy_permission_migration_preserves_existing_permission(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("opencode")
    opencode_path = tmp_path / ".config" / "opencode" / "opencode.json"
    opencode_path.parent.mkdir(parents=True, exist_ok=True)
    opencode_path.write_text(
        json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "permission": {"*": "allow"},
            }
        ),
        encoding="utf-8",
    )
    (core_root / "config" / "opencode.base.json").write_text(
        json.dumps(
            {
                "$schema": "https://opencode.ai/config.json",
                "permission": [
                    {"permission": "bash", "action": "allow"},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "opencode"])

    assert result.exit_code == 0
    payload = json.loads(opencode_path.read_text(encoding="utf-8"))
    assert payload["permission"] == {"*": "allow"}
    assert payload["tools"]["bash"] is True


def test_apply_cursor_aborts_on_invalid_schema_key(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("cursor")
    cursor_path = tmp_path / ".cursor" / "mcp.json"
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "broken": {"url": "https://example.com/mcp", "badKey": True}
                }
            }
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "cursor"])

    assert result.exit_code != 0
    assert "Invalid config schema" in result.output


def test_apply_codex_aborts_on_invalid_schema_key(
    minimal_shared_config: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("codex")
    codex_path = tmp_path / ".codex" / "config.toml"
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    codex_path.write_text(
        "\n".join(
            [
                "[mcp_servers.demo]",
                'url = "https://example.com/mcp"',
                'bad_key = "boom"',
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "codex"])

    assert result.exit_code != 0
    assert "Invalid config schema" in result.output


def test_apply_copilot_target_writes_global_mcp_skills_and_agents(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
) -> None:
    enable_app("copilot")
    (core_root / "config" / "mcp.base.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "playwright": {
                        "command": "npx",
                        "args": ["@playwright/mcp@latest"],
                        "env": {"TOKEN": "$COPILOT_MCP_TOKEN"},
                    },
                    "context7": {
                        "url": "https://mcp.context7.com/mcp",
                        "headers": {"Authorization": "Bearer $COPILOT_MCP_TOKEN"},
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    (core_root / "skills" / "review").mkdir(parents=True)
    (core_root / "skills" / "review" / "SKILL.md").write_text(
        "---\nname: review\ndescription: Review code\n---\n\nReview.\n",
        encoding="utf-8",
    )
    (core_root / "agents").mkdir(parents=True)
    (core_root / "agents" / "planner.agent.md").write_text(
        "---\nname: planner\ndescription: Plan work\n---\n\nPlan.\n",
        encoding="utf-8",
    )

    result = cli_runner.invoke(cli, ["apply", "-a", "copilot"])

    assert result.exit_code == 0
    config = json.loads((tmp_path / ".copilot" / "mcp-config.json").read_text())
    assert config["mcpServers"]["playwright"] == {
        "tools": ["*"],
        "type": "local",
        "command": "npx",
        "args": ["@playwright/mcp@latest"],
        "env": {"TOKEN": "$COPILOT_MCP_TOKEN"},
    }
    assert config["mcpServers"]["context7"] == {
        "tools": ["*"],
        "type": "http",
        "url": "https://mcp.context7.com/mcp",
        "headers": {"Authorization": "Bearer $COPILOT_MCP_TOKEN"},
    }
    assert (tmp_path / ".copilot" / "skills" / "review" / "SKILL.md").exists()
    assert (tmp_path / ".copilot" / "agents" / "planner.agent.md").exists()
    assert not (tmp_path / ".copilot" / "agents" / "planner.agent.agent.md").exists()


def test_apply_copilot_workspace_writes_repo_github_artifacts(
    minimal_shared_config: Path,
    core_root: Path,
    tmp_path: Path,
    cli_runner,
    enable_app,
    write_json,
) -> None:
    workspace_root = tmp_path / "workspace"
    repo = workspace_root / "repo-a"
    (repo / ".git" / "info").mkdir(parents=True)
    add_result = cli_runner.invoke(
        cli, ["workspaces", "add", "--name", "myws", "--path", str(workspace_root)]
    )
    assert add_result.exit_code == 0

    ws_config = core_root / "workspaces" / "myws"
    write_json(
        ws_config / "mcp.base.json",
        {"mcpServers": {"demo": {"command": "uvx", "args": ["demo"]}}},
    )
    (ws_config / "skills" / "review").mkdir(parents=True)
    (ws_config / "skills" / "review" / "SKILL.md").write_text(
        "---\nname: review\ndescription: Review code\n---\n\nReview.\n",
        encoding="utf-8",
    )
    (ws_config / "agents").mkdir(parents=True)
    (ws_config / "agents" / "planner.agent.md").write_text(
        "---\nname: planner\ndescription: Plan work\n---\n\nPlan.\n",
        encoding="utf-8",
    )
    enable_app("copilot")

    result = cli_runner.invoke(cli, ["apply", "-a", "copilot", "--apply-excludes"])

    assert result.exit_code == 0
    assert (repo / ".github" / "mcp.json").exists()
    assert (repo / ".github" / "skills" / "review" / "SKILL.md").exists()
    assert (repo / ".github" / "agents" / "planner.agent.md").exists()
    assert not (repo / ".github" / "agents" / "planner.agent.agent.md").exists()
    exclude = (repo / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert ".github/mcp.json" in exclude
    assert ".github/skills/review/SKILL.md" in exclude
    assert ".github/agents/planner.agent.md" in exclude
    assert ".github/agents/planner.agent.agent.md" not in exclude
