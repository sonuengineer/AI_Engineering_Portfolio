export type AskStatus = "answered" | "needs_clarification" | "rejected";

export interface QueryPlan {
  metrics: string[];
  dimensions: string[];
  filters: { field: string; kind: string; op: string; value: string | number | string[] }[];
  time_range: { start: string; end: string; label: string } | null;
  order_by: { field: string; direction: "asc" | "desc" }[];
  limit: number;
  assumptions: string[];
}

export interface Provenance {
  columns: string[];
  row_indexes: number[];
  note: string;
}

export interface ChartSpec {
  type: "line" | "bar" | "table";
  x: string | null;
  y: string[];
  series: string | null;
}

export type Cell = string | number | boolean | null;

export interface AskResponse {
  status: AskStatus;
  plan: QueryPlan | null;
  sql: string | null;
  validation: { ok: boolean; issues: string[] };
  columns: string[];
  rows: Cell[][];
  row_count: number;
  insight: string | null;
  clarification: { question: string; options: string[] } | null;
  rejection_reason: string | null;
  provider: string;
  model: string | null;
  latency_ms: number;
  query_id: number | null;
  chart: ChartSpec | null;
  insight_provenance: Provenance[];
}

export interface HistoryItem {
  id: number;
  question: string;
  status: string;
  sql: string | null;
  row_count: number;
  provider: string;
  latency_ms: number;
  created_at: string;
  user_id: number;
}

export interface SavedReport {
  id: number;
  name: string;
  question: string;
  plan: QueryPlan;
  created_at: string;
  updated_at: string;
  user_id: number;
}

export interface Me {
  id: number;
  email: string;
  full_name: string;
  role: string;
  org_id: number;
  org_name: string;
}

export interface Catalog {
  data_range: { start: string; end: string };
  tables: { name: string; description: string; columns: { name: string; type: string }[] }[];
  metrics: { name: string; label: string; description: string; fact: string; format: string; synonyms: string[] }[];
  dimensions: { name: string; label: string; description: string; synonyms: string[]; facts: string[]; is_time: boolean }[];
  facts: { name: string; description: string; from: string; joins: string[]; time_column: string }[];
}
