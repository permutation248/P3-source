# Anonymous-Prover

**English** | [中文](README.md)

An AI-assisted Lean 4 code generation and formal verification experiment platform. Uses Claude/Codex agents to automatically fill `sorry` placeholders (code/proof) in Lean 4 files, with full experiment management, result analysis, and statistical comparison capabilities.

## Motivation

In Lean 4 formal verification, developers manually write both implementations and correctness proofs. This project investigates: **Can AI agents (Claude/Codex) automate this work? How do different AI skills configurations affect success rate and cost?**

The platform supports three experiment modes:
- **Code** — auto-generate implementations (fill code sorries)
- **Proof** — auto-generate correctness proofs (fill proof sorries)
- **Auto** — generate both code and proofs with automatic retry

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────┐
│  React Frontend  │────→│  FastAPI Backend   │────→│    SQLite DB   │
│  (TypeScript)    │←────│  (Python)          │←────│               │
└─────────────────┘     └──────────────────┘     └───────────────┘
         │                       │
         │                ┌──────┴──────┐
         │                │     CLI      │
         │                │   (Click)    │
         │                └──────┬──────┘
         │                       │
         │              ┌────────┴────────┐
         │              │   Experiment     │
         │              │    Runner        │
         │              └────────┬────────┘
         │                       │
         │         ┌─────────────┼─────────────┐
         │         │             │             │
         │    ┌────┴───┐   ┌────┴───┐   ┌────┴──────┐
         │    │ Claude  │   │Extractor│   │ Collector │
         │    │ Agent   │   │        │   │           │
         │    └────────┘   └────────┘   └───────────┘
```

## Quick Start

### Requirements

- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **Lean 4 + Lake** (via [elan](https://github.com/leanprover/elan))
- **Claude CLI** (`claude` command-line tool) or **Codex CLI** (`codex` command-line tool)
- (Optional) **Docker** (recommended for reproducible runs)
- (Optional) **claude-tap** — for HTTP trace collection
- (Optional) **scipy** — for statistical tests

### 1. Install Lean 4

```bash
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh
cd Anonymous-Prover
lake build   # automatically fetches the correct Lean version and Mathlib
```

### 2. Install Python Package

```bash
python3 -m venv .venv
source .venv/bin/activate

# Core dependencies
pip install -e .

# With statistical tests
pip install -e ".[stats]"

# Everything (including dev tools)
pip install -e ".[all]"
```

### 3. CLI Usage

```bash
# Show help
anonymous-prover --help

# Run experiment from YAML config
anonymous-prover run --config config/experiment.example.yaml

# Run with CLI arguments
anonymous-prover run --name my-experiment --mode proof --tasks-dir Benchmarks/algoveribench --model sonnet-4-6

# Collect results
anonymous-prover collect results/my-experiment--proof--sonnet-4-6

# Compare two experiments
anonymous-prover compare results/baseline results/with-skills

# Start web server
anonymous-prover serve --host 0.0.0.0 --port 8000
```

Docker smoke test (image + single-task pipeline):

```bash
scripts/test_docker_and_task.sh
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev        # dev mode → http://localhost:5173
npm run build      # production build
```

### 5. API Endpoints

After starting `anonymous-prover serve`:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/experiments` | List experiments (supports `?mode=` `&model=` filters) |
| POST | `/api/experiments` | Create & start experiment |
| GET | `/api/experiments/{id}` | Experiment details |
| GET | `/api/results/{id}/tasks` | Task results (paginated, filterable, sortable) |
| GET | `/api/results/{id}/summary` | Experiment summary |
| GET | `/api/tasks/{id}/{task_name}` | Individual task details |
| POST | `/api/comparisons` | Create statistical comparison |
| GET | `/api/comparisons/{id}` | Comparison details |
| GET | `/api/config/agents` | Available agent types |
| GET | `/api/config/benchmarks` | Benchmark suite listing |
| WS | `/ws/experiments/{id}/progress` | Real-time experiment progress |

Interactive docs: `http://localhost:8000/docs`

---

## Project Structure

```
Anonymous-Prover/
├── pyproject.toml                     # Package config, CLI entry point
├── config/
│   └── experiment.example.yaml        # Experiment config example
│
├── src/anonymous_prover/                # ═══ Python Backend ═══
│   ├── core/                          # Enums, config, protocols, exceptions
│   ├── models/                        # SQLAlchemy ORM + Pydantic schemas
│   ├── api/                           # FastAPI (routes, WebSocket, deps)
│   ├── cli/                           # Click CLI (run, collect, compare, serve)
│   ├── runner/                        # Experiment engine (parallel task execution)
│   ├── agents/                        # Agent wrappers (Claude/Codex)
│   ├── extractors/                    # Stream-JSON parsing + result extraction
│   ├── collectors/                    # Result aggregation → summary.json
│   ├── comparators/                   # Statistical comparison (McNemar/Wilcoxon)
│   ├── stats/                         # Statistical tests (scipy optional)
│   ├── analysis/                      # Lean runner + sorry analysis
│   └── io/                            # JSON file persistence
│
├── frontend/                          # ═══ React Frontend ═══
│   └── src/
│       ├── pages/                     # Dashboard, Experiments, Detail, New, Compare
│       ├── components/shared/         # StatusBadge, MetricCard, DataTable
│       ├── api/client.ts              # API client
│       ├── hooks/                     # useExperiments, useWebSocket
│       └── types/                     # TypeScript interfaces
│
├── .claude/skills/                    # ═══ AI Skills ═══
│   ├── SKILL.md                       # Skill definition (code/proof/auto modes)
│   ├── scripts/                       # Helper scripts (sorry analysis, axiom check)
│   └── references/                    # Reference docs (tactics, invariants, etc.)
│
├── Benchmarks/                        # ═══ Benchmarks ═══
│   ├── algoveribench/                 # 82 algorithm verification problems
│   ├── verinabench/                   # 189 VeriNA verification problems
│   └── MISC/                          # Extended test suites
│       ├── algoveri/                  #   Algorithm verification
│       ├── cleverbench/               #   CleverBench
│       ├── subproblem/                #   Subproblem decomposition
│       ├── system/                    #   System-level
│       ├── userdefine/                #   User-defined
│       └── verina/                    #   VeriNA extended
│
├── Logs/                              # Claude output logs (JSON)
├── Summary/                           # Experiment result summaries (CSV)
└── History/                           # Historical version snapshots
```

---

## Experiment Design

### Experiment Groups (Ablation Study)

| Group | Skills Config | Purpose |
|-------|--------------|---------|
| **Baseline** | none | Pure Agent + Lean compiler |
| **Standard Skills** | standard | Standard skill suite |
| **Extended Skills** | extended | More aggressive automation/exploration |
| **Co-Derivation** | co_derivation | Code & proof co-derived from shared reasoning |
| **Docs Only** | docs_only | Knowledge docs only (ablation) |
| **Tools Only** | tools_only | Script tools only (ablation) |

### Experiment Pipeline

```
1. Task Setup     →  Copy .lean file to isolated workspace (with skill templates)
2. Agent Execution →  Agent reads task → invokes `/standard` skill mode → fills sorry → compile check → loop
3. Result Extract  →  Parse stream-json output: tokens, turns, cost
4. Verification    →  Sorry analysis: does the final file still contain sorry?
5. Aggregation     →  Summarize all tasks → statistical comparison
```

### Metrics

| Metric | Description |
|--------|-------------|
| **solved_rate** | Proportion of tasks fully solved (0 sorries) |
| **sorry_count** | Remaining sorry count in final file |
| **avg_time** | Average wall-clock time per task (seconds) |
| **avg_cost** | Average API cost per task (USD) |
| **total_turns** | Agent–LLM interaction turns |
| **per_benchmark** | Success rate grouped by benchmark suite |

### Statistical Tests

- **McNemar's test** — paired binary outcomes (solve rate significance)
- **Wilcoxon signed-rank test** — paired continuous variables (time/cost significance)
- **Fisher's exact test** — 2×2 contingency tables

---

## YAML Configuration

```yaml
name: baseline-proof
mode: proof                    # code | proof | auto
skills_config: none            # none | standard | extended | co_derivation | docs_only | tools_only
tasks_dir: Benchmarks/algoveribench
agent:
  type: claude-code
  model: sonnet-4-6
  use_tap: true                # use claude-tap for HTTP trace collection
  tap_output_dir: claude_traces
lean:
  timeout_seconds: 120
  lake_build: true
parallel: 4
task_timeout_seconds: 1800
force: false
persist_to_db: true
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `ANONYMOUS_PROVER_DB_URL` | Database URL | `sqlite:///data/anonymous_prover.db` |
| `LEAN4_SCRIPTS` | Skills scripts directory | — |
| `LEAN4_REFS` | Skills reference docs directory | — |
| `CLAUDE_CODE_SUBAGENT_MODEL` | Force Claude sub-agents to inherit the parent model (prevents silent Sonnet→Opus escalation) | unset |

---

## AI Skills (standard/extended/co-derivation)

### Three Modes

- **`/standard code <file>`** — generate implementations, fill code sorries one by one
- **`/standard proof <file>`** — generate proofs via 6-step workflow (Plan → Work → Checkpoint → Review → Replan → Continue)
- **`/standard auto <file>`** — joint code+proof generation with automatic retry and counterexample-driven fallback

### Core Principles

1. Never modify specifications (pre/postconditions are read-only)
2. Prefer simple, structurally recursive implementations
3. Search Mathlib exhaustively before proving from scratch
4. Design proofs around invariants first
5. Fully autonomous — use the full budget, never stop to ask

---

## License

This project is for research purposes. Benchmark tasks are sourced from the VerInaBench and AlgoVeriBench projects.
