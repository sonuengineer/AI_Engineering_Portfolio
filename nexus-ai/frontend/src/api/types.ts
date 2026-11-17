export interface Me {
  id: string; email: string; full_name: string; role: string; org_id: string; org_name: string;
  llm_provider: string; embedding_provider: string;
}
export interface Citation {
  ref: number; chunk_id: string; document_id: string; document_title: string; page: number | null;
  section: string | null; snippet: string; flagged: boolean;
}
export interface RetrievalRow {
  chunk_id: string; document_title: string; page: number | null; vector_rank: number | null;
  keyword_rank: number | null; rerank_score: number; signals: Record<string, number>; flagged: boolean;
}
export interface AskResponse {
  conversation_id: string; message_id: string; answer: string; citations: Citation[]; contexts: string[];
  retrieval: RetrievalRow[]; insufficient_evidence: boolean; provider: string; model: string;
  usage: { input_tokens: number; output_tokens: number; estimated_cost_usd: number; tokens_are_estimates: boolean };
  latency_ms: number;
}
export interface Conversation { id: string; title: string; created_at: string }
export interface ChatMessage {
  id: string; role: "user" | "assistant"; content: string; citations: Citation[];
  meta: Record<string, unknown>; created_at: string;
}
export interface DocumentRow {
  id: string; title: string; source_type: string; source_uri: string | null; mime_type: string; size_bytes: number;
  status: "pending" | "processing" | "ready" | "failed"; error: string | null; page_count: number | null;
  chunk_count: number; meta: Record<string, unknown>; created_at: string;
}
export interface ToolCall { tool: string; args: Record<string, unknown>; ok: boolean; latency_ms: number; summary: string }
export interface Step {
  id: string; seq: number; name: string; agent: string; status: string; attempts: number;
  tool_calls: ToolCall[]; error: string | null; started_at: string | null; finished_at: string | null;
}
export interface Approval {
  id: string; run_id: string | null; action: string; status: string; rationale: string | null;
  payload: { to: string; subject: string; body: string; customer_name?: string; customer_id?: string };
  decided_by: string | null; decided_at: string | null; decision_note: string | null;
  result: Record<string, unknown> | null; created_at: string;
}
export interface Run {
  id: string; goal: string; kind: string; status: string; plan: string[]; error: string | null;
  tokens_used: number; token_budget: number; created_at: string; finished_at: string | null;
}
export interface Evidence { statement: string; source: string }
export interface Hypothesis { statement: string; confidence: "low" | "medium" | "high"; supporting_sources: string[] }
export interface Finding {
  customer_id: string; customer_name: string; evidence: Evidence[]; hypotheses: Hypothesis[]; recommended_action: string;
}
export interface DecliningCustomer {
  customer_id: string; name: string; prior_revenue: number; recent_revenue: number; change_pct: number;
  monthly: { month: string; orders: number; revenue: number; avg_delay_days: number }[];
}
export interface RunDetail extends Run {
  report: { title: string; markdown: string; analysis: { summary: string; findings: Finding[] } | null;
    declining: DecliningCustomer[] } | null;
  steps: Step[];
  approvals: Approval[];
}
export interface AuditRow {
  id: string; actor_id: string | null; action: string; target_type: string | null; target_id: string | null;
  outcome: string; details: Record<string, unknown>; request_id: string | null; created_at: string;
}
export interface UsageRow {
  purpose: string; provider: string; model: string; calls: number; input_tokens: number; output_tokens: number;
  estimated_cost_usd: number; avg_latency_ms: number;
}
export interface ToolInfo {
  name: string; description: string; side_effect: string; min_role: string; requires_approval: boolean; mcp_exposed: boolean;
}
export interface MemoryItem { id: string; key: string; value: string; source: string; created_at: string }
