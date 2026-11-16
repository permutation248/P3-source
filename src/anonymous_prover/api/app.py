"""FastAPI application factory for Anonymous-Prover."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)

from ..models.database import create_db_engine, create_session_factory, get_db_url, init_db
from ..models.experiment import Experiment
from .deps import configure
from .routes import comparisons, config, datasets, experiments, proofs, results, tasks
from .websocket import ws_router


def _recover_orphan_experiments(engine) -> None:
    """Mark experiments stuck in 'running' as failed on startup.

    The previous serve process may have crashed or been killed mid-run,
    leaving rows in 'running' that no in-process runner is tracking.
    Without recovery these experiments can never be restarted via the
    UI (the restart endpoint refuses to act on a running row).

    IMPORTANT: any docker containers from the previous process that
    are still executing for these experiments must be killed BEFORE
    flipping the DB row, otherwise the user could restart the same
    experiment concurrently and have two workers writing the same
    output files. Containers are tagged with the
    ``anonymous_experiment_id=<id>`` label by ``BaseAgent._wrap_in_docker``.
    """
    # Local import to avoid a circular import with routes.experiments,
    # which imports from this module's package.
    from .routes.experiments import _kill_experiment_containers

    import json

    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        orphans = session.query(Experiment).filter(Experiment.status == "running").all()
        if not orphans:
            return

        now = datetime.now(timezone.utc)
        recovered = 0
        skipped: list[tuple[int, str]] = []
        for exp in orphans:
            # 1. Parse stored config to determine whether this run is
            #    auto-recoverable. Auto-recovery requires both:
            #      a) the run was launched with docker enabled (so all
            #         workers live in containers, not host subprocesses)
            #      b) the run was launched under the labeled-container
            #         regime (`runner_features.labeled_containers=True`)
            #         — earlier runs without labels can't be located via
            #         `docker ps --filter label=...` so we cannot prove
            #         their workers are gone.
            try:
                blob = json.loads(exp.config_json or "{}")
            except json.JSONDecodeError:
                blob = {}
            cfg = blob.get("config") or {}
            docker_enabled = bool((cfg.get("docker") or {}).get("enabled"))
            labeled = bool(
                (blob.get("runner_features") or {}).get("labeled_containers")
            )
            if not docker_enabled:
                skipped.append((exp.id, "non-docker run, cannot prove workers gone"))
                continue
            if not labeled:
                skipped.append(
                    (exp.id, "pre-label run, cannot locate orphaned containers")
                )
                continue

            # 2. Attempt confirmed termination of any leftover containers.
            try:
                killed = _kill_experiment_containers(exp.id)
            except Exception:
                logger.exception(
                    "orphan recovery: kill raised for experiment %d", exp.id
                )
                killed = False
            if not killed:
                skipped.append((exp.id, "container termination unconfirmed"))
                continue

            # 3. Only after positive proof of cleanup, flip the DB row.
            exp.status = "failed"
            exp.completed_at = now
            recovered += 1

        if recovered:
            session.commit()
        if skipped:
            logger.warning(
                "orphan recovery: %d experiment(s) left in 'running' "
                "(restart blocked until manually resolved): %s",
                len(skipped), skipped,
            )
    finally:
        session.close()


def create_app(db_url: str | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    resolved_url = get_db_url(db_url)

    app = FastAPI(
        title="Anonymous-Prover",
        version="0.1.0",
        description="AI-assisted Lean 4 code generation and verification platform",
    )

    # CORS middleware for local development frontends
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Configure database
    configure(resolved_url)
    engine = create_db_engine(resolved_url)
    init_db(engine)

    # Reset any experiments left in 'running' by a previous serve crash
    _recover_orphan_experiments(engine)

    # Register routers
    app.include_router(experiments.router)
    app.include_router(results.router)
    app.include_router(comparisons.router)
    app.include_router(tasks.router)
    app.include_router(config.router)
    app.include_router(datasets.router)
    app.include_router(proofs.router)
    app.include_router(ws_router)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    return app
