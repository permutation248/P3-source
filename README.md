# Anonymous-Prover

[English](README_EN.md) | **中文**

AI 辅助 Lean 4 代码生成与形式验证实验平台。通过 Claude/Codex Agent 自动填充 Lean 4 文件中的 `sorry`（代码/证明占位符），并提供完整的实验管理、结果分析和统计对比能力。

## 背景

Lean 4 形式验证中，开发者需要手动编写代码实现和正确性证明。本项目研究：**AI Agent（Claude）能否自动完成这些工作？不同的 AI Skills 配置对成功率和成本有何影响？**

平台支持三种实验模式：
- **Code** — 自动生成代码实现（填充代码 sorry）
- **Proof** — 自动生成正确性证明（填充证明 sorry）
- **Auto** — 同时生成代码和证明，自动重试

## 系统架构

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────┐
│   React 前端     │────→│  FastAPI 后端      │────→│  SQLite 数据库  │
│   (TypeScript)   │←────│  (Python)         │←────│               │
└─────────────────┘     └──────────────────┘     └───────────────┘
         │                       │
         │                ┌──────┴──────┐
         │                │  CLI 命令行   │
         │                │  (Click)     │
         │                └──────┬──────┘
         │                       │
         │              ┌────────┴────────┐
         │              │   实验执行引擎    │
         │              │ ExperimentRunner │
         │              └────────┬────────┘
         │                       │
         │         ┌─────────────┼─────────────┐
         │         │             │             │
         │    ┌────┴───┐   ┌────┴───┐   ┌────┴──────┐
         │    │ Claude  │   │提取器   │   │ 收集器     │
         │    │ Agent   │   │Extractor│   │ Collector │
         │    └────────┘   └────────┘   └───────────┘
```

## 快速开始

### 环境要求

- **Python 3.11+**
- **Node.js 18+**（前端开发）
- **Lean 4 + Lake**（通过 [elan](https://github.com/leanprover/elan) 安装）
- **Claude CLI**（`claude` 命令行工具）或 **Codex CLI**（`codex` 命令行工具）
- (可选) **Docker**（推荐，用于复现实验环境）
- (可选) **claude-tap** — 用于 HTTP trace 采集
- (可选) **scipy** — 用于统计检验

### 1. 安装 Lean 4

```bash
curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh
cd Anonymous-Prover
lake build   # 自动拉取正确的 Lean 版本和 Mathlib
```

### 2. 安装 Python 包

```bash
python3 -m venv .venv
source .venv/bin/activate

# 核心依赖
pip install -e .

# 含统计检验
pip install -e ".[stats]"

# 全部（含开发工具）
pip install -e ".[all]"
```

### 3. CLI 使用

```bash
# 查看帮助
anonymous-prover --help

# 通过 YAML 配置运行实验
anonymous-prover run --config config/experiment.example.yaml

# 通过命令行参数运行
anonymous-prover run --name my-experiment --mode proof --tasks-dir Benchmarks/algoveribench --model sonnet-4-6

# 收集实验结果
anonymous-prover collect results/my-experiment--proof--sonnet-4-6

# 对比两个实验
anonymous-prover compare results/baseline results/with-skills

# 启动 Web 服务
anonymous-prover serve --host 0.0.0.0 --port 8000
```

Docker 快速自检（镜像 + 单任务链路）：

```bash
scripts/test_docker_and_task.sh
```

### 4. 前端

```bash
cd frontend
npm install
npm run dev        # 开发模式 → http://localhost:5173
npm run build      # 生产构建
```

### 5. API 端点

启动 `anonymous-prover serve` 后可访问：

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| GET | `/api/experiments` | 实验列表（支持 `?mode=` `&model=` 过滤） |
| POST | `/api/experiments` | 创建并启动实验 |
| GET | `/api/experiments/{id}` | 实验详情 |
| GET | `/api/results/{id}/tasks` | 任务结果（分页、过滤、排序） |
| GET | `/api/results/{id}/summary` | 实验摘要 |
| GET | `/api/tasks/{id}/{task_name}` | 单任务详情 |
| POST | `/api/comparisons` | 创建统计对比 |
| GET | `/api/comparisons/{id}` | 对比详情 |
| GET | `/api/config/agents` | Agent 配置列表 |
| GET | `/api/config/benchmarks` | 基准测试套件列表 |
| WS | `/ws/experiments/{id}/progress` | 实验进度推送 |

交互式文档：`http://localhost:8000/docs`

---

## 项目结构

```
Anonymous-Prover/
├── pyproject.toml                     # 包配置、CLI 入口
├── config/
│   └── experiment.example.yaml        # 实验配置示例
│
├── src/anonymous_prover/                # ═══ Python 后端 ═══
│   ├── core/                          # ── 核心层 ──
│   │   ├── enums.py                   #   枚举 (ExperimentMode, SkillsConfig, AgentType, ...)
│   │   ├── config.py                  #   Pydantic 配置模型 + YAML 加载
│   │   ├── protocols.py               #   抽象接口 (CLIAgent, ResultExtractor, ...)
│   │   └── exceptions.py              #   异常体系
│   │
│   ├── models/                        # ── 数据模型 ──
│   │   ├── database.py                #   SQLAlchemy 引擎/Session
│   │   ├── experiment.py              #   Experiment ORM
│   │   ├── task_result.py             #   TaskResult ORM
│   │   ├── comparison.py              #   Comparison ORM
│   │   ├── schemas.py                 #   Pydantic API Schema
│   │   └── utils.py                   #   共享工具 (parse_json_field)
│   │
│   ├── api/                           # ── FastAPI 后端 ──
│   │   ├── app.py                     #   App 工厂
│   │   ├── deps.py                    #   依赖注入
│   │   ├── websocket.py               #   WebSocket 进度推送
│   │   └── routes/                    #   路由 (experiments, results, comparisons, tasks, config)
│   │
│   ├── cli/                           # ── Click CLI ──
│   │   ├── main.py                    #   根命令 (anonymous-prover)
│   │   ├── run.py                     #   运行实验
│   │   ├── collect.py                 #   收集结果
│   │   ├── compare.py                 #   对比实验
│   │   └── serve.py                   #   启动 Web 服务
│   │
│   ├── runner/                        # ── 实验执行引擎 ──
│   │   ├── prompts.py                 #   提示词构建
│   │   ├── workspace.py               #   工作区管理
│   │   ├── task_runner.py             #   单任务执行
│   │   └── experiment_runner.py       #   批量并行执行
│   │
│   ├── agents/                        # ── Agent 封装（Claude/Codex） ──
│   │   ├── base.py                    #   基类 (进程管理、重试)
│   │   ├── claude.py                  #   Claude CLI / claude-tap 封装
│   │   ├── codex.py                   #   Codex CLI 封装
│   │   └── factory.py                 #   Agent 工厂
│   │
│   ├── extractors/                    # ── 结果提取 ──
│   │   ├── stream_parsers.py          #   Stream-JSON 解析 + token 计费
│   │   ├── base.py                    #   提取器基类
│   │   ├── default.py                 #   默认提取器 (sorry 计数 + 超时检测)
│   │   └── factory.py                 #   工厂
│   │
│   ├── collectors/                    # ── 结果聚合 ──
│   │   ├── base.py                    #   统计工具 (avg/median/p95)
│   │   ├── default.py                 #   默认收集器 → summary.json
│   │   └── factory.py                 #   工厂
│   │
│   ├── comparators/                   # ── 统计对比 ──
│   │   ├── base.py                    #   对比器基类
│   │   ├── default.py                 #   默认对比器 (McNemar + Wilcoxon)
│   │   └── factory.py                 #   工厂
│   │
│   ├── stats/                         # ── 统计检验 ──
│   │   └── tests.py                   #   McNemar / Wilcoxon / Fisher (scipy 可选)
│   │
│   ├── analysis/                      # ── 代码分析 ──
│   │   ├── lean_runner.py             #   Lean 4 构建/检查封装
│   │   └── sorry_analyzer.py          #   sorry 分析器
│   │
│   └── io/                            # ── 持久化 ──
│       └── result_store.py            #   JSON 文件存储
│
├── frontend/                          # ═══ React 前端 ═══
│   └── src/
│       ├── App.tsx                    #   路由 + 导航
│       ├── types/index.ts             #   TypeScript 类型
│       ├── api/client.ts              #   API 客户端
│       ├── hooks/index.ts             #   React Hooks
│       ├── components/shared/         #   共享组件 (StatusBadge, MetricCard, DataTable)
│       └── pages/                     #   页面
│           ├── Dashboard.tsx          #     总览
│           ├── Experiments.tsx         #     实验列表
│           ├── ExperimentDetail.tsx    #     实验详情 + 图表
│           ├── NewExperiment.tsx       #     新建实验
│           └── Compare.tsx            #     实验对比
│
├── .claude/skills/                    # ═══ AI 技能 ═══
│   ├── SKILL.md                       #   技能定义 (code/proof/auto 模式)
│   ├── scripts/                       #   辅助脚本 (sorry 分析、公理检查等)
│   └── references/                    #   参考文档 (tactic、invariant 等)
│
├── Benchmarks/                        # ═══ 基准测试 ═══
│   ├── algoveribench/                 #   82 个算法验证问题 (164 文件)
│   ├── verinabench/                   #   189 个 VeriNA 验证问题 (378 文件)
│   └── MISC/                          #   扩展测试套件
│       ├── algoveri/                  #     算法验证
│       ├── cleverbench/               #     CleverBench
│       ├── subproblem/                #     子问题分解
│       ├── system/                    #     系统级
│       ├── userdefine/                #     自定义
│       └── verina/                    #     VeriNA 扩展
│
├── Logs/                              # Claude 输出日志 (JSON)
├── Summary/                           # 实验结果汇总 (CSV)
└── History/                           # 历史版本快照
```

---

## 实验设计

### 实验分组（消融实验）

| 分组 | Skills 配置 | 目的 |
|------|------------|------|
| **基线** | none | 纯 Agent + Lean 编译器 |
| **标准技能** | standard | 标准技能套件 |
| **扩展技能** | extended | 更强自动化/探索策略 |
| **共同推导** | co_derivation | 代码与证明共同推导 |
| **仅文档** | docs_only | 仅知识文档（消融） |
| **仅工具** | tools_only | 仅脚本工具（消融） |

### 实验流程

```
1. 任务准备   →  复制 .lean 文件到隔离工作区（含 Skills 模板）
2. Agent 执行  →  Agent 读取任务 → 调用 `/standard` 模式 → 填充 sorry → 编译检查 → 循环
3. 结果提取   →  解析 stream-json 输出：token 数、轮次、成本
4. 验证       →  sorry 分析：最终文件是否还有 sorry
5. 聚合分析   →  汇总所有任务 → 统计对比
```

### 评估指标

| 指标 | 说明 |
|------|------|
| **solved_rate** | 成功解决（0 sorry）的任务比例 |
| **sorry_count** | 最终文件中剩余 sorry 数量 |
| **avg_time** | 每任务平均耗时（秒） |
| **avg_cost** | 每任务平均 API 成本（美元） |
| **total_turns** | Agent 与 LLM 交互轮次 |
| **per_benchmark** | 按测试套件分组的成功率 |

### 统计检验

- **McNemar 检验** — 配对二值结果（求解率差异显著性）
- **Wilcoxon 符号秩检验** — 配对连续变量（时间/成本差异显著性）
- **Fisher 精确检验** — 2x2 列联表

---

## YAML 配置

```yaml
name: baseline-proof
mode: proof                    # code | proof | auto
skills_config: none            # none | standard | extended | co_derivation | docs_only | tools_only
tasks_dir: Benchmarks/algoveribench
agent:
  type: claude-code
  model: sonnet-4-6
  use_tap: true                # 是否用 claude-tap 保存 traces
  tap_output_dir: claude_traces
lean:
  timeout_seconds: 120
  lake_build: true
parallel: 4
task_timeout_seconds: 1800
force: false
persist_to_db: true
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ANONYMOUS_PROVER_DB_URL` | 数据库 URL | `sqlite:///data/anonymous_prover.db` |
| `LEAN4_SCRIPTS` | Skills 脚本目录 | — |
| `LEAN4_REFS` | Skills 参考文档目录 | — |
| `CLAUDE_CODE_SUBAGENT_MODEL` | 强制 Claude 子代理继承同一模型（避免子代理升级到 Opus） | 未设置 |

---

## AI 技能 (standard/extended/co-derivation)

### 三种模式

- **`/standard code <file>`** — 生成代码实现，逐个填充代码 sorry
- **`/standard proof <file>`** — 生成正确性证明，6 步工作流（Plan→Work→Checkpoint→Review→Replan→Continue）
- **`/standard auto <file>`** — 代码+证明联合生成，含自动重试和反例驱动回退

### 核心原则

1. 绝不修改规约（前/后条件只读）
2. 优先选择结构递归的简单实现
3. 先搜索 Mathlib 再自己证
4. 证明围绕不变量设计
5. 完全自主——用尽预算，不停下来问

---

## 许可证

本项目用于研究目的。基准任务来自 VerInaBench 和 AlgoVeriBench 项目。
