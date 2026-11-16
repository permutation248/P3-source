"""Wrapper for running Lean 4 builds and checks."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LeanResult:
    """Result of checking a Lean 4 file."""
    success: bool
    error_count: int = 0
    errors: list[str] = field(default_factory=list)
    compilation_error: bool = False
    timeout: bool = False


@dataclass
class AxiomResult:
    """Result of checking axioms in a Lean 4 file.

    status is one of: "pass", "fail", "unknown".
    """
    status: str  # "pass" | "fail" | "unknown"
    custom_axioms: list[str] = field(default_factory=list)


class LeanRunner:
    """Thin wrapper around the Lean 4 / Lake CLI.

    Args:
        lean_path: Path to the ``lean`` executable.  Use :meth:`find_lean`
            to auto-detect it.
    """

    def __init__(self, lean_path: str = "lean") -> None:
        self.lean_path = lean_path

    # ------------------------------------------------------------------
    # Lean discovery
    # ------------------------------------------------------------------

    @classmethod
    def find_lean(cls) -> str:
        """Locate the Lean 4 executable.

        Checks:
            1. ``~/.elan/bin/lean``
            2. ``lean`` on ``$PATH`` via ``shutil.which``

        Returns:
            Absolute path to the ``lean`` binary.

        Raises:
            FileNotFoundError: If Lean cannot be found.
        """
        elan_path = os.path.expanduser("~/.elan/bin/lean")
        if os.path.isfile(elan_path) and os.access(elan_path, os.X_OK):
            return elan_path

        which_lean = shutil.which("lean")
        if which_lean is not None:
            return which_lean

        raise FileNotFoundError(
            "Could not find the Lean 4 executable. "
            "Install it via elan (https://github.com/leanprover/elan) or "
            "ensure 'lean' is on your PATH."
        )

    # ------------------------------------------------------------------
    # File checking
    # ------------------------------------------------------------------

    def check_file(
        self,
        file_path: str,
        project_dir: str,
        timeout: int = 120,
        docker_config=None,
    ) -> LeanResult:
        """Run ``lake env lean <file>`` and return a :class:`LeanResult`.

        Args:
            file_path: Path to the ``.lean`` file to check.
            project_dir: Root of the Lake project (where ``lakefile.lean`` lives).
            timeout: Maximum seconds to wait for the process.
            docker_config: Optional :class:`DockerConfig`.  When provided and
                enabled, the check runs inside a Docker container using the
                same image that the agent used, so the environment matches
                exactly.

        Returns:
            A :class:`LeanResult` describing the outcome.
        """
        cwd: str | None = project_dir

        if docker_config is not None and docker_config.enabled:
            abs_project = os.path.abspath(project_dir)
            cmd = [
                "docker", "run", "--rm",
                "--user", f"{os.getuid()}:{os.getgid()}",
                # Whole workspace → /task so sibling files and
                # subdirectories (needed by `import` in project-mode
                # tasks) resolve inside the container.
                "-v", f"{abs_project}:/task",
            ]
            # Host mathlib / .lake cache as a read-only overlay.
            lake_path = docker_config.lake_cache_path
            if lake_path and os.path.isdir(lake_path):
                cmd.extend(["-v", f"{os.path.abspath(lake_path)}:/task/.lake:ro"])
            # Writable overlay for per-task build artifacts; workspace.py
            # copies the pre-built build/ into .lake-build/ under Docker.
            lake_build_rw = os.path.join(abs_project, ".lake-build")
            if os.path.isdir(lake_build_rw):
                cmd.extend(["-v", f"{lake_build_rw}:/task/.lake/build"])
            cmd.extend([
                "-w", "/task",
                docker_config.image,
                "lake", "env", "lean", file_path,
            ])
            cwd = None
        else:
            cmd = ["lake", "env", self.lean_path, file_path]

        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return LeanResult(
                success=False,
                error_count=1,
                errors=["Lean check timed out"],
                compilation_error=False,
                timeout=True,
            )
        except FileNotFoundError as exc:
            return LeanResult(
                success=False,
                error_count=1,
                errors=[str(exc)],
                compilation_error=True,
                timeout=False,
            )

        combined_output = (proc.stdout or "") + (proc.stderr or "")

        # Parse errors
        error_pattern = re.compile(r"^(.+):(\d+):(\d+):\s*error:\s*(.+)$", re.MULTILINE)
        error_matches = error_pattern.findall(combined_output)
        errors = [
            f"{fname}:{line}:{col}: {msg}"
            for fname, line, col, msg in error_matches
        ]
        error_count = len(errors)

        # Also check for "unknown" compilation errors in stderr
        compilation_error = proc.returncode != 0 and error_count == 0

        success = proc.returncode == 0 and error_count == 0

        return LeanResult(
            success=success,
            error_count=error_count,
            errors=errors,
            compilation_error=compilation_error,
            timeout=False,
        )

    # ------------------------------------------------------------------
    # Axiom checking
    # ------------------------------------------------------------------

    @staticmethod
    def _find_axiom_script(project_dir: str) -> str | None:
        """Locate ``check_axioms_inline.sh`` inside a workspace."""
        for root in (".agents", ".claude"):
            skills_dir = os.path.join(project_dir, root, "skills")
            if not os.path.isdir(skills_dir):
                continue
            for name in os.listdir(skills_dir):
                candidate = os.path.join(skills_dir, name, "scripts", "check_axioms_inline.sh")
                if os.path.isfile(candidate):
                    return candidate
        return None

    def check_axioms(
        self,
        file_path: str,
        project_dir: str,
        timeout: int = 60,
        docker_config=None,
        extra_files: list[str] | None = None,
    ) -> AxiomResult:
        """Run ``check_axioms_inline.sh`` and return an :class:`AxiomResult`.

        Returns status "pass" if only standard axioms, "fail" if custom
        axioms are detected, "unknown" on timeout or any other error.

        Args:
            file_path: Primary Lean file to scan, relative to
                ``project_dir``.
            project_dir: Lake project root.
            extra_files: Additional Lean files (relative to
                ``project_dir``) to include in the axiom scan.  Used to
                recurse into submodules so declarations in split
                projects aren't silently skipped.
        """
        script = self._find_axiom_script(project_dir)
        if script is None:
            return AxiomResult(status="unknown", custom_axioms=[])

        abs_project = os.path.abspath(project_dir)

        # Deduplicate while preserving order; the shell script also dedupes
        # via realpath but doing it here keeps the command line short.
        seen: set[str] = set()
        rel_targets: list[str] = []
        for rel in [file_path, *(extra_files or [])]:
            if rel and rel not in seen:
                seen.add(rel)
                rel_targets.append(rel)

        if docker_config is not None and docker_config.enabled:
            # Script path relative to project dir → container /task path
            rel_script = os.path.relpath(script, abs_project)
            container_script = f"/task/{rel_script}"
            container_files = [f"/task/{rel}" for rel in rel_targets]
            cmd = [
                "docker", "run", "--rm",
                "--user", f"{os.getuid()}:{os.getgid()}",
                "-v", f"{abs_project}:/task",
            ]
            lake_path = docker_config.lake_cache_path
            if lake_path and os.path.isdir(lake_path):
                cmd.extend(["-v", f"{os.path.abspath(lake_path)}:/task/.lake:ro"])
            cmd.extend([
                "-w", "/task",
                docker_config.image,
                "bash", container_script, *container_files,
            ])
            cwd = None
        else:
            cmd = ["bash", script, *rel_targets]
            cwd = abs_project

        try:
            proc = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return AxiomResult(status="unknown", custom_axioms=[])
        except Exception:
            return AxiomResult(status="unknown", custom_axioms=[])

        # Parse non-standard axioms from output.
        # The script prints lines like:  ⚠ DeclName uses non-standard axiom: SomeAxiom
        custom: list[str] = []
        for line in (proc.stdout or "").splitlines():
            m = re.search(r"non-standard axiom:\s*(.+)", line)
            if m:
                axiom_name = re.sub(r"\x1b\[[0-9;]*m", "", m.group(1)).strip()
                if axiom_name and axiom_name not in custom:
                    custom.append(axiom_name)

        if proc.returncode == 0:
            return AxiomResult(status="pass", custom_axioms=[])
        elif custom:
            return AxiomResult(status="fail", custom_axioms=custom)
        else:
            # Non-zero exit but no axiom info parsed — could be build error etc.
            return AxiomResult(status="unknown", custom_axioms=[])

    # ------------------------------------------------------------------
    # Sorry counting
    # ------------------------------------------------------------------

    @staticmethod
    def count_sorries(file_path: str) -> int:
        """Count ``sorry`` occurrences in a Lean file (excluding comments).

        Delegates to :func:`~anonymous_prover.analysis.sorry_analyzer.analyze_sorries`.
        """
        from .sorry_analyzer import analyze_sorries

        return analyze_sorries(file_path)["total_sorries"]
