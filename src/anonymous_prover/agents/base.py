"""Base agent with shared helper methods."""

from __future__ import annotations

import logging
import os
import signal
import time

from ..core.enums import AgentType
from ..core.oauth import oauth_available, oauth_container_path, oauth_host_path

logger = logging.getLogger(__name__)

# Environment variables to forward into Docker containers.
_DOCKER_ENV_FORWARD = [
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "CLAUDE_CODE_OAUTH_TOKEN",
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
    "CLAUDE_CODE_SUBAGENT_MODEL",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "LEAN4_SCRIPTS",
    "LEAN4_REFS",
    "LEAN4_PYTHON_BIN",
    "LEAN_PROJECT_PATH",
    "SMART_SEARCH_OFFLINE",
]


class BaseAgent:
    """Base class for AI agents with shared utilities."""

    def __init__(self, model: str | None = None, docker_config=None) -> None:
        self.model = model
        self.docker_config = docker_config  # DockerConfig | None
        # Optional experiment id, used to label docker containers so the
        # /experiments/{id}/stop route can authoritatively kill them.
        self.experiment_id: int | None = None

    @staticmethod
    def _valid_scripts_dir(path: str | None) -> bool:
        if not path or not os.path.isdir(path):
            return False
        return os.path.isfile(os.path.join(path, "sorry_analyzer.py"))

    @staticmethod
    def _skill_bases(workdir: str, prefer_roots: tuple[str, ...]) -> list[str]:
        bases: list[str] = []
        for root in prefer_roots:
            skills_dir = os.path.join(workdir, root, "skills")
            if not os.path.isdir(skills_dir):
                continue

            names: list[str] = []
            for preferred in ("standard", "extended"):
                if os.path.isdir(os.path.join(skills_dir, preferred)):
                    names.append(preferred)
            for name in sorted(os.listdir(skills_dir)):
                if name in names:
                    continue
                if os.path.isdir(os.path.join(skills_dir, name)):
                    names.append(name)

            for name in names:
                bases.append(os.path.join(skills_dir, name))
        return bases

    def _configure_lean_env(
        self,
        *,
        workdir: str,
        env: dict[str, str],
        prefer_roots: tuple[str, ...] = (".agents", ".claude"),
    ) -> None:
        """Resolve LEAN4_SCRIPTS/LEAN4_REFS with priority + existence checks.

        Priority:
        1) ANONYMOUS_LEAN4_SCRIPTS_OVERRIDE / ANONYMOUS_LEAN4_REFS_OVERRIDE
        2) Current workspace skill directories
        3) Existing LEAN4_SCRIPTS / LEAN4_REFS env values (if valid)
        """
        override_scripts = (
            env.get("ANONYMOUS_LEAN4_SCRIPTS_OVERRIDE")
            or os.environ.get("ANONYMOUS_LEAN4_SCRIPTS_OVERRIDE")
        )
        override_refs = (
            env.get("ANONYMOUS_LEAN4_REFS_OVERRIDE")
            or os.environ.get("ANONYMOUS_LEAN4_REFS_OVERRIDE")
        )

        scripts: str | None = None
        refs: str | None = None
        scripts_source = "none"

        if self._valid_scripts_dir(override_scripts):
            scripts = override_scripts
            scripts_source = "override"
        else:
            for base in self._skill_bases(workdir, prefer_roots):
                cand_scripts = os.path.join(base, "scripts")
                if self._valid_scripts_dir(cand_scripts):
                    scripts = cand_scripts
                    refs_dir = os.path.join(base, "references")
                    refs = refs_dir if os.path.isdir(refs_dir) else None
                    scripts_source = "workspace"
                    break

        if scripts is None:
            fallback_scripts = env.get("LEAN4_SCRIPTS") or os.environ.get("LEAN4_SCRIPTS")
            if self._valid_scripts_dir(fallback_scripts):
                scripts = fallback_scripts
                scripts_source = "fallback-env"

        if scripts is not None:
            env["LEAN4_SCRIPTS"] = scripts
        else:
            env.pop("LEAN4_SCRIPTS", None)

        if override_refs and os.path.isdir(override_refs):
            refs = override_refs
        elif refs is None:
            fallback_refs = env.get("LEAN4_REFS") or os.environ.get("LEAN4_REFS")
            if fallback_refs and os.path.isdir(fallback_refs):
                refs = fallback_refs

        if refs is not None:
            env["LEAN4_REFS"] = refs
        else:
            env.pop("LEAN4_REFS", None)

        env.setdefault("LEAN_PROJECT_PATH", workdir)

        logger.info(
            "Lean env resolved: source=%s LEAN4_SCRIPTS=%s LEAN4_REFS=%s",
            scripts_source,
            env.get("LEAN4_SCRIPTS"),
            env.get("LEAN4_REFS"),
        )

    # Workspace files that need a non-default container path.
    # These are mounted *in addition to* the /task workspace mount.
    _SPECIAL_MOUNTS: dict[str, str] = {
        ".claude.json": "/home/solver/.claude.json",
        # Codex MCP config — mounted as *global* config so it is
        # always read (project-scoped config requires explicit trust).
        ".codex/config.toml": "/home/solver/.codex/config.toml",
    }

    def _wrap_in_docker(
        self,
        cmd: list[str],
        workdir: str,
        stream_path: str,
        env: dict[str, str],
    ) -> tuple[list[str], str, dict[str, str]]:
        """Wrap *cmd* inside ``docker run`` with proper mounts.

        The workspace directory is mounted as /task so that all files
        (including .lean) live in a real directory where rename-based
        editors (sed -i, perl -i) work correctly.  The pre-built .lake
        from the host is then overlaid on top as a sub-mount.
        """
        dc = self.docker_config
        if dc is None or not dc.enabled:
            logger.info("Docker disabled (config=%s), running locally", dc)
            return cmd, workdir, env
        logger.info("Wrapping command in Docker (image=%s)", dc.image)

        docker_cmd: list[str] = [
            "docker", "run", "--rm",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "--privileged",
        ]

        # Label the container so the stop route can find and kill it
        # regardless of host-side subprocess state.
        if self.experiment_id is not None:
            docker_cmd.extend([
                "--label", f"anonymous_experiment_id={self.experiment_id}",
            ])

        # Forward API key / Lean env vars (rewrite paths for /task)
        for key in _DOCKER_ENV_FORWARD:
            val = env.get(key) or os.environ.get(key)
            if val:
                if key == "LEAN_PROJECT_PATH":
                    val = "/task"
                elif key in {"LEAN4_SCRIPTS", "LEAN4_REFS"}:
                    host_ws = os.path.abspath(workdir)
                    host_val = os.path.abspath(val)
                    if host_val == host_ws:
                        val = "/task"
                    elif host_val.startswith(host_ws + os.sep):
                        val = "/task" + host_val[len(host_ws):]
                docker_cmd.extend(["-e", f"{key}={val}"])

        abs_ws = os.path.abspath(workdir)

        # Ensure .claude.json exists (Claude CLI state file).
        host_claude_json = os.path.join(abs_ws, ".claude.json")
        if not os.path.exists(host_claude_json):
            try:
                with open(host_claude_json, "w", encoding="utf-8") as fh:
                    fh.write("{}\n")
            except OSError:
                logger.warning("Failed to create %s", host_claude_json)

        # --- Mount order matters: later sub-mounts overlay earlier ones ---
        # 1. Whole workspace directory → /task (rw, enables rename-based edits)
        docker_cmd.extend(["-v", f"{abs_ws}:/task"])

        # 2. .lake from host → /task/.lake (read-only overlay)
        lake_path = dc.lake_cache_path
        if lake_path and os.path.isdir(lake_path):
            docker_cmd.extend(["-v", f"{os.path.abspath(lake_path)}:/task/.lake:ro"])

        # 3. .lake/build — writable overlay so `lake build` can compile
        #    task-specific modules.  workspace.py copies the pre-built
        #    build/ (~10 MB) into .lake-build/ for this purpose.
        lake_build_rw = os.path.join(abs_ws, ".lake-build")
        if os.path.isdir(lake_build_rw):
            docker_cmd.extend(["-v", f"{lake_build_rw}:/task/.lake/build"])

        # 3. Special mounts (.claude.json → /home/solver/.claude.json)
        for fname, container_path in self._SPECIAL_MOUNTS.items():
            host_path = os.path.join(abs_ws, fname)
            if os.path.exists(host_path):
                docker_cmd.extend(["-v", f"{host_path}:{container_path}"])

        # Mount stream output directory so JSONL is written to host
        stream_dir = os.path.dirname(os.path.abspath(stream_path))
        docker_cmd.extend(["-v", f"{stream_dir}:{stream_dir}"])

        # Authentication files — forward each subscription credential file
        # that actually exists on the host, so the CLI inside the container
        # can use OAuth when no API key is available.
        for at in (AgentType.claude_code, AgentType.codex):
            if oauth_available(at):
                docker_cmd.extend(
                    ["-v", f"{oauth_host_path(at)}:{oauth_container_path(at)}"]
                )

        # Extra user-supplied docker args
        if dc.extra_docker_args:
            docker_cmd.extend(dc.extra_docker_args)

        docker_cmd.extend(["-w", "/task", dc.image])
        docker_cmd.extend(cmd)

        return docker_cmd, workdir, env

    @staticmethod
    def _kill_process_tree(proc) -> None:
        """Terminate a subprocess and its children gracefully, then force-kill."""
        pid = proc.pid
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            # Process already gone
            return

        try:
            proc.wait(timeout=5)
        except Exception:
            # Force kill after 5-second grace period
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass

        logger.debug("Killed process tree rooted at PID %d", pid)

    @staticmethod
    def _is_transient_failure(stream_path: str, elapsed: float) -> bool:
        """Return True if the output looks like a transient failure.

        A transient failure is characterised by an empty (0-byte) output file
        and a very short elapsed time (< 60 s), suggesting the agent crashed
        or was refused before doing any real work.
        """
        if elapsed >= 60.0:
            return False
        try:
            size = os.path.getsize(stream_path)
        except OSError:
            size = 0
        return size == 0
