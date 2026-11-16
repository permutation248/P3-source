"""Default result extractor for Anonymous-Prover experiments."""

from __future__ import annotations

import logging
import os

from ..analysis.lean_runner import AxiomResult, LeanRunner
from ..analysis.sorry_analyzer import analyze_sorries
from .base import BaseExtractor

logger = logging.getLogger(__name__)

_TASK_SKIP_DIRS = {
    ".lake",
    ".git",
    "build",
    "lake-packages",
    ".claude",
    ".agents",
    "__pycache__",
}


def _collect_task_lean_files(project_dir: str, entry_basename: str) -> list[str]:
    """Return every task-owned ``.lean`` path under ``project_dir``.

    Paths are returned relative to ``project_dir`` so they can be fed
    directly to the axiom-checker shell script inside a Docker mount.
    The entry file itself is excluded — the caller passes it separately
    as the primary ``file_path``.
    """
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = [d for d in dirnames if d not in _TASK_SKIP_DIRS]
        for name in filenames:
            if not name.endswith(".lean"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), project_dir)
            if rel == entry_basename:
                continue
            found.append(rel)
    return sorted(found)


class DefaultExtractor(BaseExtractor):
    """Extract results by inspecting the final ``_Generated.lean`` file and the
    agent stream output."""

    def extract(
        self,
        stream_path: str,
        task_path: str,
        *,
        elapsed_seconds: float = 0.0,
        model: str = "",
        docker_config=None,
        tasks_mode: str = "project",
    ) -> dict:
        """Produce a result dict for a single task.

        Parameters
        ----------
        stream_path:
            Path to the ``.stream.jsonl`` file written by the agent.
        task_path:
            Path to the ``_Generated.lean`` work file (final state).
        elapsed_seconds:
            Wall-clock time the agent was given.
        tasks_mode:
            Either ``"file"`` (single-file tasks — only ``task_path``
            itself is scanned) or ``"project"`` (split-project tasks —
            the whole workspace directory is walked, excluding build
            and tooling dirs).  Defaults to ``"project"`` because that
            is the only mode where recursion matters and the only mode
            whose sibling files were being silently ignored.
        """
        # 1. Parse stream output
        metrics = self._parse_stream(stream_path, fallback_model=model)

        # 2. Analyse the final task for sorries and compile validity.
        # project mode walks the whole workspace so split-project tasks
        # (e.g. `libs/AhoCorasick/AhoCorasick/Build.lean`) are not
        # silently skipped.  Submodule `sorry` still only produces a
        # warning during compile, so we rely on the recursive scan
        # rather than the compile exit code to catch it.
        # file mode keeps the historical contract: only the single
        # ``<name>_Generated.lean`` file is inspected.
        project_dir = os.path.dirname(task_path) or "."
        scan_target = project_dir if tasks_mode == "project" else task_path
        sorry_count = 0
        sorries_by_file: dict[str, list[int]] = {}
        error_count = 0
        compilation_error = False
        is_timeout = False
        if os.path.exists(task_path):
            try:
                sorry_info = analyze_sorries(scan_target)
                sorry_count = sorry_info["total_sorries"]
                sorries_by_file = sorry_info.get("sorries_by_file", {})
            except OSError:
                logger.warning("Could not scan task target: %s", scan_target)
                compilation_error = True

            # Build-check the final file in its workspace context.
            try:
                lean_path = LeanRunner.find_lean()
                lean_result = LeanRunner(lean_path).check_file(
                    file_path=os.path.basename(task_path),
                    project_dir=project_dir,
                    docker_config=docker_config,
                )
                error_count = lean_result.error_count
                compilation_error = compilation_error or (not lean_result.success)
                is_timeout = is_timeout or lean_result.timeout
            except Exception:
                logger.warning(
                    "Lean compilation check failed for task: %s", task_path,
                    exc_info=True,
                )
                compilation_error = True
                error_count = max(error_count, 1)
        else:
            logger.warning("Task file not found: %s", task_path)
            compilation_error = True

        # 3. Axiom check (only when compilation succeeded and no sorries).
        # Enumerate every task-owned .lean file and hand the list to the
        # axiom checker; otherwise `axiom` declarations in submodules slip
        # past (the script only introspects the first namespace of each
        # file it's told about).
        axiom_result = AxiomResult(status="unknown")
        if sorry_count == 0 and not compilation_error and os.path.exists(task_path):
            try:
                lean_path = LeanRunner.find_lean()
                extra_files = (
                    _collect_task_lean_files(
                        project_dir, os.path.basename(task_path)
                    )
                    if tasks_mode == "project"
                    else []
                )
                axiom_result = LeanRunner(lean_path).check_axioms(
                    file_path=os.path.basename(task_path),
                    project_dir=project_dir,
                    timeout=max(60, 30 * (1 + len(extra_files))),
                    docker_config=docker_config,
                    extra_files=extra_files,
                )
            except Exception:
                logger.warning(
                    "Axiom check failed for task: %s", task_path,
                    exc_info=True,
                )

        # 4. Detect timeout marker from stream tail.
        # Keep this window large enough to tolerate trailing JSON lines.
        if os.path.exists(stream_path):
            try:
                size = os.path.getsize(stream_path)
                tail_window = 64 * 1024
                with open(stream_path, "r") as fh:
                    if size > tail_window:
                        fh.seek(size - tail_window)
                    tail = fh.read()
                if "[TIMEOUT]" in tail:
                    is_timeout = True
            except OSError:
                pass

        # 5. Derive task name
        task_name = self._derive_task_name(task_path)

        total_tokens = metrics.total_input_tokens + metrics.total_output_tokens

        # solved requires: no sorry, no compilation error, no timeout,
        # and axiom check must not have explicitly failed.
        # "unknown" (script missing / infra error) is treated as neutral —
        # not having an axiom checker should not block otherwise valid proofs.
        axiom_ok = axiom_result.status != "fail"

        return {
            "task_name": task_name,
            "solved": sorry_count == 0 and not compilation_error and not is_timeout and axiom_ok,
            "sorry_count": sorry_count,
            "sorries_by_file": {
                os.path.relpath(k, project_dir): v
                for k, v in sorries_by_file.items()
            },
            "error_count": error_count,
            "compilation_error": compilation_error,
            "timeout": is_timeout,
            "axiom_check": axiom_result.status,
            "custom_axioms": axiom_result.custom_axioms,
            "total_time_seconds": round(elapsed_seconds, 2),
            "total_tokens": total_tokens,
            "input_tokens": metrics.total_input_tokens,
            "output_tokens": metrics.total_output_tokens,
            "cost_usd": metrics.cost_usd,
            "total_turns": metrics.total_turns,
            "tool_calls": metrics.tool_calls,
            "model": metrics.model,
            "mode": "",
        }
