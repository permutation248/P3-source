"""API routes for experiments."""

from __future__ import annotations

import json
import logging
import os
import traceback
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Response
from sqlalchemy.orm import Session

from ...core.config import AgentConfig, ExperimentConfig, LeanConfig
from ...core.enums import AgentType, ExperimentMode, SkillsConfig
from ...core.oauth import oauth_available, oauth_display_path
from ...models.database import create_db_engine, create_session_factory, get_db_url
from ...models.experiment import Experiment
from ...models.schemas import ExperimentCreate, ExperimentResponse
from ...models.task_result import TaskResult
from ..deps import get_db
from ..websocket import update_progress

from ...notifications.email import send_experiment_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/experiments", tags=["experiments"])

# Registry of running experiment runners (experiment_id -> ExperimentRunner)
_running_experiments: dict[int, object] = {}


def _kill_experiment_containers(
    experiment_id: int,
    *,
    confirm_empty_passes: int = 2,
    deadline_seconds: float = 30.0,
    pass_interval_seconds: float = 0.5,
) -> bool:
    """`docker kill` every container labelled with this experiment id.

    Containers are launched with ``--label anonymous_experiment_id=<id>``
    by ``BaseAgent._wrap_in_docker``, so this is a reliable way to stop
    all in-flight work for an experiment regardless of host subprocess
    state.

    Termination is **race-safe**: a single ps/kill pass is not
    authoritative, because in the same process worker threads may be
    between the cancel-flag check and ``subprocess.Popen('docker run')``.
    To close that window we loop kill+ps until we observe
    ``confirm_empty_passes`` *consecutive* empty pass results, bounded
    by ``deadline_seconds``. Caller must already have set the runner's
    cancel flag so no fresh tasks are dispatched, otherwise the loop
    will never converge.

    Returns ``True`` only when ``confirm_empty_passes`` consecutive
    passes report no containers within the deadline. Returns ``False``
    on any uncertainty: docker CLI missing, ps/kill timeout or non-zero
    exit, or the deadline elapses while containers keep reappearing.
    """
    import subprocess
    import time

    def _list_containers() -> tuple[bool, list[str]]:
        try:
            ps = subprocess.run(
                [
                    "docker", "ps", "-q",
                    "--filter", f"label=anonymous_experiment_id={experiment_id}",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.warning("docker ps failed for experiment %d: %s", experiment_id, exc)
            return False, []
        if ps.returncode != 0:
            logger.warning(
                "docker ps returned %d for experiment %d: %s",
                ps.returncode, experiment_id, ps.stderr.strip(),
            )
            return False, []
        return True, [cid for cid in ps.stdout.split() if cid]

    def _kill(ids: list[str]) -> bool:
        try:
            kill = subprocess.run(
                ["docker", "kill", *ids],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.warning("docker kill failed for experiment %d: %s", experiment_id, exc)
            return False
        if kill.returncode != 0:
            # `docker kill` returns non-zero if any container in the
            # batch is already gone (race with --rm). That's not a real
            # failure for our purposes — the next ps pass will tell us
            # whether anything is still up. Only treat as failure if
            # *every* id is reported missing AND ps still shows others.
            logger.info(
                "docker kill returned %d for experiment %d (may be benign): %s",
                kill.returncode, experiment_id, kill.stderr.strip(),
            )
        return True

    deadline = time.monotonic() + deadline_seconds
    consecutive_empty = 0
    while time.monotonic() < deadline:
        ok, ids = _list_containers()
        if not ok:
            return False
        if not ids:
            consecutive_empty += 1
            if consecutive_empty >= confirm_empty_passes:
                logger.info(
                    "experiment %d: termination confirmed (%d consecutive empty passes)",
                    experiment_id, consecutive_empty,
                )
                return True
            time.sleep(pass_interval_seconds)
            continue

        consecutive_empty = 0
        logger.info(
            "experiment %d: killing %d container(s): %s",
            experiment_id, len(ids), ids,
        )
        if not _kill(ids):
            return False
        time.sleep(pass_interval_seconds)

    logger.warning(
        "experiment %d: termination NOT confirmed within %.1fs deadline",
        experiment_id, deadline_seconds,
    )
    return False


MIROMIND_ANTHROPIC_BASE_URL = "https://api.miromind.site"

_VALID_BACKENDS = {"api", "miromind", "subscription"}

# Auth-related env vars the runner may override per experiment. Captured at
# module load so operator-configured server-side credentials (the "baseline")
# survive across runs that temporarily override them. Without this snapshot,
# a previous experiment's override would leak into subsequent runs.
_AUTH_ENV_KEYS: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_BASE_URL",
    "OPENAI_API_KEY",
)
_AUTH_ENV_SNAPSHOT: dict[str, str | None] = {
    k: os.environ.get(k) for k in _AUTH_ENV_KEYS
}


def _restore_auth_env() -> None:
    """Reset auth env vars to the operator baseline captured at import."""
    for k, v in _AUTH_ENV_SNAPSHOT.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def _parse_use_docker(value: str | None) -> bool | None:
    """Parse the ``X-Use-Docker`` header into a tri-state.

    ``None`` means "header absent" — the caller hasn't expressed a preference,
    so the server falls back to its env-var default (``ANONYMOUS_DISABLE_DOCKER``
    read at ``DockerConfig`` construction). Only explicit truthy / falsy
    values override; anything else is 422.
    """
    if value is None:
        return None
    v = value.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    raise HTTPException(
        status_code=422,
        detail=(
            f"Unknown X-Use-Docker value {value!r}. Expected a boolean "
            "(true/false) — or omit the header to use the server default."
        ),
    )


def _normalize_backend(value: str | None) -> str | None:
    """Parse an incoming ``X-Backend`` header.

    Semantics:
      - **absent / empty** (``None`` or ``""``)   → ``None`` (= default path,
        the server uses its baseline env / OAuth).
      - **one of ``_VALID_BACKENDS``**            → that value.
      - **anything else**                         → 422.

    Treating unknown values as "default" would silently downgrade a
    misspelled header (``X-Backend: miro``) into baseline credentials —
    which might succeed against the operator's env-var key but run under
    the wrong routing. Fail loudly instead so the client learns.
    """
    if not value:
        return None
    v = value.strip().lower()
    if v in _VALID_BACKENDS:
        return v
    raise HTTPException(
        status_code=422,
        detail=(
            f"Unknown X-Backend value {value!r}. Expected one of: "
            f"{', '.join(sorted(_VALID_BACKENDS))} — or omit the header "
            "to use the server default."
        ),
    )


def _validate_backend_for_request(
    backend: str | None, agent_type: "AgentType"
) -> None:
    """Reject backend choices that the server can't actually satisfy.

    Guards against stale client state — e.g., a browser that remembers
    ``active_backend = "subscription"`` from a different deployment where
    OAuth was mounted, pointing at one where it isn't. Without the check
    the run would start, ``_apply_auth_env`` would clear env keys to let
    OAuth win, and the CLI would fail obscurely with "no credentials".
    Other backends (api/miromind) can legitimately run without server-side
    setup beyond optional baseline env vars.
    """
    if backend != "subscription" or oauth_available(agent_type):
        return
    family = "Codex" if agent_type == AgentType.codex else "Claude"
    raise HTTPException(
        status_code=422,
        detail=(
            f"Subscription backend selected for {family}, but no OAuth "
            f"credentials are mounted on the server ({oauth_display_path(agent_type)} "
            "is missing). Change the Active Backend in Settings to Default, "
            "API, or MiroMind, or ask the operator to mount the OAuth "
            "credential file."
        ),
    )


# Routing-only env deltas applied on top of the operator baseline. Each
# entry is (family, backend) → dict where a string value is assigned and
# ``None`` pops the variable. ``api_key`` is layered separately below so
# its presence doesn't leak across backends. Missing entries (e.g., codex
# + api/miromind) mean "routing baseline is unchanged".
_ROUTING_DELTAS: dict[tuple[str, str], dict[str, str | None]] = {
    ("claude", "miromind"):     {"ANTHROPIC_BASE_URL": MIROMIND_ANTHROPIC_BASE_URL},
    ("claude", "api"):          {"ANTHROPIC_BASE_URL": None},
    ("claude", "subscription"): {"ANTHROPIC_API_KEY": None, "ANTHROPIC_BASE_URL": None},
    ("codex",  "subscription"): {"OPENAI_API_KEY": None},
}

# Per-family env var that a ``backend``-compatible API key gets written to.
# ``subscription`` deliberately omitted — OAuth mustn't be shadowed by a key.
_API_KEY_ENV: dict[str, str] = {
    "claude": "ANTHROPIC_API_KEY",
    "codex":  "OPENAI_API_KEY",
}


def _apply_auth_env(
    *,
    agent_type: "AgentType",
    backend: str | None,
    api_key: str | None,
) -> None:
    """Deterministically set auth env vars for a single experiment run.

    ``backend`` is a *routing* choice (which BASE_URL, which codex
    ``model_provider`` block); ``api_key`` is an independent *credential*
    choice. If a caller picks a backend but supplies no key, the operator's
    baseline key stands — deployments commonly put the gateway-compatible
    key directly in ``ANTHROPIC_API_KEY`` / ``OPENAI_API_KEY`` on the
    server. Matching key to endpoint is the operator/user's responsibility.

    Always starts from the operator baseline so prior-run overrides can't
    leak across experiments.
    """
    _restore_auth_env()

    family = "codex" if agent_type == AgentType.codex else "claude"
    for k, v in _ROUTING_DELTAS.get((family, backend or ""), {}).items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

    # Per-request API key override — never attached to subscription runs.
    if api_key and backend != "subscription":
        os.environ[_API_KEY_ENV[family]] = api_key


def _resolve_agent_type(agent_type: str | None, model: str | None) -> AgentType:
    """Resolve agent type from model family and explicit value."""
    m = (model or "").strip().lower()
    if m.startswith("gpt-") or "codex" in m:
        return AgentType.codex

    if (agent_type or "").strip().lower() == AgentType.codex.value:
        return AgentType.codex

    return AgentType.claude_code


def _send_notification(**kwargs) -> None:
    """Send email notification, swallowing all errors."""
    try:
        send_experiment_email(**kwargs)
    except Exception:
        logger.debug("Email notification failed (non-critical)", exc_info=True)


def _clean_output_dir(experiment: Experiment) -> None:
    """Remove the experiment's output directory from disk."""
    import shutil

    config_blob = json.loads(experiment.config_json) if experiment.config_json else {}
    output_dir = config_blob.get("config", {}).get("output_dir")
    if not output_dir:
        cfg = config_blob.get("config", {})
        name = cfg.get("name", experiment.name or "")
        mode = cfg.get("mode", experiment.mode or "")
        model = cfg.get("agent", {}).get("model", experiment.model or "")
        if name and mode and model:
            output_dir = f"results/{name}--{mode}--{model}"
    if output_dir and os.path.isdir(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)
        logger.info("Cleaned output directory: %s", output_dir)


@router.get("", response_model=list[ExperimentResponse])
def list_experiments(
    mode: str | None = None,
    model: str | None = None,
    db: Session = Depends(get_db),
) -> list[Experiment]:
    """List all experiments, optionally filtered by mode and/or model."""
    query = db.query(Experiment)
    if mode is not None:
        query = query.filter(Experiment.mode == mode)
    if model is not None:
        query = query.filter(Experiment.model == model)
    return query.order_by(Experiment.created_at.desc()).all()


@router.post("", response_model=ExperimentResponse, status_code=201)
def create_experiment(
    data: ExperimentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(None),
    x_backend: str | None = Header(None),
    x_use_docker: str | None = Header(None),
) -> Experiment:
    """Create a new experiment and schedule it for background execution.

    The credential backend is *not* persisted on the experiment record —
    it's read from the ``X-Backend`` header per run, allowing the same
    experiment to be (re)run against different credential sources by
    changing the active backend in the frontend Settings.
    """
    resolved_agent_type = _resolve_agent_type(data.agent_type, data.model)
    normalized_backend = _normalize_backend(x_backend)
    _validate_backend_for_request(normalized_backend, resolved_agent_type)
    use_docker = _parse_use_docker(x_use_docker)
    experiment = Experiment(
        name=data.name,
        mode=data.mode,
        skills_config=data.skills_config,
        model=data.model,
        agent_type=resolved_agent_type.value,
        tasks_dir=data.tasks_dir,
        tasks_mode=data.tasks_mode,
        parallel=data.parallel,
        task_timeout_seconds=data.task_timeout_seconds,
        max_cost_usd=data.max_cost_usd,
        notify_email=data.notify_email,
        custom_prompt=data.custom_prompt,
        status="pending",
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)

    db_url = get_db_url()
    background_tasks.add_task(
        _run_experiment_background,
        experiment.id,
        db_url,
        api_key=x_api_key,
        backend=normalized_backend,
        use_docker=use_docker,
        model=data.model,
    )

    return experiment


@router.get("/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Get a single experiment by ID, with parsed JSON blobs."""
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return experiment.to_dict()


@router.post("/{experiment_id}/restart", response_model=ExperimentResponse)
def restart_experiment(
    experiment_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(None),
    x_backend: str | None = Header(None),
    x_use_docker: str | None = Header(None),
) -> dict:
    """Restart a completed/failed experiment: reset stats, delete old results, re-run."""
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if experiment.status == "running":
        raise HTTPException(status_code=409, detail="Experiment is already running")

    # Validate credential choice against current server state *before*
    # destroying any state — a rejected request must not wipe stats.
    resolved_agent_type = _resolve_agent_type(experiment.agent_type, experiment.model)
    normalized_backend = _normalize_backend(x_backend)
    _validate_backend_for_request(normalized_backend, resolved_agent_type)
    use_docker = _parse_use_docker(x_use_docker)

    # Delete old task results
    db.query(TaskResult).filter(TaskResult.experiment_id == experiment_id).delete()

    # Reset stats
    experiment.status = "pending"
    experiment.total_tasks = 0
    experiment.solved_count = 0
    experiment.solved_rate = 0.0
    experiment.avg_time_seconds = None
    experiment.avg_cost_usd = None
    experiment.total_cost_usd = None
    experiment.avg_turns = None
    experiment.summary_json = None
    experiment.started_at = None
    experiment.completed_at = None
    db.commit()
    db.refresh(experiment)

    # Clean old output files on disk so the runner doesn't skip tasks
    _clean_output_dir(experiment)

    # Re-run in background with the caller's current credential choice.
    db_url = get_db_url()
    background_tasks.add_task(
        _run_experiment_background,
        experiment.id,
        db_url,
        api_key=x_api_key,
        backend=normalized_backend,
        use_docker=use_docker,
        model=experiment.model,
    )

    return experiment.to_dict()


@router.post("/{experiment_id}/resume", response_model=ExperimentResponse)
def resume_experiment(
    experiment_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(None),
    x_backend: str | None = Header(None),
    x_use_docker: str | None = Header(None),
) -> dict:
    """Resume a completed/failed experiment without deleting old outputs/results."""
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if experiment.status == "running":
        raise HTTPException(status_code=409, detail="Experiment is already running")

    resolved_agent_type = _resolve_agent_type(experiment.agent_type, experiment.model)
    normalized_backend = _normalize_backend(x_backend)
    _validate_backend_for_request(normalized_backend, resolved_agent_type)
    use_docker = _parse_use_docker(x_use_docker)

    # Keep historical outputs and task_results rows; runner will skip tasks
    # that already have on-disk result files and continue unfinished tasks.
    experiment.status = "pending"
    experiment.summary_json = None
    experiment.started_at = None
    experiment.completed_at = None
    db.commit()
    db.refresh(experiment)

    db_url = get_db_url()
    background_tasks.add_task(
        _run_experiment_background,
        experiment.id,
        db_url,
        api_key=x_api_key,
        backend=normalized_backend,
        use_docker=use_docker,
        model=experiment.model,
    )

    return experiment.to_dict()


@router.delete("/{experiment_id}", status_code=200)
def delete_experiment(
    experiment_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Delete an experiment and all its task results."""
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if experiment.status == "running":
        raise HTTPException(status_code=409, detail="Cannot delete a running experiment. Stop it first.")
    _clean_output_dir(experiment)
    db.query(TaskResult).filter(TaskResult.experiment_id == experiment_id).delete()
    db.delete(experiment)
    db.commit()
    return {"deleted": experiment_id}


@router.post("/{experiment_id}/stop")
def stop_experiment(
    experiment_id: int,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    """Stop a running experiment."""
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if experiment is None:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if experiment.status != "running":
        raise HTTPException(status_code=409, detail=f"Experiment is not running (status={experiment.status})")

    # Inspect stored config to decide which termination strategy is
    # safe. Three regimes:
    #   * docker + labeled : authoritative kill via `docker ps --filter`
    #   * docker + pre-label: cannot prove cleanup; best-effort cancel
    #     scheduling and leave the row 'running' (non-restartable)
    #   * non-docker        : host subprocesses; rely on runner.cancel()
    try:
        blob = json.loads(experiment.config_json or "{}")
    except json.JSONDecodeError:
        blob = {}
    cfg = blob.get("config") or {}
    docker_enabled = bool((cfg.get("docker") or {}).get("enabled"))
    labeled = bool(
        (blob.get("runner_features") or {}).get("labeled_containers")
    )

    runner = _running_experiments.get(experiment_id)

    if docker_enabled and labeled:
        # 1. Set the cancel flag FIRST so no new tasks dispatch while
        #    we are draining containers.
        if runner is not None:
            runner.cancel()  # type: ignore[union-attr]
        # 2. Race-safe multi-pass kill (loops until two consecutive
        #    empty `docker ps` results, bounded by deadline). This
        #    closes the worker-thread / Popen race window.
        killed = _kill_experiment_containers(experiment_id)
        if not killed:
            # The cancel flag is already set so no fresh dispatches
            # will occur from this serve, but we cannot prove all
            # in-flight containers are gone. Leave the DB row as
            # 'running' so restart stays blocked until the operator
            # resolves docker state and retries.
            raise HTTPException(
                status_code=503,
                detail=(
                    "Could not confirm termination of worker containers "
                    f"for experiment {experiment_id}. Scheduling has been "
                    "halted but the experiment remains marked running; "
                    "resolve docker state and retry stop, or clean up "
                    "manually before restarting."
                ),
            )

    elif docker_enabled and not labeled:
        # Pre-label run. We cannot locate its containers via labels,
        # so we cannot *prove* termination. But we can still halt
        # scheduling in this process if a live runner is registered —
        # refusing outright would be a regression (long-running
        # experiments started on the previous version would become
        # impossible to stop and would keep consuming resources).
        #
        # Behaviour:
        #   * If a live runner exists → cancel its scheduling so no
        #     new tasks launch, return 202 Accepted explaining that
        #     in-flight containers must be cleaned up manually. DB
        #     stays 'running' (restart blocked) until the operator
        #     confirms cleanup.
        #   * If no live runner → there is nothing this serve can do;
        #     refuse with 409 so the operator handles it manually.
        if runner is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Experiment {experiment_id} was launched before "
                    "container labels were supported AND no live runner "
                    "is registered in this serve process. Cannot stop "
                    "automatically — `docker ps` / `docker kill` the "
                    "leftover containers manually and update the DB."
                ),
            )
        runner.cancel()  # type: ignore[union-attr]
        update_progress(
            experiment_id,
            {"status": "running", "warning": "scheduling halted; manual cleanup required"},
        )
        # 202 Accepted: action partially performed, further work needed.
        response.status_code = 202
        return {
            "status": "scheduling-halted",
            "experiment_id": experiment_id,
            "detail": (
                "Pre-label run: scheduling cancelled but in-flight "
                "containers cannot be located via labels. Stop them "
                "manually with `docker ps` / `docker kill`, then mark "
                "the experiment failed in the DB before restart."
            ),
        }

    else:
        # Non-docker run: workers are host subprocesses of this serve
        # process. runner.cancel() halts scheduling; in-flight Popens
        # are not currently tracked (TODO in base.py). For runs with no
        # registered runner there is no remaining worker in this
        # process, so marking failed is safe.
        if runner is not None:
            runner.cancel()  # type: ignore[union-attr]

    experiment.status = "failed"
    experiment.completed_at = datetime.now(timezone.utc)
    db.commit()

    update_progress(experiment_id, {"status": "failed", "error": "Stopped by user"})

    return {"status": "stopped", "experiment_id": experiment_id}


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------


def _run_experiment_background(
    experiment_id: int,
    db_url: str,
    *,
    api_key: str | None = None,
    backend: str | None = None,
    use_docker: bool | None = None,
    model: str | None = None,
) -> None:
    """Run an experiment in a background task. Credentials are passed in,
    not read from the experiment record."""
    from ...core.config import DockerConfig
    from ...runner.experiment_runner import ExperimentRunner

    engine = create_db_engine(db_url)
    session_factory = create_session_factory(engine)
    session = session_factory()

    try:
        experiment = session.query(Experiment).filter(Experiment.id == experiment_id).first()
        if experiment is None:
            logger.error("Experiment %d not found", experiment_id)
            return

        agent_type = _resolve_agent_type(experiment.agent_type, experiment.model)
        _apply_auth_env(
            agent_type=agent_type,
            backend=backend,
            api_key=api_key,
        )

        # Mark as running
        experiment.status = "running"
        experiment.started_at = datetime.now(timezone.utc)
        session.commit()

        # Build config from stored fields. ``use_docker=None`` ⇒ fall back
        # to ``DockerConfig``'s env-driven default (``ANONYMOUS_DISABLE_DOCKER``).
        docker_cfg = DockerConfig()
        if use_docker is not None:
            docker_cfg.enabled = use_docker

        config = ExperimentConfig(
            name=experiment.name,
            mode=ExperimentMode(experiment.mode),
            skills_config=SkillsConfig(experiment.skills_config or "none"),
            tasks_dir=experiment.tasks_dir or "",
            tasks_mode=experiment.tasks_mode or "file",
            agent=AgentConfig(
                type=agent_type,
                model=experiment.model or "sonnet-4-6",
                backend=backend,
            ),
            lean=LeanConfig(),
            docker=docker_cfg,
            parallel=experiment.parallel or 4,
            task_timeout_seconds=experiment.task_timeout_seconds or 1800,
            max_cost_usd=experiment.max_cost_usd,
            custom_prompt=experiment.custom_prompt,
        )
        # Stamp runner-feature flags so orphan recovery on a future
        # serve restart can prove this run was launched under the
        # labeled-container regime (and is therefore safe to clean up
        # via `docker kill --filter label=anonymous_experiment_id=<id>`).
        config_blob = config.to_config_json()
        config_blob["runner_features"] = {
            "labeled_containers": True,
        }
        experiment.config_json = json.dumps(config_blob)
        session.commit()

        project_root = os.getcwd()
        logger.info(
            "Starting experiment %d: tasks_dir=%r, tasks_mode=%r, skills_config=%r, cwd=%s",
            experiment_id, config.tasks_dir, config.tasks_mode, config.skills_config, project_root,
        )
        runner = ExperimentRunner(config, project_root, experiment_id=experiment_id)
        _running_experiments[experiment_id] = runner

        # Progress callback
        def progress_callback(
            completed: int, total: int, task_name: str, result: dict | None
        ) -> None:
            # Always persist total_tasks so the UI never shows a stale
            # 0/0 between runner startup and the first task completion.
            # The runner emits an initial (completed=0, result=None)
            # callback right after discovery — that path must commit too.
            need_commit = False
            if experiment.total_tasks != total:
                experiment.total_tasks = total
                need_commit = True

            if result is not None:
                task_result = TaskResult(
                    experiment_id=experiment_id,
                    task_name=task_name,
                    solved=result.get("solved", False),
                    sorry_count=result.get("sorry_count", 0),
                    error_count=result.get("error_count", 0),
                    compilation_error=result.get("compilation_error", False),
                    timeout=result.get("timeout", False),
                    total_time_seconds=result.get("total_time_seconds"),
                    total_tokens=result.get("total_tokens"),
                    input_tokens=result.get("input_tokens"),
                    output_tokens=result.get("output_tokens"),
                    cost_usd=result.get("cost_usd"),
                    cost_source=result.get("cost_source"),
                    total_turns=result.get("total_turns"),
                    mode=result.get("mode"),
                    result_json=json.dumps(result),
                )
                session.add(task_result)

                if result.get("solved", False):
                    experiment.solved_count = (experiment.solved_count or 0) + 1

                need_commit = True

            if need_commit:
                session.commit()

            update_progress(experiment_id, {
                "status": "running",
                "completed": completed,
                "total": total,
                "task_name": task_name,
                "solved_count": experiment.solved_count,
            })

        # Run experiment
        summary = runner.run(progress_callback=progress_callback)

        # Update experiment with final stats
        total = summary.get("total", 0)
        solved = summary.get("solved", 0)
        experiment.total_tasks = total
        experiment.solved_count = solved
        experiment.solved_rate = (solved / total * 100.0) if total > 0 else 0.0
        time_stats = summary.get("time_stats", {})
        cost_stats = summary.get("cost_stats", {})
        turn_stats = summary.get("turn_stats", {})
        experiment.avg_time_seconds = time_stats.get("avg")
        experiment.avg_cost_usd = cost_stats.get("avg")
        experiment.total_cost_usd = cost_stats.get("total")
        experiment.avg_turns = turn_stats.get("avg")
        experiment.summary_json = json.dumps(summary)
        experiment.status = "completed"
        experiment.completed_at = datetime.now(timezone.utc)
        session.commit()

        update_progress(experiment_id, {
            "status": "completed",
            "completed": total,
            "total": total,
            "solved_count": solved,
        })

        # Send email notification with full report
        _send_notification(
            experiment_name=experiment.name,
            status="completed",
            total_tasks=total,
            solved_count=solved,
            solved_rate=experiment.solved_rate or 0.0,
            avg_time_seconds=experiment.avg_time_seconds,
            total_cost_usd=experiment.total_cost_usd,
            avg_turns=experiment.avg_turns,
            started_at=experiment.started_at.isoformat() if experiment.started_at else None,
            completed_at=experiment.completed_at.isoformat() if experiment.completed_at else None,
            recipient=experiment.notify_email,
            summary=summary,
        )

    except Exception as exc:
        logger.exception("Experiment %d failed: %s", experiment_id, exc)
        try:
            experiment = (
                session.query(Experiment).filter(Experiment.id == experiment_id).first()
            )
            if experiment is not None:
                experiment.status = "failed"
                experiment.summary_json = json.dumps({
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                })
                experiment.completed_at = datetime.now(timezone.utc)
                session.commit()
        except Exception:
            logger.exception("Failed to update experiment %d status", experiment_id)

        update_progress(experiment_id, {
            "status": "failed",
            "error": str(exc),
        })

        # Send failure email
        _send_notification(
            experiment_name=experiment.name if experiment else f"ID#{experiment_id}",
            status="failed",
            total_tasks=experiment.total_tasks if experiment else 0,
            solved_count=experiment.solved_count if experiment else 0,
            solved_rate=experiment.solved_rate if experiment else 0.0,
            avg_time_seconds=None,
            total_cost_usd=None,
            avg_turns=None,
            started_at=experiment.started_at.isoformat() if experiment and experiment.started_at else None,
            completed_at=experiment.completed_at.isoformat() if experiment and experiment.completed_at else None,
            error=str(exc),
            recipient=experiment.notify_email if experiment else None,
        )
    finally:
        _running_experiments.pop(experiment_id, None)
        session.close()
