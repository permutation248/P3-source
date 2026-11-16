"""Paths and checks for agent subscription (OAuth) credential files.

Centralised so route handlers, runtime validators, and Docker mount logic
all agree on where the credential files live.
"""

from __future__ import annotations

import os

from .enums import AgentType

# Host-side credential paths, relative to the user's home directory.
_HOST_RELATIVE_PATHS: dict[AgentType, str] = {
    AgentType.claude_code: os.path.join(".claude", ".credentials.json"),
    AgentType.codex: os.path.join(".codex", "auth.json"),
}

# Container-side mount targets, for Docker `-v host:container` lines.
_CONTAINER_PATHS: dict[AgentType, str] = {
    AgentType.claude_code: "/home/solver/.claude/.credentials.json",
    AgentType.codex: "/home/solver/.codex/auth.json",
}


def oauth_host_path(agent_type: AgentType) -> str:
    """Absolute host path where the subscription credential file lives."""
    return os.path.join(os.path.expanduser("~"), _HOST_RELATIVE_PATHS[agent_type])


def oauth_container_path(agent_type: AgentType) -> str:
    """Absolute path inside the agent container where the file is mounted."""
    return _CONTAINER_PATHS[agent_type]


def oauth_available(agent_type: AgentType) -> bool:
    """True iff the subscription credential file for *agent_type* is present."""
    return os.path.isfile(oauth_host_path(agent_type))


def oauth_display_path(agent_type: AgentType) -> str:
    """``~`` -form path for user-facing error messages."""
    return "~/" + _HOST_RELATIVE_PATHS[agent_type].replace(os.sep, "/")
