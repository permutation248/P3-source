"""Single-task execution runner."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

from ..core.config import ExperimentConfig
from ..io.result_store import ResultStore
from .prompts import _AUTONOMOUS_SUFFIX, build_prompt
from .workspace import WorkspaceManager

logger = logging.getLogger(__name__)


def _save_output_md(stream_path: str, proof_dst: str) -> None:
    """Extract the model's text output from the stream file and save as output.md."""
    if not os.path.exists(stream_path):
        return

    messages: list[str] = []
    try:
        with open(stream_path, "r") as fh:
            for raw_line in fh:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    obj = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                event_type = obj.get("type", "")

                # Claude Code format: type="assistant"
                if event_type == "assistant":
                    content = obj.get("message", {}).get("content", [])
                    texts = [
                        b["text"]
                        for b in content
                        if isinstance(b, dict) and b.get("type") == "text" and b.get("text")
                    ]
                    if texts:
                        messages.append("\n".join(texts))

                # Codex format: type="item.completed", item.type="agent_message"
                elif event_type == "item.completed":
                    item = obj.get("item", {})
                    if item.get("type") == "agent_message" and item.get("text"):
                        messages.append(item["text"])

    except Exception:
        logger.debug("Failed to parse stream for output.md", exc_info=True)
        return

    if not messages:
        messages = ["*(No assistant text output was produced.)*"]

    md_path = os.path.join(proof_dst, "output.md")
    try:
        with open(md_path, "w") as f:
            for i, msg in enumerate(messages):
                if i > 0:
                    f.write("\n\n---\n\n")
                f.write(msg)
        logger.info("Saved model output → %s", md_path)
    except Exception:
        logger.debug("Failed to write output.md", exc_info=True)


def _ensure_lean_lsp_mcp(project_root: str, workspace: str, *, docker_enabled: bool) -> None:
    """Run Lean LSP MCP preflight checks for a task workspace."""
    script_path = os.path.join(project_root, "scripts", "ensure_lean_lsp_mcp.sh")
    if not os.path.isfile(script_path):
        raise RuntimeError(f"Missing preflight script: {script_path}")

    cmd = ["bash", script_path, workspace]
    if docker_enabled:
        cmd.append("--docker")

    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.stdout.strip():
        logger.info("lean-lsp preflight: %s", proc.stdout.strip())
    if proc.stderr.strip():
        logger.warning("lean-lsp preflight stderr: %s", proc.stderr.strip())
    if proc.returncode != 0:
        raise RuntimeError(
            f"lean-lsp preflight failed (exit={proc.returncode}) for workspace {workspace}"
        )


class TaskRunner:
    """Execute a single Lean 4 task through an AI agent."""

    def __init__(
        self,
        agent,
        extractor,
        config: ExperimentConfig,
        project_root: str,
        docker_config=None,
    ) -> None:
        self.agent = agent
        self.extractor = extractor
        self.config = config
        self.project_root = project_root
        # Resolved docker config (image, lake_cache_path, skills_config filled in).
        # Falls back to config.docker for backwards compatibility.
        self._docker_config = docker_config
        self._ws_manager = WorkspaceManager(
            project_root,
            config.skills_config,
            docker_enabled=config.docker.enabled,
            agent_type=config.agent.type,
            backend=config.agent.backend,
            model=config.agent.model,
        )

    def run(self, task_file: str, output_dir: str, *, task_name: str | None = None) -> dict:
        """Run the agent on *task_file* and return a result dict."""
        workspace = None
        try:
            # 1. Create workspace
            workspace, work_file = self._ws_manager.create_workspace(
                task_file, tasks_mode=self.config.tasks_mode
            )
            _ensure_lean_lsp_mcp(
                self.project_root,
                workspace,
                docker_enabled=self.config.docker.enabled,
            )

            # 2. Determine task name
            effective_task_name = task_name or os.path.splitext(os.path.basename(task_file))[0]

            # 3. Build prompt — user-supplied custom_prompt overrides the
            # default. We still substitute {target_path} so the user can
            # parameterize, and append the autonomous suffix so batch
            # semantics are preserved.
            if self.config.custom_prompt:
                if self.config.docker.enabled:
                    target_path = (
                        "/task"
                        if self.config.tasks_mode == "project"
                        else os.path.join("/task", os.path.basename(work_file))
                    )
                else:
                    target_path = workspace if self.config.tasks_mode == "project" else work_file
                prompt = self.config.custom_prompt.replace("{target_path}", target_path)
                if _AUTONOMOUS_SUFFIX.strip() not in prompt:
                    prompt = prompt + _AUTONOMOUS_SUFFIX
            else:
                prompt = build_prompt(
                    mode=self.config.mode,
                    task_file=work_file,
                    lean_project_dir=workspace,
                    agent_type=str(self.config.agent.type),
                    tasks_mode=self.config.tasks_mode,
                    docker_enabled=self.config.docker.enabled,
                    skills_config=str(self.config.skills_config),
                )

            # 4. Stream path in output directory
            os.makedirs(output_dir, exist_ok=True)
            stream_path = os.path.join(output_dir, f"{effective_task_name}.stream.jsonl")

            # 5-6. Run agent
            start = time.monotonic()
            exit_code = self.agent.run(
                prompt=prompt,
                workdir=workspace,
                stream_path=stream_path,
                timeout=self.config.task_timeout_seconds,
            )
            elapsed = time.monotonic() - start

            logger.info(
                "Task %s finished in %.1fs (exit=%d)", effective_task_name, elapsed, exit_code
            )

            # 7-8. Extract results
            result = self.extractor.extract(
                stream_path=stream_path,
                task_path=work_file,
                elapsed_seconds=elapsed,
                model=self.config.agent.model or "",
                docker_config=self._docker_config if self._docker_config else (
                    self.config.docker if self.config.docker.enabled else None
                ),
                tasks_mode=self.config.tasks_mode,
            )
            result["task_name"] = effective_task_name

            # 9. Add mode
            result["mode"] = str(self.config.mode)

            # 9b. Preserve claude-tap traces if they exist
            if self.config.agent.use_tap:
                tap_src = os.path.join(
                    workspace, self.config.agent.tap_output_dir
                )
                if os.path.isdir(tap_src):
                    tap_dst = os.path.join(output_dir, "traces", effective_task_name)
                    os.makedirs(tap_dst, exist_ok=True)
                    try:
                        for entry in os.listdir(tap_src):
                            src_path = os.path.join(tap_src, entry)
                            dst_path = os.path.join(tap_dst, entry)
                            if os.path.isdir(src_path):
                                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                            else:
                                shutil.copy2(src_path, dst_path)
                        logger.info("Saved traces for %s → %s", effective_task_name, tap_dst)
                    except Exception:
                        # Trace export is best-effort; it should never block result extraction/persistence.
                        logger.warning("Failed to copy traces for %s", effective_task_name, exc_info=True)

            # 10. Preserve workspace artifacts (excluding bulky build dirs)
            _EXCLUDE_DIRS = {".lake", ".git", "__pycache__", ".claude", ".agents"}
            proof_dst = os.path.join(output_dir, "proofs", effective_task_name)
            os.makedirs(proof_dst, exist_ok=True)
            for p in Path(workspace).rglob("*"):
                if p.is_dir():
                    continue
                rel = p.relative_to(workspace)
                if any(part in _EXCLUDE_DIRS for part in rel.parts):
                    continue
                if p.is_symlink():
                    continue
                dest = Path(proof_dst) / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(p), str(dest))
            logger.info("Saved workspace for %s → %s", effective_task_name, proof_dst)

            # 11. Extract model output into output.md
            _save_output_md(stream_path, proof_dst)

            # 12. Save result
            store = ResultStore(output_dir)
            store.save_result(effective_task_name, result)

            return result

        except Exception:
            logger.exception("Task %s failed with unexpected error", task_file)
            raise

        finally:
            # Cleanup workspace
            if workspace:
                self._ws_manager.cleanup(workspace)
