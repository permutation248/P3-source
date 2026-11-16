"""WebSocket endpoint for streaming experiment progress."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter()

# In-memory progress store keyed by experiment_id
_progress: dict[int, dict] = {}


def update_progress(experiment_id: int, data: dict) -> None:
    """Update the in-memory progress dict for *experiment_id*."""
    _progress[experiment_id] = data


@ws_router.websocket("/ws/experiments/{experiment_id}/progress")
async def experiment_progress(websocket: WebSocket, experiment_id: int) -> None:
    """Stream progress updates for an experiment over WebSocket."""
    await websocket.accept()

    try:
        while True:
            data = _progress.get(experiment_id, {})
            await websocket.send_text(json.dumps(data))

            status = data.get("status", "")
            if status in ("completed", "failed"):
                # Clean up only when experiment is done
                _progress.pop(experiment_id, None)
                break

            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
