"""Anonymous-Prover: AI-assisted Lean 4 code generation and verification platform."""
__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Deployment auto-bootstrap
# ---------------------------------------------------------------------------
# Adjust the process env when we can tell we're running on a host that needs
# it, so the user doesn't have to source a shell script every time. Runs once
# at package import (before any config/AgentConfig/subprocess call). Each
# operation is a no-op if its target is already set, so existing correct
# configurations are never clobbered.

def _bootstrap_env() -> None:
    import os

    # Tools directory: whatever contains the persistent ``elan`` and ``uv``
    # installs. Override via ``ANONYMOUS_TOOLS_DIR`` when the default path
    # doesn't match your layout. Defaults match the documented DSW setup.
    tools_dir = os.environ.get("ANONYMOUS_TOOLS_DIR", "/opt/anonymous-prover/tools")

    # PAI-DSW (and similar k8s-hosted notebook runtimes) forbid Docker. We
    # detect DSW via its standard runtime directory and disable Docker mode
    # unless the operator explicitly opted back in.
    on_dsw = os.path.isdir("/etc/dsw")
    if on_dsw and "ANONYMOUS_DISABLE_DOCKER" not in os.environ:
        os.environ["ANONYMOUS_DISABLE_DOCKER"] = "1"

    # Prepend tool-bin dirs to PATH so subprocesses (lean, lake, uvx,
    # lean-lsp-mcp) resolve them even in non-interactive shells where
    # ~/.bashrc was never sourced.
    path = os.environ.get("PATH", "")
    parts = path.split(os.pathsep) if path else []
    prepended = False
    for bindir in (
        os.path.join(tools_dir, "elan", "bin"),
        os.path.join(tools_dir, "uv", "bin"),
    ):
        if os.path.isdir(bindir) and bindir not in parts:
            parts.insert(0, bindir)
            prepended = True
    if prepended:
        os.environ["PATH"] = os.pathsep.join(parts)


_bootstrap_env()
del _bootstrap_env
