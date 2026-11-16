"""Abstract base classes defining the core interfaces for Anonymous-Prover."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class CLIAgent(ABC):
    """Interface for running a CLI-based AI agent."""

    @abstractmethod
    def run(
        self,
        prompt: str,
        workdir: str | Path,
        stream_path: str | Path,
        timeout: int,
    ) -> int:
        """Run the agent and return its exit code.

        Args:
            prompt: The prompt / instruction to send to the agent.
            workdir: Working directory for the agent process.
            stream_path: Path where the agent's raw output stream is saved.
            timeout: Maximum wall-clock seconds before the process is killed.

        Returns:
            Process exit code (0 = success).
        """

    @abstractmethod
    def parse_output(self, stream_path: str | Path) -> dict[str, Any]:
        """Parse the agent's saved output stream into a structured dict.

        Args:
            stream_path: Path to the raw stream file written during ``run``.

        Returns:
            Parsed output with at least keys ``tokens``, ``cost``, ``turns``.
        """


class StreamParser(ABC):
    """Interface for parsing an agent output stream into metrics."""

    @abstractmethod
    def parse(self, stream_path: str | Path) -> Any:
        """Parse the stream file and return aggregated metrics."""


class ResultExtractor(ABC):
    """Interface for extracting a task result from agent output + Lean file."""

    @abstractmethod
    def extract(
        self,
        stream_path: str | Path,
        task_path: str | Path,
        *,
        elapsed_seconds: float,
    ) -> dict[str, Any]:
        """Extract a result dict for one task.

        Args:
            stream_path: Path to the agent's output stream.
            task_path: Path to the (possibly modified) Lean source file.
            elapsed_seconds: Wall-clock time the task took.

        Returns:
            Dict with keys like ``solved``, ``sorry_count``, ``error_count``,
            ``cost_usd``, ``total_turns``, etc.
        """


class ResultCollector(ABC):
    """Interface for aggregating per-task results into a summary."""

    @abstractmethod
    def collect(self, results_dir: str | Path) -> dict[str, Any]:
        """Read all result files in *results_dir* and return a summary dict."""


class ResultComparator(ABC):
    """Interface for comparing two experiment runs."""

    @abstractmethod
    def compare(
        self,
        baseline_dir: str | Path,
        treatment_dir: str | Path,
    ) -> dict[str, Any]:
        """Compare baseline vs treatment results and return statistics."""
