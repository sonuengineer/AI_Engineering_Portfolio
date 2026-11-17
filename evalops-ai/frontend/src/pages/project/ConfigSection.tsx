import { api } from "../../api/client";
import type { Evaluator, ModelConfig, Target } from "../../api/types";
import { Badge } from "../../components/Badge";
import { DataState } from "../../components/DataState";
import { useApi } from "../../lib/useApi";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-6" aria-label={title}>
      <h2 className="mb-2 text-lg font-semibold">{title}</h2>
      {children}
    </section>
  );
}

const card = "rounded-lg border border-slate-200 bg-white p-3 text-sm";

export function ConfigSection({ projectId }: { projectId: string }) {
  const targets = useApi((signal) => api<Target[]>(`/api/v1/projects/${projectId}/targets`, { signal }), [projectId]);
  const evaluators = useApi((signal) => api<Evaluator[]>(`/api/v1/projects/${projectId}/evaluators`, { signal }), [projectId]);
  const models = useApi((signal) => api<ModelConfig[]>(`/api/v1/projects/${projectId}/model-configs`, { signal }), [projectId]);
  const modelName = (id: string | null) => models.data?.find((m) => m.id === id)?.name ?? id ?? "--";

  return (
    <>
      <Section title="Targets">
        <DataState {...targets} isEmpty={(d) => d.length === 0} empty="No targets.">
          {(ts) => (
            <ul className="grid gap-2 sm:grid-cols-2">
              {ts.map((t) => (
                <li key={t.id} className={card}>
                  <p className="font-medium">{t.name}</p>
                  <p className="text-xs text-slate-600">
                    kind <span className="font-mono">{t.kind}</span>
                    {t.model_config_id && <> | model config: {modelName(t.model_config_id)}</>}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </DataState>
      </Section>
      <Section title="Evaluators">
        <DataState {...evaluators} isEmpty={(d) => d.length === 0} empty="No evaluators.">
          {(es) => (
            <ul className="grid gap-2 sm:grid-cols-2">
              {es.map((e) => (
                <li key={e.id} className={card}>
                  <p className="flex flex-wrap items-center gap-1.5 font-medium">
                    <span className="font-mono">{e.name}</span>
                    <Badge tone={e.kind === "judge" ? "purple" : "blue"}>{e.kind}</Badge>
                    {!e.gating && <Badge>non-gating</Badge>}
                  </p>
                  <p className="text-xs text-slate-600">
                    type <span className="font-mono">{e.type}</span>
                    {e.threshold !== null && <> | threshold {e.threshold}</>}
                  </p>
                  {Object.keys(e.params).length > 0 && (
                    <pre className="mt-1 overflow-x-auto text-xs text-slate-700">{JSON.stringify(e.params)}</pre>
                  )}
                </li>
              ))}
            </ul>
          )}
        </DataState>
      </Section>
      <Section title="Model configs">
        <DataState {...models} isEmpty={(d) => d.length === 0} empty="No model configs.">
          {(ms) => (
            <ul className="grid gap-2 sm:grid-cols-2">
              {ms.map((m) => (
                <li key={m.id} className={card}>
                  <p className="font-medium">{m.name}</p>
                  <p className="text-xs text-slate-600">
                    <span className="font-mono">
                      {m.provider} / {m.model}
                    </span>{" "}
                    | in ${m.price_in_per_1k}/1k, out ${m.price_out_per_1k}/1k
                  </p>
                </li>
              ))}
            </ul>
          )}
        </DataState>
      </Section>
    </>
  );
}
