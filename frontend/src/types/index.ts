export interface Experiment {
  id: number;
  name: string;
  mode: 'code' | 'proof' | 'auto';
  skills_config: string | null;
  model: string;
  agent_type: string | null;
  tasks_dir: string | null;
  tasks_mode: 'file' | 'project' | null;
  total_tasks: number;
  solved_count: number;
  solved_rate: number; // 0–100 percentage
  avg_time_seconds: number;
  avg_cost_usd: number;
  total_cost_usd: number;
  avg_turns: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  summary_json: Record<string, unknown> | null;
  config_json: Record<string, unknown> | null;
}

export interface TaskResult {
  id: number;
  experiment_id: number;
  task_name: string;
  solved: boolean;
  sorry_count: number;
  error_count: number;
  compilation_error: boolean;
  timeout: boolean;
  total_time_seconds: number | null;
  total_tokens: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  cost_source: 'reported' | 'estimated' | 'none' | null;
  total_turns: number | null;
  mode: string;
  result_json: Record<string, unknown> | null;
}

export interface Comparison {
  id: number;
  baseline_experiment_id: number;
  treatment_experiment_id: number;
  common_tasks: number | null;
  baseline_solved_rate: number | null; // 0–100 percentage
  treatment_solved_rate: number | null; // 0–100 percentage
  delta: number | null; // percentage points
  mcnemar_p_value: number | null;
  wilcoxon_time_p_value: number | null;
  wilcoxon_cost_p_value: number | null;
  comparison_json: Record<string, unknown> | null;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface ExperimentProgress {
  status: string;
  completed: number;
  total: number;
  solved_count: number;
  task_name: string | null;
}

export interface ExperimentCreate {
  name: string;
  mode: 'code' | 'proof' | 'auto';
  skills_config?: string;
  tasks_dir?: string;
  tasks_mode?: 'file' | 'project';
  model?: string;
  parallel?: number;
  task_timeout_seconds?: number;
  max_cost_usd?: number | null;
  notify_email?: string;
  custom_prompt?: string;
}
