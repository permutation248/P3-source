"""Analyse ``sorry`` usage in Lean 4 source files."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

# Directories that never belong to the task itself and must be skipped during
# recursive scans: Lake build artefacts, VCS internals, vendored skills, etc.
_SKIP_DIRS = {
    ".lake",
    ".git",
    "build",
    "lake-packages",
    ".claude",
    ".agents",
    "__pycache__",
}

_RE_SORRY = re.compile(r"\bsorry\b")
_RE_BLOCK_COMMENT = re.compile(r"/-.*?-/", re.DOTALL)
_RE_LINE_COMMENT = re.compile(r"--.*$", re.MULTILINE)


def _find_sorry_lines(text: str) -> list[int]:
    """Return 1-based line numbers where ``sorry`` occurs outside comments."""
    cleaned = _RE_BLOCK_COMMENT.sub(
        lambda m: "\n" * m.group().count("\n"), text
    )
    lines: list[int] = []
    for line_no_0, line in enumerate(cleaned.splitlines()):
        line_stripped = _RE_LINE_COMMENT.sub("", line)
        if _RE_SORRY.search(line_stripped):
            lines.append(line_no_0 + 1)
    return lines


def _analyze_file(file_path: str) -> list[int]:
    try:
        text = Path(file_path).read_text(errors="replace")
    except OSError:
        return []
    return _find_sorry_lines(text)


def _iter_lean_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune in-place so os.walk skips the dirs entirely.
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            if name.endswith(".lean"):
                yield os.path.join(dirpath, name)


def analyze_sorries(path: str) -> dict[str, Any]:
    """Analyse a Lean 4 file or project directory for ``sorry`` tokens.

    When ``path`` is a single file, the function scans that file only
    (legacy behaviour).  When ``path`` is a directory, it walks every
    ``.lean`` file underneath it, skipping build and tooling directories
    (``.lake``, ``build``, ``.claude``, ``.agents``, ``lake-packages``,
    ``.git``, ``__pycache__``).

    Args:
        path: Absolute or relative path to a ``.lean`` file or project
            directory.

    Returns:
        A dict with keys:

        - ``total_sorries`` (int): Total number of sorry tokens found
          across all scanned files.
        - ``sorry_locations`` (list[int]): 1-based line numbers where
          sorry appears.  When multiple files are scanned, line numbers
          come from across the whole project; use ``sorries_by_file``
          for per-file breakdown.
        - ``sorries_by_file`` (dict[str, list[int]]): Maps each file
          path (as given, not canonicalised) that contains at least one
          sorry to its 1-based line numbers.  Only present for
          directory scans; single-file scans return an empty dict.
        - ``has_sorry`` (bool): Whether any sorry was found.
    """
    if os.path.isdir(path):
        by_file: dict[str, list[int]] = {}
        flat: list[int] = []
        for lean_file in _iter_lean_files(path):
            hits = _analyze_file(lean_file)
            if hits:
                by_file[lean_file] = hits
                flat.extend(hits)
        return {
            "total_sorries": len(flat),
            "sorry_locations": flat,
            "sorries_by_file": by_file,
            "has_sorry": len(flat) > 0,
        }

    # Single file path (or missing path — let the error surface as before).
    hits = _analyze_file(path) if os.path.isfile(path) else []
    if not os.path.isfile(path):
        # Preserve the pre-existing contract of raising on unreadable files
        # so callers can distinguish "file missing" from "file clean".
        Path(path).read_text()  # raises OSError
    return {
        "total_sorries": len(hits),
        "sorry_locations": hits,
        "sorries_by_file": {},
        "has_sorry": len(hits) > 0,
    }
