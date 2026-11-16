"""Enumeration types for Anonymous-Prover."""

from enum import StrEnum


class ExperimentMode(StrEnum):
    """The type of sorry to fill: code, proof, or both."""
    code = "code"
    proof = "proof"
    auto = "auto"


class SkillsConfig(StrEnum):
    """Which workspace template / skills to expose to the agent."""
    none = "none"
    standard = "standard"
    extended = "extended"
    co_derivation = "co_derivation"
    docs_only = "docs_only"
    tools_only = "tools_only"


class AgentType(StrEnum):
    """Supported AI agent backends."""
    claude_code = "claude-code"
    codex = "codex"


class TaskStatus(StrEnum):
    """Status of an individual task within an experiment."""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    timeout = "timeout"


class ExperimentStatus(StrEnum):
    """Status of an experiment run."""
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"


class StreamFormat(StrEnum):
    """Output format for agent stream capture."""
    stream_json = "stream_json"
    text = "text"
