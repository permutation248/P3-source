"""API routes for configuration and discovery."""

from __future__ import annotations

import os

from fastapi import APIRouter

from ...core.enums import AgentType
from ...core.oauth import oauth_available

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/agents")
def list_agents() -> list[dict]:
    """Return the list of available agent types."""
    return [
        {
            "type": "claude-code",
            "name": "Claude Code",
            "description": "Claude CLI agent for Lean 4 proof and code generation",
            "models": [
                "sonnet-4-6",
                "opus-4-6",
            ],
        },
        {
            "type": "codex",
            "name": "Codex",
            "description": "Codex CLI agent for Lean 4 proof and code generation",
            "models": [
                "gpt-5.3-codex",
                "gpt-5.4",
            ],
        },
    ]


@router.get("/oauth-status")
def oauth_status() -> dict:
    """Report which subscription (OAuth) credentials are mounted on the server.

    Frontend uses this to enable/disable the "Subscription" backend option.
    """
    return {
        "claude": oauth_available(AgentType.claude_code),
        "codex": oauth_available(AgentType.codex),
    }


@router.get("/benchmarks")
def list_benchmarks() -> list[dict]:
    """Scan the Benchmarks/ directory for benchmark suites."""
    benchmarks_dir = os.path.join(os.getcwd(), "Benchmarks")
    if not os.path.isdir(benchmarks_dir):
        return []

    benchmarks = []
    for entry in sorted(os.listdir(benchmarks_dir)):
        suite_dir = os.path.join(benchmarks_dir, entry)
        if not os.path.isdir(suite_dir):
            continue

        tasks = sorted(
            f
            for f in os.listdir(suite_dir)
            if f.endswith(".lean") and not f.endswith("_Generated.lean")
        )
        benchmarks.append({
            "name": entry,
            "task_count": len(tasks),
            "tasks": tasks,
        })

    return benchmarks
