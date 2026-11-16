"""Codex CLI agent implementation."""

from __future__ import annotations

import logging
import os
import subprocess
import time

from .base import BaseAgent
from ..extractors.stream_parsers import StreamJsonParser

logger = logging.getLogger(__name__)

MAX_RETRIES = 2
BACKOFF_BASE = 3  # seconds


class CodexAgent(BaseAgent):
    """Agent that drives Codex via the ``codex exec`` CLI."""

    def __init__(
        self,
        model: str | None = None,
        use_tap: bool = False,
        tap_output_dir: str = "claude_traces",
        max_cost_usd: float | None = None,
        docker_config=None,
    ) -> None:
        super().__init__(model=model, docker_config=docker_config)
        # Unused, kept for factory signature compatibility.
        self.use_tap = use_tap
        self.tap_output_dir = tap_output_dir
        self.max_cost_usd = max_cost_usd

    def run(
        self,
        prompt: str,
        workdir: str,
        stream_path: str,
        timeout: int = 1800,
    ) -> int:
        """Execute ``codex exec`` and write JSONL events to ``stream_path``."""
        cmd = [
            "codex",
            "exec",
            "--json",
            "--ephemeral",
            "--full-auto",
            "--skip-git-repo-check",
        ]
        if self.model:
            cmd.extend(["--model", self.model])
        cmd.append(prompt)

        stderr_path = stream_path.replace(".stream.jsonl", ".stderr.txt")
        if stderr_path == stream_path:
            stderr_path = stream_path + ".stderr.txt"

        for attempt in range(1, MAX_RETRIES + 1):
            logger.info(
                "Attempt %d/%d  cmd=%s  workdir=%s",
                attempt,
                MAX_RETRIES,
                " ".join(cmd[:-1]) + " <prompt>",
                workdir,
            )

            start = time.monotonic()
            exit_code = self._invoke(
                cmd, workdir, stream_path, stderr_path, timeout
            )
            elapsed = time.monotonic() - start

            if exit_code == -1:
                return -1

            if exit_code != 0 and self._is_transient_failure(stream_path, elapsed):
                if attempt < MAX_RETRIES:
                    wait = BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "Transient failure (exit=%d, %.1fs). Retrying in %ds ...",
                        exit_code,
                        elapsed,
                        wait,
                    )
                    time.sleep(wait)
                    continue

            return exit_code

        logger.error("All %d attempts failed.", MAX_RETRIES)
        return exit_code  # type: ignore[possibly-undefined]

    def parse_output(self, stream_path: str) -> dict:
        """Parse Codex JSONL output using the shared stream parser."""
        parser = StreamJsonParser()
        metrics = parser.parse(stream_path, fallback_model=self.model or "")
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
            # Resolve Lean helper paths with existence checks and clear precedence.
            self._configure_lean_env(workdir=workdir, env=env)
            # Optionally wrap inside Docker
            logger.info("Before docker wrap: docker_config=%s", self.docker_config)
            cmd, workdir, env = self._wrap_in_docker(
                cmd, workdir, stream_path, env
            )
            logger.info("After docker wrap: cmd[0:3]=%s", cmd[:3])

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
                logger.error("'codex' (or docker) CLI not found on PATH")
                return 1

            try:
                exit_code = proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                logger.warning("Timeout (%ds) reached, killing process tree", timeout)
                stdout_f.write("\n[TIMEOUT]\n")
                stdout_f.flush()
                self._kill_process_tree(proc)
                return -1

        logger.info("Process exited with code %d", exit_code)
        return exit_code
