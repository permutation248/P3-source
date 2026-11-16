"""Task file discovery helpers shared by API and runners."""

from __future__ import annotations

import os
from typing import Literal

TasksMode = Literal["file", "project"]


def _is_task_file(path: str) -> bool:
    return (
        path.endswith(".lean")
        and not path.endswith("_Generated.lean")
        and os.path.basename(path).lower() != "lakefile.lean"
    )


def _direct_task_leans(directory: str) -> list[str]:
    try:
        entries = os.listdir(directory)
    except OSError:
        return []
    result = []
    for name in entries:
        full = os.path.join(directory, name)
        if os.path.isfile(full) and _is_task_file(full):
            result.append(full)
    return sorted(result)


_PROJECT_ENTRY_FALLBACKS = ("Task.lean", "Main.lean", "main.lean")


def _pick_project_entry(directory: str, lean_files: list[str]) -> str:
    """Pick a representative .lean file for a project directory.

    Prefers a file whose stem matches the directory name (the Lean
    convention for library entry points, e.g. ``Nom/Nom.lean``), then
    common entry names like ``Task.lean`` / ``Main.lean``, then the
    first sorted match.
    """
    base = os.path.basename(os.path.normpath(directory))
    for f in lean_files:
        if os.path.splitext(os.path.basename(f))[0] == base:
            return f
    for entry_name in _PROJECT_ENTRY_FALLBACKS:
        for f in lean_files:
            if os.path.basename(f) == entry_name:
                return f
    return lean_files[0]


def discover_task_files(tasks_dir: str, tasks_mode: TasksMode = "file") -> list[str]:
    """Discover task files for a dataset directory.

    Modes:
    - ``file``: every ``.lean`` file under the dataset, recursively. Each
      file is one task.
    - ``project``: every topmost directory that directly contains ``.lean``
      files. Each such directory is one task; discovery does not descend
      further once a project root is found. The returned path is a
      representative ``.lean`` file inside that directory — the runner
      uses it as the task entry point and copies its siblings into the
      workspace.

    Common exclusions: ``*_Generated.lean`` and ``lakefile.lean``.
    """
    if tasks_mode not in {"file", "project"}:
        raise ValueError(f"Unknown tasks_mode: {tasks_mode!r}")

    if not os.path.isdir(tasks_dir):
        return []

    if tasks_mode == "file":
        results: list[str] = []
        for dirpath, _dirnames, filenames in os.walk(tasks_dir):
            for name in filenames:
                full = os.path.join(dirpath, name)
                if _is_task_file(full):
                    results.append(full)
        return sorted(results)

    # project mode — topmost directories with direct .lean files.
    results = []

    def _walk(directory: str) -> None:
        direct = _direct_task_leans(directory)
        if direct:
            results.append(_pick_project_entry(directory, direct))
            return
        try:
            entries = sorted(os.listdir(directory))
        except OSError:
            return
        for name in entries:
            sub = os.path.join(directory, name)
            if os.path.isdir(sub):
                _walk(sub)

    _walk(tasks_dir)
    return sorted(results)


def count_tasks(tasks_dir: str, tasks_mode: TasksMode = "file") -> int:
    """Return discovered task count for ``tasks_dir`` under a mode."""
    return len(discover_task_files(tasks_dir, tasks_mode))
