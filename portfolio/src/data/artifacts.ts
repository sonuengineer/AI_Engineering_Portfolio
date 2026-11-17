import generated from "./generated/artifacts.json";

type Json = string | number | boolean | null | Json[] | { [k: string]: Json };
const data = generated as unknown as { artifacts: Record<string, Record<string, Json>>; screenshots: Record<string, string[]> };

export const screenshotsFor = (slug: string): string[] => data.screenshots[slug] ?? [];
export const artifactsFor = (slug: string): Record<string, Json> => data.artifacts[slug] ?? {};

/** Flatten numeric leaves of an artifact for display: "chat_ask_ms.p50" -> 37.9. */
export function numericLeaves(value: Json, prefix = ""): { key: string; value: number }[] {
  if (typeof value === "number") return [{ key: prefix, value }];
  if (Array.isArray(value)) {
    // Arrays of records (e.g. runs) are keyed by their "label" when present, else by index.
    return value.flatMap((v, i) => {
      const label = v && typeof v === "object" && !Array.isArray(v) && typeof (v as Record<string, Json>).label === "string"
        ? ((v as Record<string, Json>).label as string) : String(i);
      return numericLeaves(v, prefix ? `${prefix}[${label}]` : label);
    });
  }
  if (value && typeof value === "object") {
    return Object.entries(value).flatMap(([k, v]) => numericLeaves(v, prefix ? `${prefix}.${k}` : k));
  }
  return [];
}

export function stringField(value: Json, key: string): string | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const v = (value as Record<string, Json>)[key];
    return typeof v === "string" ? v : null;
  }
  return null;
}
