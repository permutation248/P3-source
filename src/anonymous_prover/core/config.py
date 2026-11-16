"""Pydantic configuration models for Anonymous-Prover experiments."""

from __future__ import annotations

import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator

from anonymous_prover.core.enums import AgentType, ExperimentMode, SkillsConfig


class AgentConfig(BaseModel):
    """Configuration for the AI agent backend."""
    type: AgentType = AgentType.claude_code
    model: str = "sonnet-4-6"
    # ``claude-tap`` is an optional HTTP-trace wrapper. Off by default so
    # deployments without it (e.g., PAI-DSW) work out of the box; opt in
    # via YAML when you actually want trace collection.
    use_tap: bool = False
    tap_output_dir: str = "claude_traces"
    # Runtime-only; "api" | "miromind" | "subscription" | None. Resolved
    # per request from the X-Backend header, not persisted on the DB row.
    backend: Optional[str] = None


class LeanConfig(BaseModel):
    """Configuration for the Lean 4 toolchain."""
    timeout_seconds: int = 120
    lake_build: bool = True


def _default_docker_enabled() -> bool:
    """Docker-enabled by default, except when ``ANONYMOUS_DISABLE_DOCKER=1``.
    Used on hosts (e.g., PAI-DSW) where Docker-in-Docker is forbidden."""
    import os

    return os.environ.get("ANONYMOUS_DISABLE_DOCKER", "").lower() not in ("1", "true", "yes")


class DockerConfig(BaseModel):
    """Configuration for running agents inside Docker containers."""
    enabled: bool = Field(default_factory=_default_docker_enabled)
    image: str = "anonymous-prover"
    # Optional per-skills image overrides. When unset, falls back to `image`.
    image_standard: Optional[str] = None
    image_extended: Optional[str] = None
    lake_cache_path: Optional[str] = None  # defaults to {project_root}/.lake
    extra_docker_args: list[str] = Field(default_factory=list)
    # Set at runtime by ExperimentRunner to control Negate.lean visibility.
    skills_config: Optional[str] = None

    def resolve_image_for_skills(self, skills_config: str) -> str:
        """Return docker image name for the given skills config."""
        if skills_config == SkillsConfig.extended:
            return self.image_extended or self.image
        return self.image_standard or self.image


class ExperimentConfig(BaseModel):
    """Full configuration for a single experiment run."""

    name: str
    mode: ExperimentMode
    skills_config: SkillsConfig = SkillsConfig.none
    tasks_dir: str
    tasks_mode: str = "file"
    agent: AgentConfig = Field(default_factory=AgentConfig)
    lean: LeanConfig = Field(default_factory=LeanConfig)
    docker: DockerConfig = Field(default_factory=DockerConfig)
    parallel: int = 4
    task_timeout_seconds: int = 1800
    max_cost_usd: Optional[float] = None
    force: bool = False
    persist_to_db: bool = True
    output_dir: Optional[str] = None
    custom_prompt: Optional[str] = None

    @field_validator("parallel")
    @classmethod
    def _parallel_ge_1(cls, v: int) -> int:
        if v < 1:
            raise ValueError("parallel must be >= 1")
        return v

    @field_validator("task_timeout_seconds")
    @classmethod
    def _timeout_ge_10(cls, v: int) -> int:
        if v < 10:
            raise ValueError("task_timeout_seconds must be >= 10")
        return v

    @field_validator("tasks_mode")
    @classmethod
    def _tasks_mode_valid(cls, v: str) -> str:
        if v not in {"file", "project"}:
            raise ValueError("tasks_mode must be one of: file, project")
        return v

    # ------------------------------------------------------------------
    # Derived helpers
    # ------------------------------------------------------------------

    @property
    def resolved_output_dir(self) -> str:
        """Return the output directory, generating a default if not set."""
        if self.output_dir is not None:
            return self.output_dir
        # Cache on first call so timestamp is stable across accesses
        attr = "__resolved_output_dir"
        if not hasattr(self, attr):
            object.__setattr__(self, attr, f"results/{self.name}--{self.mode}--{self.agent.model}")
        return object.__getattribute__(self, attr)

    def to_config_json(self) -> dict:
        """Return a JSON-serialisable dict with config, timestamp, and hostname."""
        return {
            "config": self.model_dump(mode="json"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hostname": socket.gethostname(),
        }

    # ------------------------------------------------------------------
    # YAML serialisation
    # ------------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: str | Path) -> ExperimentConfig:
        """Load an ExperimentConfig from a YAML file."""
        with open(path, "r") as fh:
            data = yaml.safe_load(fh)
        return cls.model_validate(data)

    def to_yaml(self, path: str | Path) -> None:
        """Write this config to a YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as fh:
            yaml.dump(
                self.model_dump(mode="json"),
                fh,
                default_flow_style=False,
                sort_keys=False,
            )
