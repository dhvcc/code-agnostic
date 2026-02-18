"""Per-editor agent compilers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from code_agnostic.agents.models import Agent
from code_agnostic.agents.parser import serialize_agent


class IAgentCompiler(ABC):
    @abstractmethod
    def compile(self, agent: Agent) -> str:
        """Return compiled agent content for target editor."""


class OpenCodeAgentCompiler(IAgentCompiler):
    """Near-identity: OpenCode agent format IS the canonical format."""

    def compile(self, agent: Agent) -> str:
        return serialize_agent(agent)


class CursorAgentCompiler(IAgentCompiler):
    """Cross-compile for Cursor."""

    def compile(self, agent: Agent) -> str:
        return serialize_agent(agent)


class CodexAgentCompiler(IAgentCompiler):
    """Cross-compile for Codex. Codex doesn't support agents natively."""

    def compile(self, agent: Agent) -> str:
        return serialize_agent(agent)
