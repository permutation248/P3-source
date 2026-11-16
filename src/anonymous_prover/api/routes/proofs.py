"""API routes for browsing proof artifacts."""

from __future__ import annotations

import json
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ...models.experiment import Experiment
from ..deps import get_db

router = APIRouter(prefix="/api/proofs", tags=["proofs"])


def _is_hidden_relpath(rel_path: str) -> bool:
    """Return True when any path component is dot-prefixed."""
    return any(part.startswith(".") for part in rel_path.split(os.sep) if part)


def _resolve_proofs_dir(experiment: Experiment) -> str | None:
    """Resolve the proofs directory for an experiment."""
    # Try explicit output_dir from config
    config_json = experiment.config_json
    if isinstance(config_json, str):
        try:
            config_json = json.loads(config_json)
        except (json.JSONDecodeError, TypeError):
            config_json = {}

    cfg = (config_json or {}).get("config", {})
    output_dir = cfg.get("output_dir")

    if not output_dir:
        # Reconstruct from config fields (must match ExperimentConfig.resolved_output_dir)
        name = cfg.get("name", "")
        mode = cfg.get("mode", "")
        model = cfg.get("agent", {}).get("model", "")
        if not (name and mode and model):
            return None
        output_dir = f"results/{name}--{mode}--{model}"

    proofs_dir = os.path.join(os.getcwd(), output_dir, "proofs")
    if os.path.isdir(proofs_dir):
        return proofs_dir
    return None


@router.get("/{experiment_id}/{task_name}")
def list_proof_files(
    experiment_id: int,
    task_name: str,
    db: Session = Depends(get_db),
) -> list[dict]:
    """List all proof files for a task."""
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    proofs_dir = _resolve_proofs_dir(experiment)
    if proofs_dir is None:
        return []

    task_dir = os.path.join(proofs_dir, task_name)
    if not os.path.isdir(task_dir):
        return []

    files = []
    for root, dirnames, filenames in os.walk(task_dir):
        # Prune hidden directories in-place.
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fname in sorted(filenames):
            if fname.startswith("."):
                continue
            full = os.path.join(root, fname)
            rel = os.path.relpath(full, task_dir)
            if _is_hidden_relpath(rel):
                continue
            files.append({"name": rel, "size": os.path.getsize(full)})
    return files


@router.get("/{experiment_id}/{task_name}/file")
def read_proof_file(
    experiment_id: int,
    task_name: str,
    path: str,
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    """Read the content of a specific proof file."""
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")

    proofs_dir = _resolve_proofs_dir(experiment)
    if proofs_dir is None:
        raise HTTPException(status_code=404, detail="Proofs directory not found")

    task_dir = os.path.join(proofs_dir, task_name)
    file_path = os.path.normpath(os.path.join(task_dir, path))
    rel_path = os.path.relpath(file_path, task_dir)

    # Prevent path traversal
    if not file_path.startswith(os.path.normpath(task_dir)):
        raise HTTPException(status_code=400, detail="Invalid file path")
    if _is_hidden_relpath(rel_path):
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        with open(file_path, "r", errors="replace") as f:
            content = f.read()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read file")

    return PlainTextResponse(content)
