import { useNavigate } from 'react-router-dom';
import { FlaskConical, Zap, TrendingUp, DollarSign } from 'lucide-react';
import { useExperiments } from '../hooks';
import {
  MetricCard,
  StatusBadge,
  LoadingSpinner,
  DataTable,
  PageHeader,
  SectionCard,
  type Column,
} from '../components/shared';
import type { Experiment } from '../types';

export default function Dashboard() {
  const { experiments, loading, error } = useExperiments();
  const navigate = useNavigate();

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="p-8 text-proof-red font-mono text-sm">Error: {error}</div>;

  const running = experiments.filter((e) => e.status === 'running').length;
  const bestRate = experiments.length > 0 ? Math.max(...experiments.map((e) => e.solved_rate ?? 0)) : 0;
  const totalCost = experiments.reduce((sum, e) => sum + (e.total_cost_usd ?? 0), 0);
  const recent = [...experiments].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);

  const columns: Column<Experiment>[] = [
    { key: 'name', header: 'Name' },
    {
      key: 'mode',
      header: 'Mode',
      render: (r) => <StatusBadge status={r.mode} />,
    },
    {
      key: 'status',
      header: 'Status',
      render: (r) => <StatusBadge status={r.status} />,
    },
    {
      key: 'solved_rate',
      header: 'Solve Rate',
      mono: true,
      render: (r) => `${(r.solved_rate ?? 0).toFixed(1)}%`,
    },
    {
      key: 'total_cost_usd',
      header: 'Cost',
      mono: true,
      render: (r) => `$${(r.total_cost_usd ?? 0).toFixed(2)}`,
    },
  ];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Dashboard"
        subtitle="Formal verification experiment overview"
        symbol="λ"
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Experiments"
          value={experiments.length}
          icon={<FlaskConical size={18} />}
          accent="violet"
        />
        <MetricCard
          label="Running"
          value={running}
          icon={<Zap size={18} />}
          accent="blue"
          trend={running > 0 ? { direction: 'up', text: `${running} active` } : undefined}
        />
        <MetricCard
          label="Best Solve Rate"
          value={`${bestRate.toFixed(1)}%`}
          icon={<TrendingUp size={18} />}
          accent="green"
        />
        <MetricCard
          label="Total Cost"
          value={`$${totalCost.toFixed(2)}`}
          icon={<DollarSign size={18} />}
          accent="amber"
        />
      </div>

      <SectionCard title="Recent Experiments">
        <DataTable
          columns={columns}
          data={recent}
          rowKey={(r) => r.id}
          onRowClick={(r) => navigate(`/experiments/${r.id}`)}
        />
      </SectionCard>
    </div>
  );
}
