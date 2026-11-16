import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Clock, Target, TrendingUp, DollarSign, Layers, Square, Trash2, X, RotateCcw, Play } from 'lucide-react';
import { useExperiment, useWebSocket } from '../hooks';
import {
  listTaskResults,
  stopExperiment,
  deleteExperiment,
  restartExperiment,
  resumeExperiment,
  listProofFiles,
  readProofFile,
  extractApiError,
} from '../api/client';
import { useApiKey, BACKEND_LABELS, familyForExperiment } from '../contexts/ApiKeyContext';
import {
  MetricCard,
  StatusBadge,
  LoadingSpinner,
  DataTable,
  PageHeader,
  SectionCard,
  selectClass,
  btnSecondary,
  type Column,
} from '../components/shared';
import type { TaskResult, PaginatedResponse } from '../types';

export default function ExperimentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const expId = id ? Number(id) : undefined;
  const { experiment, loading, error, refresh, silentRefresh } = useExperiment(expId);
  const { authForFamily, activeBackend } = useApiKey();

  const rerunFamily = useMemo(
    () => familyForExperiment(experiment?.agent_type, experiment?.model),
    [experiment?.agent_type, experiment?.model],
  );

  const { progress, connected } = useWebSocket(
    experiment?.status === 'running' ? expId : undefined,
  );

  const [taskData, setTaskData] = useState<PaginatedResponse<TaskResult> | null>(null);
  const [taskLoading, setTaskLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [solvedFilter, setSolvedFilter] = useState<boolean | undefined>(undefined);
  const [sortBy, setSortBy] = useState('task_name');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [stopping, setStopping] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [allTasks, setAllTasks] = useState<TaskResult[]>([]);
  const [proofModal, setProofModal] = useState<{ taskName: string; files: { name: string; size: number }[] } | null>(null);
  const [proofContent, setProofContent] = useState<{ name: string; content: string } | null>(null);
  const [proofLoading, setProofLoading] = useState(false);

  const loadTasks = useCallback(async (showLoading = true) => {
    if (!expId) return;
    if (showLoading) setTaskLoading(true);
    try {
      const data = await listTaskResults(expId, {
        page,
        page_size: 25,
        solved: solvedFilter,
        sort_by: sortBy,
        sort_order: sortOrder,
      });
      setTaskData(data);
    } catch {
      // silently fail
    } finally {
      if (showLoading) setTaskLoading(false);
    }
  }, [expId, page, solvedFilter, sortBy, sortOrder]);

  useEffect(() => {
    loadTasks();
  }, [loadTasks]);

  // Fetch all tasks for chart — triggered by WebSocket updates or polling
  const fetchAllTasks = useCallback(async () => {
    if (!expId) return;
    const all: TaskResult[] = [];
    let pg = 1;
    while (true) {
      const res = await listTaskResults(expId, { page: pg, page_size: 200, sort_by: 'total_time_seconds', sort_order: 'asc' });
      all.push(...res.items);
      if (all.length >= res.total || res.items.length === 0) break;
      pg++;
    }
    setAllTasks(all);
  }, [expId]);

  useEffect(() => {
    fetchAllTasks().catch(() => {});
  }, [fetchAllTasks, progress?.completed]);

  // Poll task list + experiment status every 10s while running
  const isRunning = experiment?.status === 'running';
  const refreshRef = useRef(silentRefresh);
  refreshRef.current = silentRefresh;
  const loadTasksRef = useRef(loadTasks);
  loadTasksRef.current = loadTasks;
  const fetchAllTasksRef = useRef(fetchAllTasks);
  fetchAllTasksRef.current = fetchAllTasks;

  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => {
      loadTasksRef.current(false);
      fetchAllTasksRef.current().catch(() => {});
      refreshRef.current();
    }, 10000);
    return () => clearInterval(interval);
  }, [isRunning]);

  const handleSort = (key: string) => {
    if (sortBy === key) {
      setSortOrder((o) => (o === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortOrder('asc');
    }
    setPage(1);
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="p-8 text-proof-red font-mono text-sm">Error: {error}</div>;
  if (!experiment) return <div className="p-8 text-ink-400 font-mono text-sm">Experiment not found</div>;

  // Build cumulative solve-rate-over-time curve
  const curveData: { time: number; solveRate: number }[] = [];
  {
    const totalTasks = allTasks.length;
    if (totalTasks > 0) {
      const solved = allTasks
        .filter((t) => t.solved && t.total_time_seconds != null)
        .map((t) => t.total_time_seconds!)
        .sort((a, b) => a - b);
      curveData.push({ time: 0, solveRate: 0 });
      solved.forEach((t, i) => {
        curveData.push({ time: Math.round(t * 10) / 10, solveRate: ((i + 1) / totalTasks) * 100 });
      });
    }
  }

  const hasProgressTotals =
    progress != null &&
    typeof progress.total === 'number' &&
    typeof progress.solved_count === 'number';

  const displaySolved = hasProgressTotals ? progress.solved_count : experiment.solved_count;
  const displayTotal = hasProgressTotals ? progress.total : experiment.total_tasks;
  const displayRate = displayTotal > 0 ? (displaySolved / displayTotal) * 100 : experiment.solved_rate ?? 0;

  const taskColumns: Column<TaskResult>[] = [
    { key: 'task_name', header: 'Task', sortable: true },
    {
      key: 'solved',
      header: 'Status',
      sortable: true,
      render: (r) => <StatusBadge status={r.solved ? 'solved' : r.timeout ? 'timeout' : 'failed'} />,
    },
    { key: 'sorry_count', header: 'Sorry', sortable: true, mono: true },
    {
      key: 'total_time_seconds',
      header: 'Time',
      sortable: true,
      mono: true,
      render: (r) => r.total_time_seconds != null ? `${r.total_time_seconds.toFixed(1)}s` : '\u2014',
    },
    {
      key: 'input_tokens',
      header: 'In Tokens',
      sortable: true,
      mono: true,
      render: (r) => r.input_tokens != null ? r.input_tokens.toLocaleString() : '\u2014',
    },
    {
      key: 'output_tokens',
      header: 'Out Tokens',
      sortable: true,
      mono: true,
      render: (r) => r.output_tokens != null ? r.output_tokens.toLocaleString() : '\u2014',
    },
    {
      key: 'cost_usd',
      header: 'Cost',
      sortable: true,
      mono: true,
      render: (r) => {
        if (r.cost_usd == null) return '\u2014';
        const suffix = r.cost_source === 'estimated' ? ' (est.)' : '';
        return `$${r.cost_usd.toFixed(4)}${suffix}`;
      },
    },
    { key: 'total_turns', header: 'Turns', sortable: true, mono: true },
  ];

  /** Shared Resume/Restart handler. Kept in one place so the credential
   *  flow (authForFamily at click time) + error surfacing stay symmetric. */
  const runRerun = async (
    kind: 'resume' | 'restart',
    setBusy: (b: boolean) => void,
  ) => {
    if (!expId) return;
    const confirmMsg =
      kind === 'resume'
        ? 'Resume this experiment? Existing results will be kept and only unfinished tasks will continue.'
        : 'Restart this experiment? Old results will be deleted.';
    if (!confirm(confirmMsg)) return;
    const action = kind === 'resume' ? resumeExperiment : restartExperiment;
    setBusy(true);
    try {
      await action(expId, authForFamily(rerunFamily));
      await Promise.all([refresh(), loadTasks()]);
      fetchAllTasks().catch(() => {});
    } catch (err) {
      alert(extractApiError(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <PageHeader
        title={experiment.name}
        symbol="∃"
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge status={experiment.mode} />
            <StatusBadge status={experiment.status} />
            <span className="font-mono text-xs text-ink-400">{experiment.model}</span>
            {connected && (
              <span className="ml-2 inline-flex items-center gap-1.5 text-xs text-proof-green font-medium">
                <span className="live-dot" />
                Live
              </span>
            )}
            {experiment.status !== 'running' && (
              <span
                className="ml-2 rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-ink-500"
                title="Credentials read from Settings at run time. Change in Settings, not here."
              >
                {BACKEND_LABELS[activeBackend[rerunFamily]]}
              </span>
            )}
            {experiment.status !== 'running' && (
              <>
                <button
                  onClick={() => !resuming && runRerun('resume', setResuming)}
                  disabled={resuming}
                  className="ml-2 inline-flex items-center gap-1.5 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 hover:bg-emerald-100 transition-colors disabled:opacity-50"
                >
                  <Play size={12} />
                  {resuming ? 'Resuming...' : 'Resume'}
                </button>
                <button
                  onClick={() => !restarting && runRerun('restart', setRestarting)}
                  disabled={restarting}
                  className="ml-2 inline-flex items-center gap-1.5 rounded-lg border border-accent-300 bg-accent-50 px-3 py-1.5 text-xs font-medium text-accent-700 hover:bg-accent-100 transition-colors disabled:opacity-50"
                >
                  <RotateCcw size={12} />
                  {restarting ? 'Restarting...' : 'Restart'}
                </button>
                <button
                  onClick={async () => {
                    if (!expId || deleting) return;
                    if (!confirm('Delete this experiment and all its results?')) return;
                    setDeleting(true);
                    try {
                      await deleteExperiment(expId);
                      navigate('/experiments');
                    } catch {
                      /* best-effort */
                    } finally {
                      setDeleting(false);
                    }
                  }}
                  disabled={deleting}
                  className="ml-2 inline-flex items-center gap-1.5 rounded-lg border border-red-300 bg-red-50 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-100 transition-colors disabled:opacity-50"
                >
                  <Trash2 size={12} />
                  {deleting ? 'Deleting...' : 'Delete'}
                </button>
              </>
            )}
          </div>
        }
      />

      {/* Progress bar */}
      {experiment.status === 'running' && (
        <div className="rounded-xl border border-accent-200 bg-accent-50/30 p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-accent-700">
              Progress: <span className="font-mono">{progress?.completed ?? taskData?.total ?? 0}/{progress?.total ?? experiment.total_tasks}</span>
              {progress?.task_name && (
                <span className="ml-2 text-accent-500 font-mono text-xs">({progress.task_name})</span>
              )}
            </span>
            <div className="flex items-center gap-3">
              <span className="font-mono font-semibold text-accent-600">
                {(() => {
                  const c = progress?.completed ?? taskData?.total ?? 0;
                  const t = progress?.total ?? experiment.total_tasks;
                  return t > 0 ? ((c / t) * 100).toFixed(0) : 0;
                })()}%
              </span>
              <button
                onClick={async () => {
                  if (!expId || stopping) return;
                  setStopping(true);
                  try {
                    await stopExperiment(expId);
                    await refresh();
                  } catch {
                    // ignore
                  } finally {
                    setStopping(false);
                  }
                }}
                disabled={stopping}
                className="inline-flex items-center gap-1.5 rounded-lg border border-red-300 bg-red-50 px-3 py-1 text-xs font-medium text-red-700 hover:bg-red-100 transition-colors disabled:opacity-50"
              >
                <Square size={12} />
                {stopping ? 'Stopping...' : 'Stop'}
              </button>
            </div>
          </div>
          <div className="mt-2.5 h-1.5 w-full overflow-hidden rounded-full bg-accent-200/50">
            <div
              className="h-full rounded-full bg-accent-500 transition-all duration-500 ease-out"
              style={{
                width: `${(() => {
                  const c = progress?.completed ?? taskData?.total ?? 0;
                  const t = progress?.total ?? experiment.total_tasks;
                  return t > 0 ? (c / t) * 100 : 0;
                })()}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Metrics */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-5">
        <MetricCard label="Total Tasks" value={displayTotal} icon={<Layers size={16} />} accent="violet" />
        <MetricCard label="Solved" value={displaySolved} icon={<Target size={16} />} accent="green" />
        <MetricCard label="Solve Rate" value={`${displayRate.toFixed(1)}%`} icon={<TrendingUp size={16} />} accent="blue" />
        <MetricCard label="Avg Time" value={`${(experiment.avg_time_seconds ?? 0).toFixed(1)}s`} icon={<Clock size={16} />} accent="amber" />
        <MetricCard label="Total Cost" value={`$${(experiment.total_cost_usd ?? 0).toFixed(2)}`} icon={<DollarSign size={16} />} accent="default" />
      </div>

      {/* Chart */}
      {curveData.length > 1 && (
        <SectionCard title="Solve Rate over Time">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={curveData} margin={{ top: 5, right: 20, bottom: 20, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e5ed" />
              <XAxis
                dataKey="time"
                type="number"
                domain={['dataMin', 'dataMax']}
                tickFormatter={(v) => `${v}s`}
                tick={{ fontSize: 11, fill: '#67739b' }}
                label={{ value: 'Solve Time (s)', position: 'insideBottom', offset: -10, fontSize: 11, fill: '#67739b' }}
              />
              <YAxis
                domain={[0, 100]}
                tickFormatter={(v) => `${v}%`}
                tick={{ fontSize: 11, fill: '#67739b' }}
                label={{ value: 'Cumulative Solve Rate', angle: -90, position: 'insideLeft', offset: 5, fontSize: 11, fill: '#67739b' }}
              />
              <Tooltip
                formatter={(v: number) => [`${v.toFixed(1)}%`, 'Solve Rate']}
                labelFormatter={(l) => `${l}s`}
                contentStyle={{
                  borderRadius: '8px',
                  border: '1px solid #d9dce6',
                  boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
                  fontSize: '12px',
                  fontFamily: '"JetBrains Mono", monospace',
                }}
              />
              <Line type="stepAfter" dataKey="solveRate" stroke="#6366f1" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </SectionCard>
      )}

      {/* Task Results */}
      <div>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-ink-500">
            Task Results
          </h2>
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-400">Filter</span>
            <select
              value={solvedFilter === undefined ? 'all' : solvedFilter ? 'solved' : 'unsolved'}
              onChange={(e) => {
                const v = e.target.value;
                setSolvedFilter(v === 'all' ? undefined : v === 'solved');
                setPage(1);
              }}
              className={`${selectClass} w-auto min-w-[130px]`}
            >
              <option value="all">All</option>
              <option value="solved">Solved</option>
              <option value="unsolved">Unsolved</option>
            </select>
          </div>
        </div>

        {taskLoading ? (
          <LoadingSpinner size="sm" />
        ) : taskData ? (
          <>
            <DataTable
              columns={taskColumns}
              data={taskData.items}
              sortBy={sortBy}
              sortOrder={sortOrder}
              onSort={handleSort}
              rowKey={(r) => r.id}
              onRowClick={async (r) => {
                if (!expId || proofLoading) return;
                setProofLoading(true);
                try {
                  const files = await listProofFiles(expId, r.task_name);
                  setProofModal({ taskName: r.task_name, files });
                  setProofContent(null);
                  // Auto-open first .lean file
                  const firstLean = files.find((f) => f.name.endsWith('.lean') && !f.name.startsWith('lakefile'));
                  if (firstLean) {
                    const content = await readProofFile(expId, r.task_name, firstLean.name);
                    setProofContent({ name: firstLean.name, content });
                  }
                } catch {
                  // ignore
                } finally {
                  setProofLoading(false);
                }
              }}
            />
            {(() => {
              const totalPages = Math.ceil(taskData.total / taskData.page_size);
              return totalPages > 1 ? (
                <div className="mt-4 flex items-center justify-between">
                  <span className="text-xs font-mono text-ink-400">
                    Page {taskData.page} / {totalPages} ({taskData.total} total)
                  </span>
                  <div className="flex gap-2">
                    <button
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                      disabled={page <= 1}
                      className={btnSecondary}
                    >
                      Prev
                    </button>
                    <button
                      onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                      disabled={page >= totalPages}
                      className={btnSecondary}
                    >
                      Next
                    </button>
                  </div>
                </div>
              ) : null;
            })()}
          </>
        ) : null}
      </div>

      {/* Proof Files Modal */}
      {proofModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={() => { setProofModal(null); setProofContent(null); }}>
          <div
            className="relative mx-4 flex max-h-[85vh] w-full max-w-4xl flex-col rounded-xl border border-accent-200 bg-white shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-accent-100 px-6 py-4">
              <h3 className="text-base font-semibold text-ink-700">{proofModal.taskName}</h3>
              <button
                onClick={() => { setProofModal(null); setProofContent(null); }}
                className="text-ink-400 hover:text-ink-600"
              >
                <X size={18} />
              </button>
            </div>
            {/* Body */}
            <div className="flex min-h-0 flex-1">
              {/* File list sidebar */}
              <div className="w-56 shrink-0 overflow-auto border-r border-accent-100 bg-ink-50/50 p-3">
                {proofModal.files.length === 0 ? (
                  <p className="text-xs text-ink-400">No proof files found.</p>
                ) : (
                  <ul className="space-y-0.5">
                    {proofModal.files.map((f) => (
                      <li key={f.name}>
                        <button
                          onClick={async () => {
                            if (!expId) return;
                            try {
                              const content = await readProofFile(expId, proofModal.taskName, f.name);
                              setProofContent({ name: f.name, content });
                            } catch { /* ignore */ }
                          }}
                          className={`w-full rounded-md px-2.5 py-1.5 text-left text-xs font-mono transition-colors ${
                            proofContent?.name === f.name
                              ? 'bg-accent-100 text-accent-700 font-medium'
                              : 'text-ink-600 hover:bg-accent-50'
                          }`}
                        >
                          {f.name}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              {/* File content */}
              <div className="flex-1 overflow-auto p-4">
                {proofContent ? (
                  <>
                    <div className="mb-2 text-xs font-mono text-ink-400">{proofContent.name}</div>
                    <pre className="rounded-lg bg-ink-50 p-4 text-xs font-mono text-ink-700 leading-relaxed whitespace-pre-wrap overflow-auto max-h-[65vh]">
                      {proofContent.content}
                    </pre>
                  </>
                ) : (
                  <p className="text-xs text-ink-400">Select a file to view its content.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
