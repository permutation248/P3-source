import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useExperiments } from '../hooks';
import {
  StatusBadge,
  LoadingSpinner,
  DataTable,
  PageHeader,
  selectClass,
  type Column,
} from '../components/shared';
import type { Experiment } from '../types';

export default function Experiments() {
  const [modeFilter, setModeFilter] = useState<string>('');
  const { experiments, loading, error } = useExperiments(modeFilter ? { mode: modeFilter } : undefined);
  const navigate = useNavigate();

  const columns: Column<Experiment>[] = [
    { key: 'name', header: 'Name' },
    {
      key: 'status',
      header: 'Status',
      render: (r) => <StatusBadge status={r.status} />,
    },
    {
      key: 'started_at',
      header: 'Date',
      mono: true,
      render: (r) => {
        const d = r.started_at ?? r.created_at;
        return d ? new Date(d).toLocaleString() : '—';
      },
    },
    { key: 'model', header: 'Model', mono: true },
    { key: 'total_tasks', header: 'Tasks', mono: true },
    {
      key: 'solved_rate',
      header: 'Solve Rate',
      mono: true,
      render: (r) => `${(r.solved_rate ?? 0).toFixed(1)}%`,
    },
    {
      key: 'avg_time_seconds',
      header: 'Avg Time',
      mono: true,
      render: (r) => `${(r.avg_time_seconds ?? 0).toFixed(1)}s`,
    },
    {
      key: 'total_cost_usd',
      header: 'Cost',
      mono: true,
      render: (r) => `$${(r.total_cost_usd ?? 0).toFixed(2)}`,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Experiments"
        subtitle="All verification experiments"
        symbol="∀"
      />

      <div className="flex items-center gap-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-ink-400">Filter</span>
        <select
          value={modeFilter}
          onChange={(e) => setModeFilter(e.target.value)}
          className={`${selectClass} w-auto min-w-[120px]`}
        >
          <option value="">All Modes</option>
          <option value="code">Code</option>
          <option value="proof">Proof</option>
          <option value="auto">Auto</option>
        </select>
      </div>

      {loading ? (
        <LoadingSpinner />
      ) : error ? (
        <div className="text-proof-red font-mono text-sm">Error: {error}</div>
      ) : (
        <DataTable
          columns={columns}
          data={experiments}
          rowKey={(r) => r.id}
          onRowClick={(r) => navigate(`/experiments/${r.id}`)}
        />
      )}
    </div>
  );
}
