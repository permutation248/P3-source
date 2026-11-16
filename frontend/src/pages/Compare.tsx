import { useState } from 'react';
import { Scale } from 'lucide-react';
import { useExperiments } from '../hooks';
import { createComparison } from '../api/client';
import {
  MetricCard,
  LoadingSpinner,
  PageHeader,
  SectionCard,
  FormField,
  selectClass,
  btnPrimary,
} from '../components/shared';
import type { Comparison } from '../types';

function formatPValue(p: number | null): { text: string; stars: string } {
  if (p === null) return { text: 'N/A', stars: '' };
  const text = p < 0.001 ? p.toExponential(2) : p.toFixed(4);
  const stars = p < 0.001 ? '***' : p < 0.01 ? '**' : p < 0.05 ? '*' : '';
  return { text, stars };
}

export default function Compare() {
  const { experiments, loading: expLoading } = useExperiments();
  const [baselineId, setBaselineId] = useState<number | ''>('');
  const [treatmentId, setTreatmentId] = useState<number | ''>('');
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = async () => {
    if (baselineId === '' || treatmentId === '') return;
    setSubmitting(true);
    setError(null);
    setComparison(null);
    try {
      const result = await createComparison({
        baseline_experiment_id: baselineId,
        treatment_experiment_id: treatmentId,
      });
      setComparison(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Comparison failed');
    } finally {
      setSubmitting(false);
    }
  };

  const baselineExp = experiments.find((e) => e.id === baselineId);
  const treatmentExp = experiments.find((e) => e.id === treatmentId);

  const delta = comparison ? (comparison.delta ?? 0) : 0;

  const mcnemar = comparison ? formatPValue(comparison.mcnemar_p_value) : null;
  const wilcoxonTime = comparison ? formatPValue(comparison.wilcoxon_time_p_value) : null;
  const wilcoxonCost = comparison ? formatPValue(comparison.wilcoxon_cost_p_value) : null;

  const metricRows = comparison && baselineExp && treatmentExp
    ? [
        {
          metric: 'Solve Rate',
          baseline: `${(comparison.baseline_solved_rate ?? 0).toFixed(1)}%`,
          treatment: `${(comparison.treatment_solved_rate ?? 0).toFixed(1)}%`,
          delta: `${(comparison.delta ?? 0).toFixed(1)}pp`,
          deltaPct: (comparison.baseline_solved_rate ?? 0) > 0
            ? `${(((comparison.delta ?? 0) / (comparison.baseline_solved_rate ?? 1)) * 100).toFixed(1)}%`
            : 'N/A',
        },
        {
          metric: 'Avg Time (s)',
          baseline: (baselineExp.avg_time_seconds ?? 0).toFixed(1),
          treatment: (treatmentExp.avg_time_seconds ?? 0).toFixed(1),
          delta: ((treatmentExp.avg_time_seconds ?? 0) - (baselineExp.avg_time_seconds ?? 0)).toFixed(1),
          deltaPct: (baselineExp.avg_time_seconds ?? 0) > 0
            ? `${((((treatmentExp.avg_time_seconds ?? 0) - (baselineExp.avg_time_seconds ?? 0)) / (baselineExp.avg_time_seconds ?? 1)) * 100).toFixed(1)}%`
            : 'N/A',
        },
        {
          metric: 'Total Cost ($)',
          baseline: `$${(baselineExp.total_cost_usd ?? 0).toFixed(2)}`,
          treatment: `$${(treatmentExp.total_cost_usd ?? 0).toFixed(2)}`,
          delta: `$${((treatmentExp.total_cost_usd ?? 0) - (baselineExp.total_cost_usd ?? 0)).toFixed(2)}`,
          deltaPct: (baselineExp.total_cost_usd ?? 0) > 0
            ? `${((((treatmentExp.total_cost_usd ?? 0) - (baselineExp.total_cost_usd ?? 0)) / (baselineExp.total_cost_usd ?? 1)) * 100).toFixed(1)}%`
            : 'N/A',
        },
        {
          metric: 'Avg Turns',
          baseline: (baselineExp.avg_turns ?? 0).toFixed(1),
          treatment: (treatmentExp.avg_turns ?? 0).toFixed(1),
          delta: ((treatmentExp.avg_turns ?? 0) - (baselineExp.avg_turns ?? 0)).toFixed(1),
          deltaPct: (baselineExp.avg_turns ?? 0) > 0
            ? `${((((treatmentExp.avg_turns ?? 0) - (baselineExp.avg_turns ?? 0)) / (baselineExp.avg_turns ?? 1)) * 100).toFixed(1)}%`
            : 'N/A',
        },
      ]
    : [];

  return (
    <div className="space-y-8">
      <PageHeader
        title="Compare Experiments"
        subtitle="Statistical comparison of two experiments"
        symbol="≡"
      />

      {/* Selection */}
      <SectionCard title="Select Experiments">
        {expLoading ? (
          <LoadingSpinner size="sm" />
        ) : (
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex-1 min-w-[200px]">
              <FormField label="Baseline">
                <select
                  value={baselineId}
                  onChange={(e) => setBaselineId(e.target.value ? Number(e.target.value) : '')}
                  className={selectClass}
                >
                  <option value="">Select experiment...</option>
                  {experiments.map((exp) => (
                    <option key={exp.id} value={exp.id}>
                      {exp.name} ({exp.mode}, {(exp.solved_rate ?? 0).toFixed(1)}%)
                    </option>
                  ))}
                </select>
              </FormField>
            </div>

            <div className="flex items-center pb-2.5 text-ink-300">
              <Scale size={20} />
            </div>

            <div className="flex-1 min-w-[200px]">
              <FormField label="Treatment">
                <select
                  value={treatmentId}
                  onChange={(e) => setTreatmentId(e.target.value ? Number(e.target.value) : '')}
                  className={selectClass}
                >
                  <option value="">Select experiment...</option>
                  {experiments.map((exp) => (
                    <option key={exp.id} value={exp.id}>
                      {exp.name} ({exp.mode}, {(exp.solved_rate ?? 0).toFixed(1)}%)
                    </option>
                  ))}
                </select>
              </FormField>
            </div>

            <div className="pb-0.5">
              <button
                onClick={handleCompare}
                disabled={baselineId === '' || treatmentId === '' || submitting}
                className={btnPrimary}
              >
                {submitting ? 'Comparing...' : 'Compare'}
              </button>
            </div>
          </div>
        )}
      </SectionCard>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-proof-red">
          {error}
        </div>
      )}

      {/* Results */}
      {comparison && (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <MetricCard label="Common Tasks" value={comparison.common_tasks ?? 0} accent="violet" />
            <MetricCard
              label="Baseline Rate"
              value={`${(comparison.baseline_solved_rate ?? 0).toFixed(1)}%`}
              accent="blue"
            />
            <MetricCard
              label="Treatment Rate"
              value={`${(comparison.treatment_solved_rate ?? 0).toFixed(1)}%`}
              accent="green"
            />
            <MetricCard
              label="Delta"
              value={`${(comparison.delta ?? 0).toFixed(1)}pp`}
              accent="amber"
              trend={
                delta !== 0
                  ? { direction: delta > 0 ? 'up' : 'down', text: `${delta > 0 ? '+' : ''}${delta.toFixed(1)}pp` }
                  : undefined
              }
            />
          </div>

          {/* Statistical Tests */}
          <SectionCard title="Statistical Tests">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-ink-100">
                <thead>
                  <tr className="text-left">
                    <th className="pb-3 text-[11px] font-semibold uppercase tracking-wider text-ink-400">Test</th>
                    <th className="pb-3 text-[11px] font-semibold uppercase tracking-wider text-ink-400">P-Value</th>
                    <th className="pb-3 text-[11px] font-semibold uppercase tracking-wider text-ink-400">Sig.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-50">
                  {[
                    { name: 'McNemar (Solve Rate)', data: mcnemar },
                    { name: 'Wilcoxon (Time)', data: wilcoxonTime },
                    { name: 'Wilcoxon (Cost)', data: wilcoxonCost },
                  ].map((row) => (
                    <tr key={row.name}>
                      <td className="py-3 text-sm text-ink-700">{row.name}</td>
                      <td className="py-3 font-mono text-sm text-ink-600">{row.data?.text}</td>
                      <td className="py-3 font-mono text-sm font-bold text-proof-amber">{row.data?.stars || '\u2014'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>

          {/* Metric Comparison */}
          <SectionCard title="Metric Comparison">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-ink-100">
                <thead>
                  <tr className="text-left">
                    {['Metric', 'Baseline', 'Treatment', 'Delta', 'Delta %'].map((h) => (
                      <th key={h} className="pb-3 text-[11px] font-semibold uppercase tracking-wider text-ink-400">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-50">
                  {metricRows.map((row) => (
                    <tr key={row.metric}>
                      <td className="py-3 text-sm font-medium text-ink-700">{row.metric}</td>
                      <td className="py-3 font-mono text-sm text-ink-600">{row.baseline}</td>
                      <td className="py-3 font-mono text-sm text-ink-600">{row.treatment}</td>
                      <td className={`py-3 font-mono text-sm font-semibold ${
                        delta > 0 ? 'text-proof-green' : delta < 0 ? 'text-proof-red' : 'text-ink-500'
                      }`}>
                        {row.delta}
                      </td>
                      <td className="py-3 font-mono text-sm text-ink-400">{row.deltaPct}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </>
      )}
    </div>
  );
}
