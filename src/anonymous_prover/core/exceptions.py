"""Exception hierarchy for Anonymous-Prover."""


class AnonymousProverError(Exception):
    """Base exception for all Anonymous-Prover errors."""


class ConfigError(AnonymousProverError):
    """Invalid or missing configuration."""


class LeanNotFoundError(AnonymousProverError):
    """Lean 4 executable could not be located."""


class LeanTimeoutError(AnonymousProverError):
    """Lean 4 build or check exceeded the timeout."""


class AgentError(AnonymousProverError):
    """Error communicating with or running the AI agent."""


class ExtractionError(AnonymousProverError):
    """Failed to extract results from agent output."""


class WorkspaceError(AnonymousProverError):
    """Error setting up or tearing down a task workspace."""


class DatabaseError(AnonymousProverError):
    """Database connection or query error."""
