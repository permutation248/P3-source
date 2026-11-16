"""Batch experiment runner -- execute all tasks and collect results."""

from __future__ import annotations

import logging
import os
import re
import threading
from contextvars import copy_context
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable

from ..agents.factory import create_agent
from ..collectors.factory import create_collector
from ..core.config import ExperimentConfig
from ..core.logging_context import (
    ExperimentTagFilter,
    install_experiment_record_factory,
    reset_experiment_tag,
    set_experiment_tag,
)
from ..core.task_discovery import discover_task_files
from ..extractors.factory import create_extractor
from .task_runner import TaskRunner

logger = logging.getLogger(__name__)

# Type alias for progress callbacks
ProgressCallback = Callable[[int, int, str, dict | None], None] | None


class ExperimentRunner:
    """Discover tasks, run them through the agent, and collect results."""

    def __init__(
        self,
        config: ExperimentConfig,
        project_root: str,
        experiment_id: int | None = None,
    ) -> None:
        self.config = config
        self.project_root = project_root
        self.experiment_id = experiment_id
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        """Signal the runner to stop accepting new tasks."""
        self._cancel_event.set()

    def run(self, progress_callback: ProgressCallback = None) -> dict:
        """Execute the experiment and return a summary dict."""
        # 1. Discover task files
        logger.info(
            "Discovering tasks: tasks_dir=%r, tasks_mode=%r, cwd=%s",
            self.config.tasks_dir, self.config.tasks_mode, os.getcwd(),
        )
        tasks = self._discover_tasks()
        if not tasks:
            logger.warning(
                "No task files found in %s (tasks_mode=%s, cwd=%s, exists=%s)",
                self.config.tasks_dir,
                self.config.tasks_mode,
                os.getcwd(),
                os.path.isdir(self.config.tasks_dir),
            )
            return {"total": 0, "solved": 0, "error": "no tasks found"}

        logger.info("Discovered %d tasks in %s", len(tasks), self.config.tasks_dir)

        # 2. Prepare output directory
        output_dir = self.config.resolved_output_dir
        os.makedirs(output_dir, exist_ok=True)
        log_path = os.path.join(
            output_dir,
            f".{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.log",
        )
        install_experiment_record_factory()
        experiment_tag = f"{self.config.name}:{log_path}"
        tag_token = set_experiment_tag(experiment_tag)
        root_logger = logging.getLogger()
        previous_root_level = root_logger.level
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.NOTSET)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        file_handler.addFilter(ExperimentTagFilter(experiment_tag))
        root_logger.addHandler(file_handler)
        if root_logger.level > logging.INFO:
            root_logger.setLevel(logging.INFO)
        logger.info("Experiment log file: %s", log_path)

        try:
            # 3. Create components via factories
            docker_config = None
            if self.config.docker.enabled:
                docker_config = self.config.docker.model_copy()
                if not docker_config.lake_cache_path:
                    docker_config.lake_cache_path = os.path.join(
                        self.project_root, ".lake"
                    )
                docker_config.skills_config = str(self.config.skills_config)
                docker_config.image = docker_config.resolve_image_for_skills(
                    str(self.config.skills_config)
                )
                logger.info(
                    "Docker image resolved for skills_config=%s -> %s",
                    self.config.skills_config,
                    docker_config.image,
                )
            agent = create_agent(
                self.config.agent.type,
                model=self.config.agent.model,
                use_tap=self.config.agent.use_tap,
                tap_output_dir=self.config.agent.tap_output_dir,
                max_cost_usd=self.config.max_cost_usd,
                docker_config=docker_config,
            )
            # Tag the agent so its docker containers carry the
            # anonymous_experiment_id label for cleanup.
            try:
                agent.experiment_id = self.experiment_id
            except AttributeError:
                pass
            extractor = create_extractor()
            runner = TaskRunner(agent, extractor, self.config, self.project_root,
                                docker_config=docker_config)

            # 4-6. Execute tasks (potentially in parallel)
            results: list[dict] = []
            completed = 0
            total = len(tasks)

            task_names = {tf: self._task_name(tf) for tf in tasks}

            # Emit an initial progress event so the UI/DB sees the
            # correct denominator immediately, instead of staying at
            # 0/0 until the first task completes (which can take many
            # minutes for slow Lean tasks).
            if progress_callback:
                try:
                    progress_callback(0, total, "", None)
                except Exception:
                    logger.exception("Initial progress_callback raised")

            def _run_one(task_file: str) -> dict | None:
                if self._cancel_event.is_set():
                    return None

                task_name = task_names[task_file]

                # Skip if result exists and not forcing
                if not self.config.force:
                    result_path = os.path.join(output_dir, f"{task_name}.result.json")
                    if os.path.exists(result_path):
                        logger.info("Skipping %s (result exists)", task_name)
                        return None

                return runner.run(task_file, output_dir, task_name=task_name)

            with ThreadPoolExecutor(max_workers=self.config.parallel) as pool:
                future_to_task = {
                    pool.submit(copy_context().run, _run_one, tf): tf for tf in tasks
                }

                for future in as_completed(future_to_task):
                    task_file = future_to_task[future]
                    task_name = task_names[task_file]
                    completed += 1

                    try:
                        result = future.result()
                        if result is not None:
                            results.append(result)
                    except Exception:
                        logger.exception("Task %s raised an exception", task_name)
                        result = None

                    if progress_callback:
                        progress_callback(completed, total, task_name, result)

                    if self._cancel_event.is_set():
                        logger.info("Cancellation requested — cancelling remaining tasks")
                        for f in future_to_task:
                            f.cancel()
                        break

            # 7. Collect and summarise
            collector = create_collector()
            summary = collector.collect(output_dir)

            logger.info(
                "Experiment %s complete: %d/%d solved (%.1f%%)",
                self.config.name,
                summary.get("solved", 0),
                summary.get("total", 0),
                summary.get("solved_rate", 0.0),
            )

            return summary
        finally:
            root_logger.removeHandler(file_handler)
            file_handler.close()
            root_logger.setLevel(previous_root_level)
            reset_experiment_tag(tag_token)

    # -- helpers -------------------------------------------------------------

    def _discover_tasks(self) -> list[str]:
        """Discover task files using shared dataset rules."""
        return discover_task_files(self.config.tasks_dir, self.config.tasks_mode)

    def _task_name(self, task_file: str) -> str:
        """Return a stable filesystem-safe unique task name."""
        rel = os.path.relpath(task_file, self.config.tasks_dir)
        rel_no_ext = os.path.splitext(rel)[0]
        normalized = rel_no_ext.replace("\\", "/")
        slug = re.sub(r"[^A-Za-z0-9._/-]+", "_", normalized).replace("/", "__")
        return slug
