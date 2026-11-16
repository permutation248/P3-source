"""Agent factory -- instantiate agents by AgentType."""

from __future__ import annotations

from ..core.enums import AgentType
from .claude import ClaudeAgent
from .codex import CodexAgent

_REGISTRY = {
    AgentType.claude_code: ClaudeAgent,
    AgentType.codex: CodexAgent,
}


def create_agent(agent_type: AgentType, **kwargs):
    """Create an agent instance for the given *agent_type*."""
    cls = _REGISTRY.get(agent_type)
    if cls is None:
        raise ValueError(f"Unknown agent type: {agent_type!r}")
    return cls(**kwargs)
