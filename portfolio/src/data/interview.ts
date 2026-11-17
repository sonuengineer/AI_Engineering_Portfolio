import generated from "./generated/interview.json";
import type { Handbook } from "./interviewTypes";

const data = generated as unknown as Record<string, Handbook | null>;
export const HANDBOOK_KEYS = ["nexus-ai", "datawise-ai", "evalops-ai", "cross-project"] as const;
export type HandbookKey = (typeof HANDBOOK_KEYS)[number];
export const handbook = (key: string | undefined): Handbook | null => (key ? data[key] ?? null : null);
export const HANDBOOK_NAMES: Record<HandbookKey, string> = {
  "nexus-ai": "NEXUS AI", "datawise-ai": "DATAWISE AI", "evalops-ai": "EVALOPS AI", "cross-project": "Cross-project",
};
