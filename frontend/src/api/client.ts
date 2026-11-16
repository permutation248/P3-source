import type { Experiment, ExperimentCreate, TaskResult, Comparison, PaginatedResponse } from '../types';

const BASE_URL = '/api';

/** Auth details supplied per mutating request. Always derived from the
 *  active backend in Settings via ``authForFamily()`` — experiments never
 *  carry their own backend, so changing Settings immediately changes the
 *  next run (new or rerun) without touching the experiment record. */
export interface RequestAuth {
  /** ``'default'`` = omit X-Backend header (server uses baseline env). */
  backend: 'api' | 'miromind' | 'subscription' | 'default' | null;
  /** Empty for subscription/default; otherwise the stored key from Settings. */
  apiKey?: string;
  /** null/undefined = omit X-Use-Docker header (server env default wins). */
  useDocker?: boolean | null;
}

function baseHeaders(): Record<string, string> {
  return { 'Content-Type': 'application/json' };
}

function withAuth(auth?: RequestAuth): Record<string, string> {
  const headers = baseHeaders();
  if (auth) {
    // 'default' and null both mean "don't send X-Backend" — server falls
    // back to baseline env/OAuth. Only concrete routing choices go on the wire.
    if (auth.backend && auth.backend !== 'default') {
      headers['X-Backend'] = auth.backend;
    }
    if (auth.apiKey) headers['X-API-Key'] = auth.apiKey;
    // X-Use-Docker is tri-state: omit when null/undefined, let server env decide.
    if (auth.useDocker === true) headers['X-Use-Docker'] = 'true';
    else if (auth.useDocker === false) headers['X-Use-Docker'] = 'false';
  }
  return headers;
}

async function request<T>(path: string, options?: RequestInit, auth?: RequestAuth): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: withAuth(auth),
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json();
}

/** Unwrap the `API error <code>: <body>` format produced by request(). If
 *  the body is a FastAPI ``{"detail": "..."}`` envelope, return the detail;
 *  otherwise return the raw body. Non-Error inputs fall back to *fallback*. */
export function extractApiError(err: unknown, fallback = 'Request failed.'): string {
  if (!(err instanceof Error)) return fallback;
  const m = err.message.match(/^API error \d+: (.+)$/s);
  if (!m) return err.message;
  try {
    const parsed = JSON.parse(m[1]);
    if (parsed && typeof parsed.detail === 'string') return parsed.detail;
  } catch {
    /* fall through */
  }
  return m[1];
}

export async function listExperiments(params?: {
  mode?: string;
  model?: string;
}): Promise<Experiment[]> {
  const searchParams = new URLSearchParams();
  if (params?.mode) searchParams.set('mode', params.mode);
  if (params?.model) searchParams.set('model', params.model);
  const qs = searchParams.toString();
  return request<Experiment[]>(`/experiments${qs ? `?${qs}` : ''}`);
}

export async function getExperiment(id: number): Promise<Experiment> {
  return request<Experiment>(`/experiments/${id}`);
}

export async function createExperiment(
  data: ExperimentCreate,
  auth?: RequestAuth,
): Promise<Experiment> {
  return request<Experiment>(
    '/experiments',
    {
      method: 'POST',
      body: JSON.stringify(data),
    },
    auth,
  );
}

export async function stopExperiment(id: number): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/experiments/${id}/stop`, { method: 'POST' });
}

export async function restartExperiment(id: number, auth?: RequestAuth): Promise<Experiment> {
  return request<Experiment>(`/experiments/${id}/restart`, { method: 'POST' }, auth);
}

export async function resumeExperiment(id: number, auth?: RequestAuth): Promise<Experiment> {
  return request<Experiment>(`/experiments/${id}/resume`, { method: 'POST' }, auth);
}

export async function deleteExperiment(id: number): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/experiments/${id}`, { method: 'DELETE' });
}

export async function getTaskDetail(expId: number, taskName: string): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/tasks/${expId}/${encodeURIComponent(taskName)}`);
}

export async function listProofFiles(expId: number, taskName: string): Promise<{ name: string; size: number }[]> {
  return request<{ name: string; size: number }[]>(`/proofs/${expId}/${encodeURIComponent(taskName)}`);
}

export async function readProofFile(expId: number, taskName: string, filePath: string): Promise<string> {
  const res = await fetch(`${BASE_URL}/proofs/${expId}/${encodeURIComponent(taskName)}/file?path=${encodeURIComponent(filePath)}`, {
    headers: baseHeaders(),
  });
  if (!res.ok) throw new Error(`API error ${res.status}`);
  return res.text();
}

export async function getResultSummary(expId: number): Promise<Record<string, unknown>> {
  return request<Record<string, unknown>>(`/results/${expId}/summary`);
}

export async function listTaskResults(
  expId: number,
  params?: {
    page?: number;
    page_size?: number;
    solved?: boolean;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
  },
): Promise<PaginatedResponse<TaskResult>> {
  const searchParams = new URLSearchParams();
  if (params?.page !== undefined) searchParams.set('page', String(params.page));
  if (params?.page_size !== undefined) searchParams.set('page_size', String(params.page_size));
  if (params?.solved !== undefined) searchParams.set('solved', String(params.solved));
  if (params?.sort_by) searchParams.set('sort_by', params.sort_by);
  if (params?.sort_order) searchParams.set('sort_order', params.sort_order);
  const qs = searchParams.toString();
  return request<PaginatedResponse<TaskResult>>(`/results/${expId}/tasks${qs ? `?${qs}` : ''}`);
}

export async function createComparison(data: {
  baseline_experiment_id: number;
  treatment_experiment_id: number;
}): Promise<Comparison> {
  return request<Comparison>('/comparisons', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getComparison(id: number): Promise<Comparison> {
  return request<Comparison>(`/comparisons/${id}`);
}

export async function listAgentConfigs(): Promise<Record<string, unknown>[]> {
  return request<Record<string, unknown>[]>('/config/agents');
}

export async function listBenchmarks(): Promise<Record<string, unknown>[]> {
  return request<Record<string, unknown>[]>('/config/benchmarks');
}
