import { useState, useEffect, useRef, useCallback } from 'react';
import type { Experiment, ExperimentProgress } from '../types';
import { listExperiments, getExperiment } from '../api/client';

export function useExperiments(params?: { mode?: string; model?: string }) {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listExperiments(params);
      setExperiments(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load experiments');
    } finally {
      setLoading(false);
    }
  }, [params?.mode, params?.model]);

  useEffect(() => {
    load();
  }, [load]);

  return { experiments, loading, error, refresh: load };
}

export function useExperiment(id: number | undefined) {
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (silent = false) => {
    if (id === undefined) return;
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const data = await getExperiment(id);
      setExperiment(data);
    } catch (err) {
      if (!silent) setError(err instanceof Error ? err.message : 'Failed to load experiment');
    } finally {
      if (!silent) setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const silentRefresh = useCallback(() => load(true), [load]);

  return { experiment, loading, error, refresh: load, silentRefresh };
}

export function useWebSocket(experimentId: number | undefined) {
  const [progress, setProgress] = useState<ExperimentProgress | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (experimentId === undefined) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/experiments/${experimentId}/progress`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (event) => {
      try {
        const raw = JSON.parse(event.data) as Partial<ExperimentProgress>;
        const hasProgressPayload =
          raw &&
          typeof raw === 'object' &&
          (typeof raw.status === 'string' ||
            typeof raw.completed === 'number' ||
            typeof raw.total === 'number' ||
            typeof raw.solved_count === 'number');

        // Backend may emit empty {} while progress is not initialized yet.
        // Ignore those heartbeats so they don't overwrite visible metrics.
        if (!hasProgressPayload) return;

        setProgress((prev) => {
          const status = typeof raw.status === 'string' ? raw.status : 'running';
          const completed = typeof raw.completed === 'number' ? raw.completed : 0;
          const total = typeof raw.total === 'number' ? raw.total : 0;
          const solved_count = typeof raw.solved_count === 'number' ? raw.solved_count : 0;
          const task_name = typeof raw.task_name === 'string' ? raw.task_name : null;
          if (
            prev &&
            prev.status === status &&
            prev.completed === completed &&
            prev.total === total &&
            prev.solved_count === solved_count &&
            prev.task_name === task_name
          ) {
            return prev;
          }
          return { status, completed, total, solved_count, task_name };
        });
      } catch {
        // ignore malformed messages
      }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [experimentId]);

  return { progress, connected };
}
