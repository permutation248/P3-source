"""Prompt templates for driving Lean 4 tasks via different agents.

Both the Claude Code skill and the Codex AGENTS.md describe the same
``code | proof | auto`` mode protocol regardless of which skill variant
(``standard`` / ``extended`` / ``co_derivation``) is installed into the
workspace. The variant only changes the *content* of the skill — not the
calling convention. See ``workspace.py`` for how the variant is selected.
"""

from __future__ import annotations

_AUTONOMOUS_SUFFIX = (
    "\n\nCRITICAL: You are running in fully autonomous batch mode with NO human in the loop. "
    "Follow the instructions in the task file strictly. "
    "NEVER stop to ask for confirmation or suggest next steps. "
    "NEVER write a failure summary while you can still take actions. "
    "If stuck, rollback and try a completely different approach. "
    "Keep iterating until all sorries are eliminated or your session is terminated by the harness."
)

# The unified slash-command name. The same name is used regardless of
# skills_config — the workspace installs a different skill body under
# this name depending on the variant.
SKILL_SLASH_NAME = "lean4-codeprover"


def build_prompt(
    mode: str,
    task_file: str,
    lean_project_dir: str = "",
    agent_type: str = "claude-code",
    tasks_mode: str = "file",
    *,
    docker_enabled: bool = False,
    skills_config: str = "standard",
) -> str:
    """Return a fully-substituted prompt for the given *mode*.

    ``skills_config`` is accepted for API compatibility but does NOT affect
    the prompt body — the protocol is uniform across variants.
    """
    if mode not in {"code", "proof", "auto"}:
        raise ValueError(f"Unknown mode: {mode!r}. Expected one of ['code', 'proof', 'auto']")
    if docker_enabled:
        import os
        target_path = "/task" if tasks_mode == "project" else os.path.join("/task", os.path.basename(task_file))
    else:
        target_path = lean_project_dir if tasks_mode == "project" else task_file

    if agent_type == "codex":
        # Codex auto-loads AGENTS.md from the workspace root.
        # The prompt just needs to specify mode and target.
        return (
            f"Run in `{mode}` mode on `{target_path}`.\n"
            "Read AGENTS.md for workflow instructions. Follow them directly."
            + _AUTONOMOUS_SUFFIX
        )
    # Claude Code (and any other slash-command-driven harness). The
    # skill is installed under .claude/skills/lean4-codeprover/ by
    # workspace.py, so Claude Code registers `/lean4-codeprover` as a
    # top-level slash command. The mode (code/proof/auto) is passed as
    # the first positional arg, followed by the target file.
    return f"/{SKILL_SLASH_NAME} {mode} {target_path}" + _AUTONOMOUS_SUFFIX


def get_default_prompt(mode: str, skills_config: str = "standard") -> str:
    """Return the raw template string (with ``{target_path}`` placeholder).

    ``skills_config`` is accepted for API compatibility; the template is
    uniform across variants.
    """
    if mode not in {"code", "proof", "auto"}:
        raise ValueError(f"Unknown mode: {mode!r}. Expected one of ['code', 'proof', 'auto']")
    return f"/{SKILL_SLASH_NAME} {mode} {{target_path}}" + _AUTONOMOUS_SUFFIX
