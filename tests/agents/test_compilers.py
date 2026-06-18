"""Tests for agent compilers."""

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

import yaml
import pytest

from code_agnostic.agents.compilers import (
    ClaudeAgentCompiler,
    CodexAgentCompiler,
    CopilotAgentCompiler,
    CursorAgentCompiler,
    OpenCodeAgentCompiler,
)
from code_agnostic.agents.models import (
    Agent,
    AgentCodexConfig,
    AgentMetadata,
    AgentSkillConfig,
    AgentToolPermissions,
)
from code_agnostic.agents.parser import parse_agent
from code_agnostic.errors import InvalidConfigSchemaError


def _make_agent(
    name: str = "test-agent",
    description: str = "Test agent",
    model: str = "claude-sonnet-4-20250514",
    content: str = "Agent body.\n",
    app_overrides: dict[str, dict[str, object]] | None = None,
    tools: AgentToolPermissions | None = None,
) -> Agent:
    return Agent(
        name=name,
        source_path=Path(f"/fake/{name}.md"),
        metadata=AgentMetadata(
            name=name,
            description=description,
            model=model,
            model_reasoning_effort="medium",
            sandbox_mode="read-only",
            nickname_candidates=["Atlas", "Echo"],
            tools=tools or AgentToolPermissions(read=True, write=True),
            app_overrides=app_overrides or {},
            codex=AgentCodexConfig(
                mcp_servers={
                    "openaiDeveloperDocs": {"url": "https://developers.openai.com/mcp"}
                },
                skills_config=[
                    AgentSkillConfig(path="/tmp/docs/SKILL.md", enabled=False)
                ],
            ),
        ),
        content=content,
    )


def test_opencode_compiler() -> None:
    agent = _make_agent()
    compiler = OpenCodeAgentCompiler()
    result = compiler.compile(agent)
    raw, body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)
    assert payload["name"] == "test-agent"
    assert payload["description"] == "Test agent"
    assert payload["model"] == "claude-sonnet-4-20250514"
    assert payload["reasoningEffort"] == "medium"
    assert payload["permission"] == {"read": "allow", "edit": "allow"}
    assert "model_reasoning_effort" not in payload
    assert body.strip() == "Agent body."


def test_opencode_compiler_rejects_missing_description() -> None:
    agent = _make_agent(description="")

    compiler = OpenCodeAgentCompiler()
    with pytest.raises(
        InvalidConfigSchemaError, match="OpenCode agents require a description"
    ):
        compiler.compile(agent)


def test_opencode_compiler_uses_app_override_and_passthrough() -> None:
    agent = _make_agent(
        model="gpt-5.4-mini",
        app_overrides={
            "opencode": {
                "model": "opencode/big-pickle",
                "temperature": 0.2,
                "variant": "large-context",
            }
        },
    )

    compiler = OpenCodeAgentCompiler()
    result = compiler.compile(agent)
    raw, _body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload["model"] == "opencode/big-pickle"
    assert payload["temperature"] == 0.2
    assert payload["variant"] == "large-context"


def test_opencode_compiler_uses_permission_config_for_tools() -> None:
    agent = _make_agent(
        tools=AgentToolPermissions(
            read=False,
            write=False,
            mcp=[
                {"server": "github", "tool": "create_pr"},
                {"server": "docs"},
            ],
        ),
    )

    compiler = OpenCodeAgentCompiler()
    result = compiler.compile(agent)
    raw, _body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload["permission"] == {
        "read": "deny",
        "edit": "deny",
        "github_create_pr": "allow",
        "docs_*": "allow",
    }
    assert "tools" not in payload


def test_opencode_compiler_merges_explicit_permission_override() -> None:
    agent = _make_agent(
        app_overrides={
            "opencode": {
                "permission": {
                    "edit": "ask",
                    "bash": {"*": "ask", "git diff": "allow"},
                    "glob": "deny",
                    "github_*": "deny",
                }
            }
        },
        tools=AgentToolPermissions(
            read=False,
            write=True,
            mcp=[{"server": "github"}, {"server": "docs", "tool": "search"}],
        ),
    )

    compiler = OpenCodeAgentCompiler()
    result = compiler.compile(agent)
    raw, _body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload["permission"] == {
        "read": "deny",
        "edit": "ask",
        "github_*": "deny",
        "docs_search": "allow",
        "bash": {"*": "ask", "git diff": "allow"},
        "glob": "deny",
    }


def test_cursor_compiler_uses_current_frontmatter() -> None:
    agent = _make_agent(tools=AgentToolPermissions(read=False, write=False))
    compiler = CursorAgentCompiler()
    result = compiler.compile(agent)
    raw, body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload == {
        "name": "test-agent",
        "description": "Test agent",
        "model": "claude-sonnet-4-20250514",
        "readonly": True,
    }
    assert body.strip() == "Agent body."


def test_cursor_compiler_uses_supported_app_overrides() -> None:
    agent = _make_agent(
        model="gpt-5.4-mini",
        app_overrides={
            "cursor": {
                "name": "cursor-reviewer",
                "description": "Cursor-specific reviewer",
                "model": "inherit",
                "is_background": True,
                "readonly": False,
            }
        },
        tools=AgentToolPermissions(read=True, write=False),
    )

    compiler = CursorAgentCompiler()
    result = compiler.compile(agent)
    raw, _body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload["name"] == "cursor-reviewer"
    assert payload["description"] == "Cursor-specific reviewer"
    assert payload["model"] == "inherit"
    assert payload["is_background"] is True
    assert payload["readonly"] is False


def test_cursor_compiler_rejects_unsupported_app_override() -> None:
    agent = _make_agent(app_overrides={"cursor": {"permission": "ask"}})

    with pytest.raises(InvalidConfigSchemaError) as exc_info:
        CursorAgentCompiler().compile(agent)

    assert "x-cursor.permission is not supported" in exc_info.value.detail


def test_cursor_compiler_does_not_leak_other_app_overrides() -> None:
    agent = _make_agent(
        app_overrides={"opencode": {"model": "opencode/big-pickle", "temperature": 0.2}}
    )

    compiler = CursorAgentCompiler()
    result = compiler.compile(agent)

    assert "opencode-model" not in result
    assert "opencode-temperature" not in result


def test_codex_compiler() -> None:
    agent = _make_agent()
    compiler = CodexAgentCompiler()
    result = compiler.compile(agent)
    payload = tomllib.loads(result)
    assert payload["name"] == "test-agent"
    assert payload["description"] == "Test agent"
    assert payload["developer_instructions"] == "Agent body.\n"
    assert payload["model_reasoning_effort"] == "medium"
    assert payload["sandbox_mode"] == "read-only"
    assert payload["nickname_candidates"] == ["Atlas", "Echo"]
    assert payload["mcp_servers"]["openaiDeveloperDocs"]["url"] == (
        "https://developers.openai.com/mcp"
    )
    assert payload["skills"]["config"] == [
        {"path": "/tmp/docs/SKILL.md", "enabled": False}
    ]


def test_codex_compiler_uses_generic_model_when_other_app_overrides_exist() -> None:
    agent = _make_agent(
        model="gpt-5.4-mini",
        app_overrides={
            "opencode": {"model": "opencode/big-pickle", "temperature": 0.2}
        },
    )

    compiler = CodexAgentCompiler()
    result = compiler.compile(agent)
    payload = tomllib.loads(result)

    assert payload["model"] == "gpt-5.4-mini"
    assert "temperature" not in payload


def test_copilot_compiler_outputs_custom_agent_markdown() -> None:
    agent = _make_agent(
        model="gpt-5.4-mini",
        tools=AgentToolPermissions(
            read=True,
            write=False,
            mcp=[
                {"server": "github", "tool": "list_issues"},
                {"server": "playwright"},
            ],
        ),
    )

    result = CopilotAgentCompiler().compile(agent)
    raw, body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload == {
        "name": "test-agent",
        "description": "Test agent",
        "model": "gpt-5.4-mini",
        "tools": ["read", "github/list_issues", "playwright/*"],
    }
    assert body.strip() == "Agent body."


def test_copilot_compiler_omits_default_tools() -> None:
    agent = _make_agent(tools=AgentToolPermissions(read=True, write=True))

    result = CopilotAgentCompiler().compile(agent)
    raw, _body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert "tools" not in payload


def test_copilot_compiler_rejects_unsupported_app_override() -> None:
    agent = _make_agent(app_overrides={"copilot": {"handoffs": ["reviewer"]}})

    with pytest.raises(InvalidConfigSchemaError) as exc_info:
        CopilotAgentCompiler().compile(agent)

    assert "x-copilot.handoffs is not supported" in exc_info.value.detail


def test_copilot_compiler_rejects_native_tools_override() -> None:
    agent = _make_agent(app_overrides={"copilot": {"tools": ["shell"]}})

    with pytest.raises(InvalidConfigSchemaError) as exc_info:
        CopilotAgentCompiler().compile(agent)

    assert "x-copilot.tools is not supported" in exc_info.value.detail


def test_copilot_compiler_rejects_mcp_tool_without_server() -> None:
    agent = _make_agent(
        tools=AgentToolPermissions(
            read=True,
            write=False,
            mcp=[{"tool": "search"}],
        )
    )

    with pytest.raises(InvalidConfigSchemaError) as exc_info:
        CopilotAgentCompiler().compile(agent)

    assert "Copilot agent MCP tools require a server" in exc_info.value.detail


def test_copilot_compiler_uses_legacy_flat_model_override(tmp_path: Path) -> None:
    (tmp_path / "reviewer.md").write_text(
        "---\n"
        "name: reviewer\n"
        "description: Review code\n"
        "model: gpt-5.4-mini\n"
        "copilot-model: gpt-5.4\n"
        "---\n"
        "\n"
        "Review carefully.\n",
        encoding="utf-8",
    )

    result = CopilotAgentCompiler().compile(parse_agent(tmp_path / "reviewer.md"))
    raw, _body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload["model"] == "gpt-5.4"


def test_claude_compiler_outputs_markdown_subagent() -> None:
    agent = _make_agent(
        app_overrides={
            "claude": {
                "permissionMode": "plan",
                "color": "blue",
                "skills": ["review-pr"],
            }
        },
    )

    result = ClaudeAgentCompiler().compile(agent)
    raw, body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload["name"] == "test-agent"
    assert payload["description"] == "Test agent"
    assert payload["model"] == "claude-sonnet-4-20250514"
    assert payload["effort"] == "medium"
    assert payload["permissionMode"] == "plan"
    assert payload["color"] == "blue"
    assert payload["skills"] == ["review-pr"]
    assert body.strip() == "Agent body."


def test_copilot_compiler_emits_agent_profile_frontmatter() -> None:
    agent = _make_agent(
        tools=AgentToolPermissions(
            read=False,
            write=False,
            mcp=[
                {"server": "github"},
                {"server": "playwright", "tool": "browser_snapshot"},
            ],
        ),
        app_overrides={
            "copilot": {
                "target": "github-copilot",
                "disable-model-invocation": True,
            }
        },
    )

    result = CopilotAgentCompiler().compile(agent)
    raw, body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload == {
        "name": "test-agent",
        "description": "Test agent",
        "model": "claude-sonnet-4-20250514",
        "tools": ["github/*", "playwright/browser_snapshot"],
        "disable-model-invocation": True,
        "target": "github-copilot",
    }
    assert body.strip() == "Agent body."


def test_copilot_compiler_rejects_unsupported_agent_overrides() -> None:
    agent = _make_agent(app_overrides={"copilot": {"argument-hint": "ticket"}})

    with pytest.raises(InvalidConfigSchemaError) as exc_info:
        CopilotAgentCompiler().compile(agent)

    assert "x-copilot.argument-hint is not supported" in exc_info.value.detail
