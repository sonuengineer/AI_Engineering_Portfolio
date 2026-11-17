// Types mirroring the EVALOPS backend (app/schemas, services/run_queries.py,
// services/aggregation.py, services/comparison.py).

export type Role = "admin" | "member" | "viewer";

export interface User {
  id: string;
  org_id: string;
  email: string;
  display_name: string;
  role: Role | string;
}

export interface Project {
  id: string;
  name: string;
  slug: string;
  description: string;
  created_at: string;
}

export interface DatasetVersion {
  id: string;
  dataset_id: string;
  version: number;
  content_hash: string;
  case_count: number;
  notes: string;
  source_filename: string | null;
  created_at: string;
}

export interface Dataset {
  id: string;
  project_id: string;
  name: string;
  description: string;
  created_at: string;
  versions: DatasetVersion[];
}

export interface TestCase {
  id: string;
  external_id: string;
  position: number;
  input: string;
  expected_output: string | null;
  reference_contexts: string[];
  expected_citations: string[];
  tags: string[];
  metadata: Record<string, unknown>;
}

export interface Target {
  id: string;
  project_id: string;
  name: string;
  kind: string;
  model_config_id: string | null;
  prompt_version_id: string | null;
  config: Record<string, unknown>;
}

export interface ModelConfig {
  id: string;
  project_id: string;
  name: string;
  provider: string;
  model: string;
  params: Record<string, unknown>;
  price_in_per_1k: number;
  price_out_per_1k: number;
}

export interface Evaluator {
  id: string;
  project_id: string;
  name: string;
  type: string;
  kind: "deterministic" | "judge" | string;
  params: Record<string, unknown>;
  threshold: number | null;
  gating: boolean;
}

export interface Experiment {
  id: string;
  project_id: string;
  name: string;
  description: string;
  dataset_id: string | null;
  created_at: string;
}

export interface Provider {
  name: string;
  configured: boolean;
  is_real_llm: boolean;
  label: string;
}

export interface MetricSummary {
  scored: number;
  skipped: number;
  errors: number;
  passed: number;
  is_estimate: boolean;
  gating: boolean;
  pass_rate: number | null;
  mean: number | null;
}

export interface RunSummary {
  case_count: number;
  error_count: number;
  error_rate: number;
  cases_judged: number;
  cases_passed: number;
  overall_pass_rate: number | null;
  latency_ms: { mean: number | null; p50: number | null; p95: number | null; max: number | null };
  tokens: { input: number; output: number; total: number };
  cost_usd: number;
  wall_seconds: number | null;
  throughput_cases_per_sec: number | null;
  metrics: Record<string, MetricSummary>;
}

export type RunStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface Run {
  id: string;
  project_id: string;
  experiment_id: string | null;
  dataset_version_id: string;
  target_id: string;
  target_name: string | null;
  target_kind: string | null;
  provider: string | null;
  model: string | null;
  is_deterministic_provider: boolean;
  label: string;
  status: RunStatus | string;
  error: string | null;
  seed: number;
  git_sha: string | null;
  dataset_hash: string | null;
  config_snapshot?: Record<string, unknown>;
  summary: RunSummary | null;
  progress_done: number;
  progress_total: number;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface Score {
  metric: string;
  status: "scored" | "skipped" | "error" | string;
  value: number | null;
  passed: boolean | null;
  is_estimate: boolean;
  gating: boolean;
  explanation: string | null;
  details: Record<string, unknown> | null;
}

export interface CaseResult {
  id: string;
  external_id: string;
  input: string | null;
  expected_output: string | null;
  tags: string[];
  output_text: string | null;
  output_json: Record<string, unknown> | null;
  latency_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  tokens_estimated: boolean;
  cost_usd: number;
  error: string | null;
  attempts: number;
  passed: boolean | null;
  trace_id: string | null;
  scores: Score[];
}

export interface CompareMetricRow {
  metric: string;
  baseline_pass_rate: number | null;
  candidate_pass_rate: number | null;
  baseline_mean?: number | null;
  candidate_mean?: number | null;
  delta: number | null;
  tolerance: number;
  is_estimate: boolean;
  regression: boolean;
}

export interface CompareOpRow {
  name: string;
  baseline: number | null;
  candidate: number | null;
  delta: number | null;
  regression: boolean;
}

export interface CompareCases {
  newly_failing: string[];
  newly_passing: string[];
  still_failing: string[];
  only_in_baseline: string[];
  only_in_candidate: string[];
}

export interface CompareResult {
  metrics: CompareMetricRow[];
  operational: CompareOpRow[];
  regressions: string[];
  has_regression: boolean;
  cases: CompareCases;
  same_dataset: boolean;
  baseline: Run;
  candidate: Run;
}

export interface Span {
  id: string;
  parent_span_id: string | null;
  name: string;
  span_type: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  status: string;
  attributes: Record<string, unknown>;
}

export interface Trace {
  id: string;
  run_id: string | null;
  name: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  status: string;
  attributes: Record<string, unknown>;
  spans: Span[];
}

export interface RunCreate {
  project_id: string;
  dataset_version_id: string;
  target_ids: string[];
  evaluator_ids: string[];
  experiment_id?: string | null;
  label: string;
  concurrency: number;
  timeout_s: number;
  max_retries: number;
  seed: number;
}

export const TERMINAL_STATUSES = ["completed", "failed", "cancelled"];
