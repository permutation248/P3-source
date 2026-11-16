#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ensure_lean_lsp_mcp.sh <workspace_dir> [--docker]

Checks/fixes workspace .mcp.json so lean-lsp-mcp has a valid LEAN_PROJECT_PATH.
Also runs lightweight local toolchain checks when not in docker mode.
EOF
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 2
fi

workspace_dir="$1"
docker_mode="false"
if [[ $# -eq 2 ]]; then
  if [[ "$2" != "--docker" ]]; then
    usage
    exit 2
  fi
  docker_mode="true"
fi

if [[ ! -d "$workspace_dir" ]]; then
  echo "workspace not found: $workspace_dir" >&2
  exit 1
fi

mcp_path="$workspace_dir/.mcp.json"
if [[ ! -f "$mcp_path" ]]; then
  echo ".mcp.json missing in workspace: $workspace_dir" >&2
  exit 1
fi

if [[ "$docker_mode" == "true" ]]; then
  expected_project_path="/task"
else
  expected_project_path="$workspace_dir"
fi

python3 - "$mcp_path" "$expected_project_path" <<'PY'
import json
import pathlib
import sys

mcp_path = pathlib.Path(sys.argv[1])
expected = sys.argv[2]

try:
    data = json.loads(mcp_path.read_text(encoding="utf-8"))
except Exception as exc:
    raise SystemExit(f"invalid .mcp.json: {exc}")

servers = data.get("mcpServers")
if not isinstance(servers, dict):
    raise SystemExit("invalid .mcp.json: missing mcpServers object")

lean = servers.get("lean-lsp")
if not isinstance(lean, dict):
    lean = {"command": "uvx", "args": ["lean-lsp-mcp", "--repl"]}
    servers["lean-lsp"] = lean

env = lean.get("env")
if not isinstance(env, dict):
    env = {}
    lean["env"] = env

changed = env.get("LEAN_PROJECT_PATH") != expected
env["LEAN_PROJECT_PATH"] = expected

if changed:
    mcp_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"updated LEAN_PROJECT_PATH={expected}")
else:
    print(f"LEAN_PROJECT_PATH already set: {expected}")
PY

if [[ "$docker_mode" == "false" ]]; then
  if ! command -v lake >/dev/null 2>&1; then
    echo "lake not found on PATH" >&2
    exit 1
  fi
  if ! command -v lean >/dev/null 2>&1; then
    echo "lean not found on PATH" >&2
    exit 1
  fi
  lake --version >/dev/null
  lean --version >/dev/null
  if command -v uvx >/dev/null 2>&1; then
    uvx lean-lsp-mcp --help >/dev/null 2>&1 || true
  fi
fi

echo "lean-lsp-mcp preflight OK: workspace=$workspace_dir docker=$docker_mode"
