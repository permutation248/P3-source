# Lean4 verification environment for BPF benchmark tasks
#
# Includes Lean4 via elan, Claude Code CLI, Codex CLI, and lean-lsp-mcp server.
#
# Build:
#   docker build -f docker/lean4.Dockerfile --build-arg SKILLS_PROFILE=standard -t anonymous-prover:standard .
#   docker build -f docker/lean4.Dockerfile --build-arg SKILLS_PROFILE=extended -t anonymous-prover:extended .
#
# Run (task runner handles this automatically when docker.enabled=true):
#   docker run --rm \
#     -e CLAUDE_CODE_OAUTH_TOKEN="$TOKEN" \
#     -v ./workspaces/active/my_task:/task \
#     -v ./.lake/packages:/task/.lake/packages:ro \
#     anonymous-prover \
#     claude -p "..." --output-format stream-json --dangerously-skip-permissions
#
FROM ubuntu:24.04
ARG SKILLS_PROFILE=standard

# --- Root: system dependencies ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        git \
        ca-certificates \
        build-essential \
        python3 \
        ripgrep \
        openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Install uv (Python package manager, needed for lean-lsp-mcp)
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh

# Install Node.js + Claude Code CLI + Codex CLI + Gemini CLI
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g @anthropic-ai/claude-code @google/gemini-cli @openai/codex \
    && rm -rf /var/lib/apt/lists/*

# Create solver user with host UID/GID so bind-mounted files have correct ownership.
ARG SOLVER_UID=1000
ARG SOLVER_GID=1000
RUN userdel -r ubuntu 2>/dev/null || true \
    && groupadd -o -g ${SOLVER_GID} solver \
    && useradd -o -u ${SOLVER_UID} -g solver -m -s /bin/bash solver

# --- Solver user: install elan/lean and pre-cache lean-lsp-mcp ---
USER solver

COPY --chown=solver:solver lean-toolchain /tmp/lean-toolchain
RUN curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
    | bash -s -- -y --default-toolchain "$(cat /tmp/lean-toolchain)"
ENV PATH="/home/solver/.local/bin:/home/solver/.elan/bin:${PATH}"
ENV ELAN_HOME="/home/solver/.elan"

RUN lean --version && lake --version

# Pre-cache lean-lsp-mcp and claude-tap so uvx doesn't need network at runtime
ENV UV_CACHE_DIR="/home/solver/.cache/uv"
RUN uvx lean-lsp-mcp --help 2>/dev/null || true
RUN uv tool install claude-tap

# Pre-install lean4-skills plugin into a seed directory.
RUN claude plugin marketplace add cameronfreer/lean4-skills 2>&1 || true \
    && claude plugin install lean4@lean4-skills 2>&1 || true \
    && mkdir -p /home/solver/.plugin-seed \
    && cp -a /home/solver/.claude/plugins/* /home/solver/.plugin-seed/ 2>/dev/null || true

# --- Performance & headless env vars ---
ENV NODE_OPTIONS="--max-old-space-size=4096"
ENV CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
ENV DISABLE_AUTOUPDATER=1
ENV CLAUDE_CODE_PLUGIN_SEED_DIR="/home/solver/.plugin-seed"

# Pre-create runtime config dirs and clean up plugin install artifacts.
RUN mkdir -p /home/solver/.claude /home/solver/.gemini /home/solver/.codex \
    && rm -f /home/solver/.claude.json \
    && rm -rf /home/solver/.claude/backups

# --- Pre-built Lean project ---
# Copy project config, shared library, AND the pre-built .lake directory
# (contains mathlib, quickcheck, and all olean artifacts from the host).
# This avoids cloning private repos or compiling mathlib during image build.
# Rebuild the image when deps or Tacs/ change (see docs/docker-strategy.md).
COPY --chown=solver:solver lakefile.toml lean-toolchain lake-manifest.json /task/
COPY --chown=solver:solver Tacs.lean /task/Tacs.lean
COPY --chown=solver:solver Tacs/ /task/Tacs/
COPY --chown=solver:solver .lake/ /task/.lake/
WORKDIR /task
# Keep Negate only in extended profile.
RUN if [ "$SKILLS_PROFILE" != "extended" ]; then rm -f /task/Tacs/Negate.lean; fi
# Verify the pre-built artifacts are usable (fast no-op if everything is cached).
RUN lake build Tacs
