"""Tests for agent compilers."""

from pathlib import Path

from code_agnostic.agents.compilers import (
    CodexAgentCompiler,
    CursorAgentCompiler,
    OpenCodeAgentCompiler,
)
from code_agnostic.agents.models import Agent, AgentMetadata, AgentToolPermissions


def _make_agent(
    name: str = "test-agent",
    description: str = "Test agent",
    model: str = "claude-sonnet-4-20250514",
    content: str = "Agent body.\n",
) -> Agent:
    return Agent(
        name=name,
        source_path=Path(f"/fake/{name}.md"),
        metadata=AgentMetadata(
            name=name,
            description=description,
            model=model,
            tools=AgentToolPermissions(read=True, write=True),
        ),
        content=content,
    )


def test_opencode_compiler() -> None:
    agent = _make_agent()
    compiler = OpenCodeAgentCompiler()
    result = compiler.compile(agent)
    assert "test-agent" in result
    assert "Test agent" in result
    assert "Agent body." in result


def test_cursor_compiler() -> None:
    agent = _make_agent()
    compiler = CursorAgentCompiler()
    result = compiler.compile(agent)
    assert "test-agent" in result
    assert "Agent body." in result


def test_codex_compiler() -> None:
    agent = _make_agent()
    compiler = CodexAgentCompiler()
    result = compiler.compile(agent)
    assert "test-agent" in result
    assert "Agent body." in result
