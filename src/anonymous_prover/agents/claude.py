"""Claude Code CLI agent implementation."""

from __future__ import annotations

import logging
import os
import subprocess
import time

from .base import BaseAgent
from ..extractors.stream_parsers import StreamJsonParser

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 5  # seconds
DEFAULT_CLAUDE_MAX_OUTPUT_TOKENS = "120000"


class ClaudeAgent(BaseAgent):
    """Agent that drives Claude via the ``claude`` CLI.

    When *use_tap* is ``True``, the agent invokes ``claude-tap`` instead of
    ``claude`` so that full HTTP-level traces are persisted alongside the
    normal stream-json output.
    """

    # Default tools available to the agent.
    DEFAULT_TOOLS = "Bash,Edit,Read,Write,Glob,Grep"

    def __init__(
        self,
        model: str | None = None,
        use_tap: bool = False,
        tap_output_dir: str = "claude_traces",
        max_cost_usd: float | None = None,
        max_turns: int | None = 1024,
        allowed_tools: str | None = None,
        docker_config=None,
    ) -> None:
        super().__init__(model=model, docker_config=docker_config)
        self.use_tap = use_tap
        self.tap_output_dir = tap_output_dir
        self.max_cost_usd = max_cost_usd
        self.max_turns = max_turns
        self.allowed_tools = allowed_tools

    # -- CLIAgent protocol ---------------------------------------------------

    def run(
        self,
        prompt: str,
        workdir: str,
        stream_path: str,
        timeout: int = 1800,
    ) -> int:
        """Execute *claude -p* and stream output to *stream_path*.

        Returns the process exit code, or ``-1`` on timeout.
        """
        if self.use_tap:
            # Use claude-tap wrapper for trace collection.
            # Create the host-side directory; inside Docker the path is
            # under /task so we pass the container-relative path to the
            # command and let _wrap_in_docker handle mount translation.
            tap_dir_host = os.path.join(workdir, self.tap_output_dir)
            os.makedirs(tap_dir_host, exist_ok=True)
            docker_enabled = self.docker_config and self.docker_config.enabled
            tap_dir_cmd = f"/task/{self.tap_output_dir}" if docker_enabled else tap_dir_host
            cmd = [
                "claude-tap",
                "--tap-output-dir", tap_dir_cmd,
                "--",
                "-p", prompt,
                "--output-format", "stream-json",
                "--dangerously-skip-permissions",
                "--include-partial-messages",
                "--verbose",
            ]
        else:
            cmd = [
                "claude",
                "-p", prompt,
                "--output-format", "stream-json",
                "--dangerously-skip-permissions",
                "--include-partial-messages",
                "--verbose",
            ]
        if self.model:
            cmd.extend(["--model", self.model])
        if self.max_cost_usd is not None:
            cmd.extend(["--max-budget-usd", str(self.max_cost_usd)])
        if self.max_turns is not None:
            cmd.extend(["--max-turns", str(self.max_turns)])
        if self.allowed_tools:
            cmd.extend(["--allowedTools", self.allowed_tools])

        stderr_path = stream_path.replace(".stream.jsonl", ".stderr.txt")
        if stderr_path == stream_path:
            stderr_path = stream_path + ".stderr.txt"

        for attempt in range(1, MAX_RETRIES + 1):
            logger.info(
                "Attempt %d/%d  cmd=%s  workdir=%s",
                attempt,
                MAX_RETRIES,
                " ".join(cmd),
                workdir,
            )

            start = time.monotonic()
            exit_code = self._invoke(
                cmd, workdir, stream_path, stderr_path, timeout
            )
            elapsed = time.monotonic() - start

            if exit_code == -1:
                # Timeout -- do not retry
                return -1

            if exit_code != 0 and self._is_transient_failure(stream_path, elapsed):
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "Transient failure (exit=%d, %.1fs).  Retrying in %ds ...",
                        exit_code,
                        elapsed,
                        wait,
                    )
                    time.sleep(wait)
                    continue

            return exit_code

        # Exhausted retries
        logger.error("All %d attempts failed.", MAX_RETRIES)
        return exit_code  # type: ignore[possibly-undefined]

    def parse_output(self, stream_path: str) -> dict:
        """Parse a stream-json output file and return metrics as a dict."""
        parser = StreamJsonParser()
        metrics = parser.parse(stream_path)
        return {
            "total_input_tokens": metrics.total_input_tokens,
            "total_output_tokens": metrics.total_output_tokens,
            "cached_input_tokens": metrics.cached_input_tokens,
            "total_turns": metrics.total_turns,
            "tool_calls": metrics.tool_calls,
            "model": metrics.model,
            "cost_usd": metrics.cost_usd,
            "cost_source": metrics.cost_source,
        }

    # -- internal helpers ----------------------------------------------------

    def _invoke(
        self,
        cmd: list[str],
        workdir: str,
        stream_path: str,
        stderr_path: str,
        timeout: int,
    ) -> int:
        """Run *cmd* as a subprocess, returning exit code or -1 on timeout."""
        os.makedirs(os.path.dirname(stream_path) or ".", exist_ok=True)

        with (
            open(stream_path, "w") as stdout_f,
            open(stderr_path, "w") as stderr_f,
        ):
            env = os.environ.copy()
            # Set a default output token cap only when not externally configured.
            env.setdefault(
                "CLAUDE_CODE_MAX_OUTPUT_TOKENS",
                DEFAULT_CLAUDE_MAX_OUTPUT_TOKENS,
            )
            # ``--dangerously-skip-permissions`` refuses to run as root for
            # safety. The Docker mode sidesteps this via ``--user`` demotion;
            # in native/DSW mode the whole pod already runs in a k8s
            # sandbox, so advertise that to Claude Code so it accepts the
            # flag. ``IS_SANDBOX=1`` is Claude Code's documented escape
            # hatch for "I know what I'm doing, this env is isolated".
            env.setdefault("IS_SANDBOX", "1")
            logger.info(
                "Using CLAUDE_CODE_MAX_OUTPUT_TOKENS=%s",
                env.get("CLAUDE_CODE_MAX_OUTPUT_TOKENS"),
            )
            # Force sub-agents to use the same model as the parent.
            # Without this, agent definitions with `model: opus` in their
            # frontmatter would silently escalate to a more expensive model.
            if self.model:
                env["CLAUDE_CODE_SUBAGENT_MODEL"] = self.model

            # Resolve Lean helper paths with existence checks and clear precedence.
            self._configure_lean_env(workdir=workdir, env=env)

            # Optionally wrap inside Docker
            cmd, workdir, env = self._wrap_in_docker(
                cmd, workdir, stream_path, env
            )

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=stdout_f,
                    stderr=stderr_f,
                    cwd=workdir,
                    env=env,
                    start_new_session=True,
                )
            except FileNotFoundError:
                logger.error("'claude' (or docker) CLI not found on PATH")
                return 1

            try:
                exit_code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning("Timeout (%ds) reached, killing process tree", timeout)
                # Write timeout marker
                stdout_f.write("\n[TIMEOUT]\n")
                stdout_f.flush()
                self._kill_process_tree(proc)
                return -1

        logger.info("Process exited with code %d", exit_code)
        return exit_code
