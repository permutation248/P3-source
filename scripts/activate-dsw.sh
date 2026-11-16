#!/usr/bin/env bash
# Source this file in PAI-DSW (or any non-Docker host) before launching
# Anonymous-Prover. Puts the persistent toolchain on PATH and tells the
# harness to skip ``docker run``.
#
#   source /path/to/anonymous-prover/scripts/activate-dsw.sh

# Persistent tool locations (CPFS-backed, survive pod restart).
_ANONYMOUS_TOOLS="${ANONYMOUS_TOOLS_DIR:-/opt/anonymous-prover/tools}"

# Lean toolchain via elan.
export ELAN_HOME="$_ANONYMOUS_TOOLS/elan"

# Prepend tool dirs only if not already there (idempotent).
for _dir in "$ELAN_HOME/bin" "$_ANONYMOUS_TOOLS/uv/bin"; do
  case ":$PATH:" in
    *":$_dir:"*) ;;
    *) PATH="$_dir:$PATH" ;;
  esac
done
export PATH
unset _dir _ANONYMOUS_TOOLS

# Skip Docker. DockerConfig reads this env var (core/config.py) and
# defaults ``enabled`` to False when set. DSW forbids Docker-in-Docker.
export ANONYMOUS_DISABLE_DOCKER=1

echo "Anonymous-Prover DSW environment activated:"
for _cmd in elan lean lake uv uvx claude codex; do
  _path=$(command -v "$_cmd" 2>/dev/null)
  if [ -n "$_path" ]; then
    printf "  %-7s %s\n" "$_cmd" "$_path"
  else
    printf "  %-7s MISSING\n" "$_cmd"
  fi
done
unset _cmd _path
echo "  docker  DISABLED (ANONYMOUS_DISABLE_DOCKER=1)"
