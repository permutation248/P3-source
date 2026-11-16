"""API routes for dataset management (upload + listing)."""

from __future__ import annotations

import json
import os
import shutil

from fastapi import APIRouter, HTTPException, Request
from starlette.datastructures import UploadFile

from ...core.task_discovery import count_tasks

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

DATASETS_ROOT = os.path.join(os.getcwd(), "Benchmarks")
DATASET_META_FILENAME = ".anonymous_dataset.json"

# Starlette's default multipart limits (1000 files/fields, 1 MB per part) are
# too low for real Lean projects (Mathlib-style folders routinely exceed this).
UPLOAD_MAX_FILES = 50_000
UPLOAD_MAX_FIELDS = 50_000
UPLOAD_MAX_PART_SIZE = 32 * 1024 * 1024  # 32 MB per file part


def _meta_path(dataset_dir: str) -> str:
    return os.path.join(dataset_dir, DATASET_META_FILENAME)


def _save_dataset_mode(dataset_dir: str, tasks_mode: str) -> None:
    with open(_meta_path(dataset_dir), "w") as f:
        json.dump({"tasks_mode": tasks_mode}, f)


def _load_dataset_mode(dataset_dir: str) -> str | None:
    path = _meta_path(dataset_dir)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r") as f:
            obj = json.load(f)
        mode = str(obj.get("tasks_mode", "")).strip().lower()
        if mode == "flat":
            mode = "file"
        if mode in {"file", "project"}:
            return mode
    except Exception:
        return None
    return None


def _scan_datasets() -> list[dict]:
    """Return metadata for every dataset directory under Benchmarks/."""
    if not os.path.isdir(DATASETS_ROOT):
        return []
    datasets = []
    for entry in sorted(os.listdir(DATASETS_ROOT)):
        suite_dir = os.path.join(DATASETS_ROOT, entry)
        if not os.path.isdir(suite_dir):
            continue
        file_count = count_tasks(suite_dir, "file")
        project_count = count_tasks(suite_dir, "project")
        preferred_mode = _load_dataset_mode(suite_dir)
        if preferred_mode is None:
            preferred_mode = "project" if project_count > 0 else "file"
        preferred_count = project_count if preferred_mode == "project" else file_count
        datasets.append({
            "name": entry,
            "path": f"Benchmarks/{entry}",
            "tasks_mode": preferred_mode,
            "task_count": preferred_count,
            "task_count_file": file_count,
            "task_count_project": project_count,
        })
    return datasets


def _sanitize_upload_relpath(filename: str) -> str:
    path = filename.replace("\\", "/").lstrip("/")
    if not path:
        raise ValueError("Empty filename")
    parts = path.split("/")
    if any(p in {"", ".", ".."} for p in parts):
        raise ValueError("Invalid filename path")
    return "/".join(parts)


def _is_hidden_upload_path(path: str) -> bool:
    normalized = path.replace("\\", "/").lstrip("/")
    if not normalized:
        return False
    parts = normalized.split("/")
    return any(part.startswith(".") for part in parts)


@router.get("")
def list_datasets() -> list[dict]:
    """List all available datasets."""
    return _scan_datasets()


@router.post("")
async def upload_dataset(request: Request) -> dict:
    """Upload dataset files (entire folder content) to create a new dataset.

    Parses the multipart form manually so we can raise Starlette's default
    1000-file limit — real Lean projects easily exceed that.
    """
    form = await request.form(
        max_files=UPLOAD_MAX_FILES,
        max_fields=UPLOAD_MAX_FIELDS,
        max_part_size=UPLOAD_MAX_PART_SIZE,
    )

    name = str(form.get("name", "")).strip()
    tasks_mode = str(form.get("tasks_mode", "file")).strip() or "file"
    files: list[UploadFile] = [
        v for v in form.getlist("files") if isinstance(v, UploadFile)
    ]

    # Validate name
    safe_name = name.replace(" ", "_")
    if not safe_name or "/" in safe_name or "\\" in safe_name or ".." in safe_name:
        raise HTTPException(status_code=400, detail="Invalid dataset name")
    if tasks_mode not in {"file", "project"}:
        raise HTTPException(status_code=400, detail="tasks_mode must be one of: file, project")

    dataset_dir = os.path.join(DATASETS_ROOT, safe_name)

    # Check if exists
    if os.path.isdir(dataset_dir):
        raise HTTPException(status_code=409, detail=f"Dataset '{safe_name}' already exists")

    # Validate files
    valid_files = [f for f in files if f.filename]
    if not valid_files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Create directory and save files
    os.makedirs(dataset_dir, exist_ok=True)
    saved = []
    try:
        for f in valid_files:
            raw_name = str(f.filename)
            if _is_hidden_upload_path(raw_name):
                continue
            rel = _sanitize_upload_relpath(raw_name)
            dest = os.path.normpath(os.path.join(dataset_dir, rel))
            if os.path.commonpath([dataset_dir, dest]) != os.path.normpath(dataset_dir):
                raise ValueError("Invalid filename path")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as out:
                shutil.copyfileobj(f.file, out)
            saved.append(rel)
        if not saved:
            raise HTTPException(status_code=400, detail="No non-hidden files provided")
        _save_dataset_mode(dataset_dir, tasks_mode)
    except ValueError as exc:
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception:
        # Cleanup on failure
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail="Failed to save files")

    file_count = count_tasks(dataset_dir, "file")
    project_count = count_tasks(dataset_dir, "project")
    preferred_count = project_count if tasks_mode == "project" else file_count
    return {
        "name": safe_name,
        "path": f"Benchmarks/{safe_name}",
        "tasks_mode": tasks_mode,
        "task_count": preferred_count,
        "task_count_file": file_count,
        "task_count_project": project_count,
        "files": saved,
    }


@router.delete("/{name}")
def delete_dataset(name: str) -> dict:
    """Delete a dataset directory."""
    dataset_dir = os.path.join(DATASETS_ROOT, name)
    if not os.path.isdir(dataset_dir):
        raise HTTPException(status_code=404, detail=f"Dataset '{name}' not found")
    shutil.rmtree(dataset_dir)
    return {"deleted": name}
