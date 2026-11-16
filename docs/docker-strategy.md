# Docker Strategy for Anonymous-Prover

## Problem Statement

The eBPF-GPT-5.3-Codex experiment (51 tasks) scored **0/51 solved**, even though some tasks had `sorry_count=0` and `error_count=0`. Root cause analysis revealed two Docker-related framework bugs:

1. **Post-hoc verification runs on the host, not in Docker.** After the agent container exits, the host workspace loses access to `.lake/packages` (mathlib) because it was a Docker bind mount. The extractor runs `lake env lean Task.lean` on the host, which fails with `error: unknown module prefix 'Mathlib'`. This sets `compilation_error=true` for **every** Docker-mode task, making it impossible to ever report `solved=true`.

2. **Shared directories use absolute symlinks that don't resolve inside Docker.** `workspace.py` creates `Tacs -> /home/.../lean-tacs/Tacs` as an absolute symlink. The container only has `/task` mounted, so the symlink target doesn't exist. `lake build` fails with `no such file or directory: /task/Tacs.lean`, forcing the model to waste turns discovering and working around this.

### Evidence

```
# summary.json
{ "total": 51, "solved": 0, "failed": 51 }

# Example: Jmp32Jset — model produced valid proof, sorry_count=0, error_count=0
# But compilation_error=true because host-side verification failed
{ "sorry_count": 0, "error_count": 0, "compilation_error": true, "solved": false }

# Agent's own verification inside Docker succeeded:
# lake env lean Task.lean → only unused variable warnings, no errors
```

## Current Architecture (Broken)

```
Host                                    Docker Container
─────────────────────────────────────   ───────────────────────────
workspace.py                            
├─ symlink Tacs -> /home/.../Tacs       /task/Tacs -> /home/.../Tacs  ✗ broken
├─ skip .lake symlink (Docker mode)     /task/.lake/packages ← mount from host
├─ copy lakefile.toml etc.              
│                                       
base.py _wrap_in_docker                 
├─ mount workspace -> /task             agent runs here
├─ mount .lake/packages:ro              ← works during execution
├─ (Tacs not mounted)                   ← lake build fails
│                                       
│                                       container exits, mounts disappear
│                                       
default.py extractor                    
├─ lake env lean Task.lean (ON HOST)    
├─ .lake/packages gone → FAIL           ← every task fails here
└─ compilation_error = true             
```

**Root cause**: Docker execution and host-side verification share workspace state, but their environments differ after the container exits.

## Proposed Architecture: Self-Contained Image

**Principle**: The Docker image contains all immutable Lean dependencies pre-built. Only per-task files are mounted at runtime. Verification runs inside Docker too. Host and Docker paths never cross.

### Lakefile policy: image overrides task

> **All tasks run against the project's `lakefile.toml`, never the task's own `lakefile.lean`.**

Benchmark task directories often ship their own `lakefile.lean` with different dependency versions. If this file were mounted into the container, Lake would prefer `.lean` over `.toml`, breaking the pre-compiled `.lake` cache and causing dependency mismatches.

To prevent this:
- **Docker mode**: `lakefile.lean` is in the `_IMAGE_PROVIDED` exclusion set — it is never mounted, even if present in the workspace. The image's `lakefile.toml` is authoritative.
- **Local mode**: `workspace.py` copies the project root's `lakefile.toml` into the workspace and deletes any task-provided `lakefile.lean`.

This ensures all tasks run in an identical, reproducible environment regardless of what their source directory contains.

### What goes INTO the image (build-time)

| Content | Path in image | Notes |
|---------|---------------|-------|
| Lean toolchain, CLI tools | `/home/solver/.elan/` | Already present |
| `lakefile.toml` | `/task/lakefile.toml` | Project build config |
| `lean-toolchain` | `/task/lean-toolchain` | Toolchain version pin |
| `lake-manifest.json` | `/task/lake-manifest.json` | Dependency lock |
| `Tacs.lean` | `/task/Tacs.lean` | Library root (`import Tacs.CountNodes` etc.) |
| `Tacs/` | `/task/Tacs/` | Shared Lean library modules |
| `.lake/` | `/task/.lake/` | **Pre-compiled** mathlib + Tacs |

### What is MOUNTED at runtime (per-task)

| Host path | Container path | Mode | Content |
|-----------|----------------|------|---------|
| `workspace/Task.lean` | `/task/Task.lean` | rw | Task file (agent edits this) |
| `workspace/.agents/` | `/task/.agents/` | ro | Skill configs for Codex |
| `workspace/.claude/` | `/task/.claude/` | ro | Skill configs for Claude |
| `workspace/.mcp.json` | `/task/.mcp.json` | ro | MCP server config |
| `workspace/.claude.json` | `/home/solver/.claude.json` | rw | Claude state |
| `{output_dir}/` (abs path) | same abs path | rw | JSONL stream output (host path passed through so agent writes directly to host) |
| `~/.codex/auth.json` | `/home/solver/.codex/auth.json` | ro | Credentials |
| `~/.claude/.credentials.json` | `/home/solver/.claude/.credentials.json` | ro | Credentials |

### Lifecycle

```
1. Image Build (one-time, or when deps change)
   ┌─────────────────────────────────────────┐
   │ COPY lakefile.toml, lean-toolchain,     │
   │      lake-manifest.json,               │
   │      Tacs.lean, Tacs/,                 │
   │      .lake/ (pre-built from host)      │
   │ RUN  lake build Tacs  (verify, ~9s)    │
   │ → Image has /task/.lake/ fully built   │
   └─────────────────────────────────────────┘

2. Workspace Preparation (per-task, on host)
   ┌─────────────────────────────────────────┐
   │ workspace.py:                           │
   │ ├─ Copy task file                       │
   │ ├─ Copy skills (.agents/, .claude/)     │
   │ ├─ Write .mcp.json                      │
   │ ├─ (NO symlinks, NO lakefile copy)      │
   │ └─ Done — workspace is minimal          │
   └─────────────────────────────────────────┘

3. Agent Execution (in Docker)
   ┌─────────────────────────────────────────┐
   │ docker run --rm                         │
   │   -v Task.lean:/task/Task.lean          │
   │   -v .agents:/task/.agents:ro           │
   │   -v .claude:/task/.claude:ro           │
   │   ...                                   │
   │   anonymous-prover                        │
   │   codex exec ... "prompt"               │
   │                                         │
   │ Agent sees complete Lean project:       │
   │   /task/.lake/     ← from image         │
   │   /task/Tacs/      ← from image         │
   │   /task/Task.lean  ← mounted            │
   │   lake build  ✓                         │
   │   lake env lean Task.lean  ✓            │
   └─────────────────────────────────────────┘

4. Verification (in Docker, same image)
   ┌─────────────────────────────────────────┐
   │ docker run --rm                         │
   │   -v Task.lean:/task/Task.lean          │
   │   anonymous-prover                        │
   │   lake env lean Task.lean               │
   │                                         │
   │ Same image, same env as agent.          │
   │ Parse stdout/stderr on host.            │
   └─────────────────────────────────────────┘

5. Result Extraction (on host)
   ┌─────────────────────────────────────────┐
   │ Parse stream.jsonl (tokens, cost, etc.) │
   │ Parse verification stdout (errors)      │
   │ Count sorries in Task.lean              │
   │ Write result.json                       │
   └─────────────────────────────────────────┘

6. Cleanup
   └─ rm -rf workspace
```

### Local Mode (unchanged)

```
workspace.py:
├─ symlink Tacs -> project_root/Tacs
├─ symlink .lake -> project_root/.lake
├─ copy lakefile.toml, lean-toolchain, lake-manifest.json
│
agent runs locally
│
extractor runs lake env lean locally (symlinks resolve on host)
```

Docker and local are two fully independent code paths. No shared assumptions about filesystem state.

## Code Changes Required

### `docker/lean4.Dockerfile`

Add pre-compilation of Lean project dependencies:

```dockerfile
# --- Pre-built Lean project ---
COPY --chown=solver:solver lakefile.toml lean-toolchain lake-manifest.json /task/
COPY --chown=solver:solver Tacs.lean /task/Tacs.lean
COPY --chown=solver:solver Tacs/ /task/Tacs/
COPY --chown=solver:solver .lake/ /task/.lake/
WORKDIR /task
RUN lake build Tacs
```

**Notes**:
- `lean_lib Tacs` (defined in `lakefile.toml`) requires the root file `Tacs.lean` as the library entry point. Both `Tacs.lean` and `Tacs/` must be copied.
- `.lake/` is copied directly from the host (pre-built mathlib, quickcheck, etc.), not cloned during build. This is necessary because `quickcheck` is a private repo that cannot be cloned without credentials inside Docker build.
- `RUN lake build Tacs` is a fast verification step (~9s) that confirms the copied oleans are usable. It does NOT recompile mathlib.
- A `.dockerignore` file excludes `.git`, `results/`, `.venv/`, etc. from the build context. `.lake/` is intentionally **included**.

Image size will increase (~5-8 GB for mathlib build artifacts). This is a one-time cost; all tasks reuse the same image layer.

Note on `.lake/build` writability: The agent needs to write to `.lake/build/` when compiling `Task.lean` (produces `.olean` files). Docker's overlay filesystem handles this naturally — the container can write on top of the image layer via copy-on-write, and these writes are discarded when the container exits (`--rm`). **Do NOT mount a tmpfs over `/task/.lake/build/`** — that would hide all pre-compiled mathlib `.olean` files.

### `src/anonymous_prover/agents/base.py` — `_wrap_in_docker`

Replace whole-workspace mount with per-file mounts:

```python
# OLD: mount entire workspace, then overlay .lake
docker_cmd.extend(["-v", f"{os.path.abspath(workdir)}:/task"])
# ... complex .lake mount logic ...

# NEW: mount only per-task files, image provides everything else
abs_ws = os.path.abspath(workdir)

# Files already baked into the image — never mount these
_IMAGE_PROVIDED = {
    "Tacs", "Tacs.lean", ".lake",
    "lakefile.toml", "lean-toolchain", "lake-manifest.json",
}

# .claude.json is special: Claude CLI reads it from $HOME, not /task
_SPECIAL_MOUNTS = {
    ".claude.json": "/home/solver/.claude.json",  # rw — Claude CLI state
}

# .lean files are always rw (agent edits them); everything else is ro.

for fname in os.listdir(abs_ws):
    if fname in _IMAGE_PROVIDED:
        continue
    host_path = os.path.join(abs_ws, fname)
    if fname in _SPECIAL_MOUNTS:
        docker_cmd.extend(["-v", f"{host_path}:{_SPECIAL_MOUNTS[fname]}"])
        continue
    mode = "" if fname.endswith(".lean") else ":ro"
    docker_cmd.extend(["-v", f"{host_path}:/task/{fname}{mode}"])
```

Mount permissions follow the table above: task files the agent edits are rw, everything else (skills, configs) is ro. This prevents the agent from accidentally modifying skill definitions or MCP configs.

Delete: `.lake/packages` mount logic, `.lake/build` mkdir, symlink detection.

### `src/anonymous_prover/runner/workspace.py`

Split Docker and local workspace creation:

```python
# Docker mode: minimal workspace (only per-task content)
if self.docker_enabled:
    # Task file + skills + configs only. No symlinks, no lakefile copy.
    pass
else:
    # Local mode: symlink shared dirs + copy project files (unchanged)
    for dirname in ["Tacs", ".lake"]:
        ...
    for item in ("lakefile.toml", "lean-toolchain", "lake-manifest.json"):
        ...
```

### `src/anonymous_prover/analysis/lean_runner.py` — `check_file`

Support running verification inside Docker:

```python
def check_file(self, file_path, project_dir, timeout=120, docker_config=None):
    if docker_config and docker_config.enabled:
        # Verification only supports top-level files (e.g. "Task.lean").
        # Subdirectory paths would require mkdir -p inside the container;
        # reject them explicitly to keep the mount strategy simple.
        if os.sep in file_path or "/" in file_path:
            raise ValueError(
                f"Docker verification only supports top-level files, got: {file_path}"
            )
        host_file = os.path.join(os.path.abspath(project_dir), file_path)
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{host_file}:/task/{file_path}",
            "-w", "/task",
            docker_config.image,
            "lake", "env", "lean", file_path,
        ]
        project_dir = None
    else:
        cmd = ["lake", "env", self.lean_path, file_path]
    # ... rest unchanged ...
```

**Limitation**: Docker-mode verification assumes `file_path` is a top-level filename (e.g. `Task.lean`), not a nested path. This matches the current task layout where each task is a single `.lean` file at the workspace root. If multi-file tasks are needed in the future, the verification mount strategy must be extended (e.g. mount the entire workspace and exclude image-provided files).

### `src/anonymous_prover/extractors/default.py`

Thread `docker_config` through:

```python
def extract(self, ..., docker_config=None):
    lean_result = LeanRunner(lean_path).check_file(
        ..., docker_config=docker_config,
    )
```

### `src/anonymous_prover/runner/task_runner.py`

Pass config to extractor:

```python
result = self.extractor.extract(
    ...,
    docker_config=self.config.docker if self.config.docker.enabled else None,
)
```

## Image Rebuild Triggers

The image must be rebuilt when any of these change:
- `lakefile.toml` (dependencies)
- `lean-toolchain` (Lean version)
- `lake-manifest.json` (dependency lock)
- `Tacs.lean` + `Tacs/` (shared library entry point and modules)

Add to CI or Makefile:

```makefile
DOCKER_DEPS := lakefile.toml lean-toolchain lake-manifest.json Tacs.lean $(shell find Tacs -name '*.lean' 2>/dev/null)

docker-build: $(DOCKER_DEPS)
	docker build -f docker/lean4.Dockerfile -t anonymous-prover .
```

## Summary of Changes

| File | Change | Lines |
|------|--------|-------|
| `docker/lean4.Dockerfile` | Add `COPY` + `RUN lake build` | +5 |
| `base.py` `_wrap_in_docker` | Per-file mount instead of whole-workspace + .lake overlay | ~-20, +15 |
| `workspace.py` | Skip symlinks + lakefile copy in Docker mode | ~-10, +5 |
| `lean_runner.py` `check_file` | Docker-mode verification | +15 |
| `default.py` `extract` | Accept + pass `docker_config` | +3 |
| `task_runner.py` `run` | Pass `docker_config` to extractor | +2 |

Net: ~40 lines changed. Deletes more complexity than it adds.
