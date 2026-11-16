import { useState, useEffect, useMemo } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Play, X } from 'lucide-react';
import { createExperiment, extractApiError } from '../api/client';
import {
  PageHeader,
  SectionCard,
  FormField,
  inputClass,
  selectClass,
  btnPrimary,
  btnSecondary,
} from '../components/shared';
import type { ExperimentCreate } from '../types';
import { useApiKey, BACKEND_LABELS, familyForExperiment } from '../contexts/ApiKeyContext';

interface Dataset {
  name: string;
  path: string;
  tasks_mode?: 'file' | 'project';
  task_count: number;
  task_count_file?: number;
  task_count_project?: number;
}

export default function NewExperiment() {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { authForFamily, activeBackend } = useApiKey();

  const [datasets, setDatasets] = useState<Dataset[]>([]);

  useEffect(() => {
    fetch('/api/datasets')
      .then((res) => res.json())
      .then(setDatasets)
      .catch(() => {});
  }, []);

  const [form, setForm] = useState({
    name: '',
    mode: 'auto' as ExperimentCreate['mode'],
    skills_config: 'none',
    tasks_dir: '',
    tasks_mode: 'file' as NonNullable<ExperimentCreate['tasks_mode']>,
    model: 'claude-sonnet-4-6',
    parallel: 4,
    task_timeout_minutes: 30,
    max_cost_usd: null as number | null,
    notify_email: '',
    custom_prompt: '',
  });

  const family = useMemo(() => familyForExperiment(undefined, form.model), [form.model]);

  useEffect(() => {
    if (datasets.length > 0 && !form.tasks_dir) {
      const first = datasets[0];
      setForm((prev) => ({
        ...prev,
        tasks_dir: first.path,
        tasks_mode: first.tasks_mode ?? prev.tasks_mode,
      }));
    }
  }, [datasets]);

  const update = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const taskCountFor = (d: Dataset) =>
    form.tasks_mode === 'project'
      ? (d.task_count_project ?? d.task_count)
      : (d.task_count_file ?? d.task_count);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim()) {
      setError('Name is required');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const { task_timeout_minutes, notify_email, custom_prompt, ...rest } = form;
      const payload: ExperimentCreate = {
        ...rest,
        task_timeout_seconds: task_timeout_minutes * 60,
        ...(notify_email.trim() ? { notify_email: notify_email.trim() } : {}),
        ...(custom_prompt.trim() ? { custom_prompt } : {}),
      };
      const exp = await createExperiment(payload, authForFamily(family));
      navigate(`/experiments/${exp.id}`);
    } catch (err) {
      setError(extractApiError(err));
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader
        title="New Experiment"
        subtitle="Configure and launch a verification experiment"
        symbol="⊢"
      />

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-proof-red">
          {error}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Custom Prompt */}
        <SectionCard title="Custom Prompt">
          <FormField
            label="Prompt Override"
            hint="Leave empty to use the default. Use {target_path} as a placeholder for the task file path."
          >
            <textarea
              value={form.custom_prompt}
              onChange={(e) => update('custom_prompt', e.target.value)}
              placeholder="e.g., /lean4-codeprover auto {target_path}"
              rows={6}
              className={`${inputClass} font-mono text-sm`}
            />
          </FormField>
        </SectionCard>

        {/* Basic Config */}
        <SectionCard title="Configuration">
          <div className="space-y-5">
            <FormField label="Experiment Name">
              <input
                type="text"
                value={form.name}
                onChange={(e) => update('name', e.target.value)}
                placeholder="e.g., sonnet-auto-standard-v1"
                className={inputClass}
              />
            </FormField>

            <div className="grid grid-cols-2 gap-4">
              <FormField label="Mode">
                <select
                  value={form.mode}
                  onChange={(e) => update('mode', e.target.value as ExperimentCreate['mode'])}
                  className={selectClass}
                >
                  <option value="auto">Auto</option>
                  <option value="code">Code</option>
                  <option value="proof">Proof</option>
                </select>
              </FormField>

              <FormField label="Model">
                <select
                  value={form.model}
                  onChange={(e) => update('model', e.target.value)}
                  className={selectClass}
                >
                  <option value="claude-sonnet-4-6">Claude-Sonnet-4.6</option>
                  <option value="claude-opus-4-6">Claude-Opus-4.6</option>
                  <option value="gpt-5.3-codex">GPT-5.3-Codex</option>
                  <option value="gpt-5.4">GPT-5.4</option>
                </select>
              </FormField>
            </div>

            <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-ink-500">
              Backend for this run:{' '}
              <span className="font-mono text-ink-700">{BACKEND_LABELS[activeBackend[family]]}</span>{' '}
              · change in{' '}
              <Link to="/settings" className="underline hover:text-ink-700">
                Settings
              </Link>
              .
            </div>

            <FormField label="Skills Config">
              <select
                value={form.skills_config}
                onChange={(e) => update('skills_config', e.target.value)}
                className={selectClass}
              >
                <option value="none">None (baseline)</option>
                <option value="standard">Standard (no negation)</option>
                <option value="extended">Extended (with negation)</option>
                <option value="co_derivation">Co-Derivation</option>
                <option value="docs_only">Docs Only</option>
                <option value="tools_only">Tools Only</option>
              </select>
            </FormField>

            <FormField label="Dataset">
              <select
                value={form.tasks_dir}
                onChange={(e) => {
                  const selectedPath = e.target.value;
                  const d = datasets.find((x) => x.path === selectedPath);
                  setForm((prev) => ({
                    ...prev,
                    tasks_dir: selectedPath,
                    tasks_mode: d?.tasks_mode ?? prev.tasks_mode,
                  }));
                }}
                className={selectClass}
              >
                {datasets.map((d) => (
                  <option key={d.path} value={d.path}>
                    {d.name} ({taskCountFor(d)} tasks)
                  </option>
                ))}
                {datasets.length === 0 && (
                  <option value="">No datasets available</option>
                )}
              </select>
            </FormField>

            <FormField label="Task Discovery Mode">
              <select
                value={form.tasks_mode}
                onChange={(e) => update('tasks_mode', e.target.value as NonNullable<ExperimentCreate['tasks_mode']>)}
                className={selectClass}
              >
                <option value="file">file (each .lean file is a task)</option>
                <option value="project">project (each folder with .lean files is a task)</option>
              </select>
            </FormField>
          </div>
        </SectionCard>

        {/* Resources */}
        <SectionCard title="Resources">
          <div className="space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <FormField label="Parallel Workers">
                <input
                  type="number"
                  min={1}
                  max={32}
                  value={form.parallel}
                  onChange={(e) => update('parallel', Number(e.target.value))}
                  className={inputClass}
                />
              </FormField>
              <FormField label="Task Timeout (min)">
                <input
                  type="number"
                  min={1}
                  value={form.task_timeout_minutes}
                  onChange={(e) => update('task_timeout_minutes', Number(e.target.value))}
                  className={inputClass}
                />
              </FormField>
            </div>

            <FormField label="Max Cost per Task" hint="USD, leave empty for unlimited">
              <input
                type="number"
                min={0.01}
                step={0.01}
                value={form.max_cost_usd ?? ''}
                onChange={(e) => update('max_cost_usd', e.target.value ? Number(e.target.value) : null)}
                placeholder="e.g., 5.00"
                className={inputClass}
              />
            </FormField>
          </div>
        </SectionCard>

        {/* Notifications */}
        <SectionCard title="Notifications">
          <FormField label="Email" hint="leave empty for default">
            <input
              type="email"
              value={form.notify_email}
              onChange={(e) => update('notify_email', e.target.value)}
              placeholder="recipient@example.invalid"
              className={inputClass}
            />
          </FormField>
        </SectionCard>

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2">
          <button type="button" onClick={() => navigate('/experiments')} className={btnSecondary}>
            <X size={16} />
            Cancel
          </button>
          <button type="submit" disabled={submitting} className={btnPrimary}>
            <Play size={16} />
            {submitting ? 'Creating...' : 'Launch Experiment'}
          </button>
        </div>
      </form>
    </div>
  );
}
