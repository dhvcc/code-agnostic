"""Tests for agent compilers."""

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

import yaml

from code_agnostic.agents.compilers import (
    CodexAgentCompiler,
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


def _make_agent(
    name: str = "test-agent",
    description: str = "Test agent",
    model: str = "claude-sonnet-4-20250514",
    content: str = "Agent body.\n",
    app_overrides: dict[str, dict[str, object]] | None = None,
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
            tools=AgentToolPermissions(read=True, write=True),
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
    assert "model_reasoning_effort" not in payload
    assert body.strip() == "Agent body."


def test_opencode_compiler_uses_app_override_and_passthrough() -> None:
    agent = _make_agent(
        model="gpt-5.4-mini",
        app_overrides={
            "opencode": {"model": "opencode/big-pickle", "temperature": 0.2}
        },
    )

    compiler = OpenCodeAgentCompiler()
    result = compiler.compile(agent)
    raw, _body = result.split("---\n", 2)[1:]
    payload = yaml.safe_load(raw)

    assert payload["model"] == "opencode/big-pickle"
    assert payload["temperature"] == 0.2


def test_cursor_compiler() -> None:
    agent = _make_agent()
    compiler = CursorAgentCompiler()
    result = compiler.compile(agent)
    assert "test-agent" in result
    assert "Agent body." in result


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
