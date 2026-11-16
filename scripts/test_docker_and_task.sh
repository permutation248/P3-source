#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

AGENT_TYPE="${AGENT_TYPE:-codex}"              # codex | claude-code
MODEL="${MODEL:-gpt-5.3-codex}"
MODE="${MODE:-auto}"                            # code | proof | auto
SKILLS_CONFIG="${SKILLS_CONFIG:-standard}"      # none | standard | extended | ...
IMAGE_STANDARD="${IMAGE_STANDARD:-anonymous-prover:standard}"
IMAGE_EXTENDED="${IMAGE_EXTENDED:-anonymous-prover:extended}"
if [[ -n "${IMAGE:-}" ]]; then
  SELECTED_IMAGE="$IMAGE"
elif [[ "$SKILLS_CONFIG" == "extended" ]]; then
  SELECTED_IMAGE="$IMAGE_EXTENDED"
else
  SELECTED_IMAGE="$IMAGE_STANDARD"
fi
TASKS_DIR="${TASKS_DIR:-Benchmarks/eBPF_mini/eBPF/Alu32Add}"
TASKS_MODE="${TASKS_MODE:-flat}"                # flat | project
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-420}"
MAX_COST_USD="${MAX_COST_USD:-2.0}"
EXP_NAME="${EXP_NAME:-DockerSmoke-$(date -u +%Y%m%dT%H%M%SZ)}"
OUTPUT_DIR="${OUTPUT_DIR:-results/${EXP_NAME}--${MODE}--${MODEL}}"

echo "[1/4] Checking prerequisites"
command -v docker >/dev/null 2>&1 || { echo "docker not found"; exit 1; }
if [[ ! -x ".venv/bin/anonymous-prover" ]]; then
  echo "missing CLI: .venv/bin/anonymous-prover"
  exit 1
fi
docker image inspect "$SELECTED_IMAGE" >/dev/null 2>&1 || {
  echo "docker image not found: $SELECTED_IMAGE"
  exit 1
}

echo "[2/4] Docker smoke check on image '$SELECTED_IMAGE'"
# Toolchain check (no network needed)
docker run --rm --network none "$SELECTED_IMAGE" /bin/bash -lc \
  "lean --version >/dev/null && lake --version >/dev/null"
echo "  toolchain OK"
# Pre-built Lean project check (no network needed)
docker run --rm --network none "$SELECTED_IMAGE" /bin/bash -lc \
  "test -f /task/Tacs.lean && test -d /task/.lake/build/lib && test -f /task/lakefile.toml"
echo "  pre-built project OK"
# lean-lsp-mcp check (needs network for uvx cache miss)
docker run --rm "$SELECTED_IMAGE" /bin/bash -lc \
  "uvx lean-lsp-mcp --help >/dev/null 2>&1"
echo "  lean-lsp-mcp OK"
echo "docker image smoke check passed"

echo "[3/4] Writing temporary experiment config"
TMP_CFG="$(mktemp /tmp/anonymous-prover-docker-smoke.XXXXXX.yaml)"
cat > "$TMP_CFG" <<EOF
name: ${EXP_NAME}
mode: ${MODE}
skills_config: ${SKILLS_CONFIG}
tasks_dir: ${TASKS_DIR}
tasks_mode: ${TASKS_MODE}
agent:
  type: ${AGENT_TYPE}
  model: ${MODEL}
  use_tap: false
docker:
  enabled: true
  image: ${SELECTED_IMAGE}
parallel: 1
task_timeout_seconds: ${TIMEOUT_SECONDS}
max_cost_usd: ${MAX_COST_USD}
force: true
persist_to_db: false
output_dir: ${OUTPUT_DIR}
EOF

echo "[4/4] Running single-task experiment"
.venv/bin/anonymous-prover run --config "$TMP_CFG"

SUMMARY_PATH="${OUTPUT_DIR}/summary.json"
if [[ ! -f "$SUMMARY_PATH" ]]; then
  echo "missing summary: $SUMMARY_PATH"
  exit 1
fi

echo
echo "Run finished."
echo "config : $TMP_CFG"
echo "output : $OUTPUT_DIR"
echo "summary: $SUMMARY_PATH"
echo
cat "$SUMMARY_PATH"
