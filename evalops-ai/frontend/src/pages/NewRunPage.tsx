import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Dataset, Evaluator, Experiment, RunCreate, Target } from "../api/types";
import { Badge } from "../components/Badge";
import { DataState, ErrorBox } from "../components/DataState";
import { PageTitle, btnPrimary, input, link } from "../components/Layout";
import { shortHash } from "../lib/format";
import { useApi } from "../lib/useApi";

interface FormData {
  datasets: Dataset[];
  targets: Target[];
  evaluators: Evaluator[];
  experiments: Experiment[];
}

export function NewRunPage() {
  const { projectId = "" } = useParams();
  const state = useApi(async (signal): Promise<FormData> => {
    const base = `/api/v1/projects/${projectId}`;
    const [datasets, targets, evaluators, experiments] = await Promise.all([
      api<Dataset[]>(`${base}/datasets`, { signal }),
      api<Target[]>(`${base}/targets`, { signal }),
      api<Evaluator[]>(`${base}/evaluators`, { signal }),
      api<Experiment[]>(`${base}/experiments`, { signal }),
    ]);
    return { datasets, targets, evaluators, experiments };
  }, [projectId]);

  return (
    <>
      <p className="mb-1 text-sm">
        <Link to={`/projects/${projectId}`} className={link}>
          Back to project
        </Link>
      </p>
      <PageTitle>New run</PageTitle>
      <DataState {...state} loadingLabel="Loading project resources">
        {(d) => <NewRunForm projectId={projectId} data={d} />}
      </DataState>
    </>
  );
}

const fieldset = "rounded-lg border border-slate-200 bg-white p-4";
const legend = "px-1 text-sm font-semibold text-slate-800";

function NewRunForm({ projectId, data }: { projectId: string; data: FormData }) {
  const navigate = useNavigate();
  const versions = data.datasets.flatMap((ds) => ds.versions.map((v) => ({ ds, v })));
  const [versionId, setVersionId] = useState(versions[0]?.v.id ?? "");
  const [targetIds, setTargetIds] = useState<string[]>([]);
  const [evaluatorIds, setEvaluatorIds] = useState<string[]>(data.evaluators.map((e) => e.id));
  const [experimentId, setExperimentId] = useState("");
  const [label, setLabel] = useState("");
  const [concurrency, setConcurrency] = useState(4);
  const [timeoutS, setTimeoutS] = useState(30);
  const [retries, setRetries] = useState(2);
  const [seed, setSeed] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const toggle = (list: string[], set: (v: string[]) => void, id: string) =>
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!versionId || targetIds.length === 0) {
      setError(new Error("Choose a dataset version and at least one target."));
      return;
    }
    const body: RunCreate = {
      project_id: projectId,
      dataset_version_id: versionId,
      target_ids: targetIds,
      evaluator_ids: evaluatorIds,
      experiment_id: experimentId || null,
      label,
      concurrency,
      timeout_s: timeoutS,
      max_retries: retries,
      seed,
    };
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ run_ids: string[] }>("/api/v1/runs", { method: "POST", body });
      if (res.run_ids.length === 1) navigate(`/runs/${res.run_ids[0]}`);
      else navigate(`/projects/${projectId}?tab=runs`);
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  if (versions.length === 0) return <ErrorBox error={new Error("This project has no dataset versions to run against.")} />;

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <fieldset className={fieldset}>
        <legend className={legend}>Dataset</legend>
        <label htmlFor="dv" className="block text-sm text-slate-700">
          Dataset version
        </label>
        <select id="dv" value={versionId} onChange={(e) => setVersionId(e.target.value)} className={`${input} mt-1`}>
          {versions.map(({ ds, v }) => (
            <option key={v.id} value={v.id}>
              {ds.name} v{v.version} ({v.case_count} cases, {shortHash(v.content_hash, 8)})
            </option>
          ))}
        </select>
      </fieldset>

      <fieldset className={fieldset}>
        <legend className={legend}>Targets (one run per target)</legend>
        {data.targets.length === 0 && <p className="text-sm text-slate-600">No targets configured.</p>}
        <div className="grid gap-1 sm:grid-cols-2">
          {data.targets.map((t) => (
            <label key={t.id} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4"
                checked={targetIds.includes(t.id)}
                onChange={() => toggle(targetIds, setTargetIds, t.id)}
              />
              {t.name} <span className="font-mono text-xs text-slate-600">({t.kind})</span>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className={fieldset}>
        <legend className={legend}>Evaluators</legend>
        <div className="grid gap-1 sm:grid-cols-2">
          {data.evaluators.map((ev) => (
            <label key={ev.id} className="flex flex-wrap items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="h-4 w-4"
                checked={evaluatorIds.includes(ev.id)}
                onChange={() => toggle(evaluatorIds, setEvaluatorIds, ev.id)}
              />
              <span className="font-mono">{ev.name}</span>
              <Badge tone={ev.kind === "judge" ? "purple" : "blue"}>{ev.kind}</Badge>
            </label>
          ))}
        </div>
      </fieldset>

      <fieldset className={`${fieldset} grid gap-3 sm:grid-cols-2`}>
        <legend className={legend}>Settings</legend>
        <div>
          <label htmlFor="label" className="block text-sm text-slate-700">
            Label
          </label>
          <input id="label" value={label} maxLength={200} onChange={(e) => setLabel(e.target.value)} className={`${input} mt-1`} />
        </div>
        <div>
          <label htmlFor="exp" className="block text-sm text-slate-700">
            Experiment (optional)
          </label>
          <select id="exp" value={experimentId} onChange={(e) => setExperimentId(e.target.value)} className={`${input} mt-1`}>
            <option value="">None</option>
            {data.experiments.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
        </div>
        <NumField id="conc" label="Concurrency (1-32)" value={concurrency} min={1} max={32} onChange={setConcurrency} />
        <NumField id="timeout" label="Timeout seconds (1-300)" value={timeoutS} min={1} max={300} onChange={setTimeoutS} />
        <NumField id="retries" label="Max retries (0-5)" value={retries} min={0} max={5} onChange={setRetries} />
        <NumField id="seed" label="Seed" value={seed} onChange={setSeed} />
      </fieldset>

      {error !== null && <ErrorBox error={error} />}
      <button type="submit" className={btnPrimary} disabled={busy}>
        {busy ? "Starting..." : "Start run"}
      </button>
    </form>
  );
}

function NumField(props: { id: string; label: string; value: number; min?: number; max?: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label htmlFor={props.id} className="block text-sm text-slate-700">
        {props.label}
      </label>
      <input
        id={props.id}
        type="number"
        value={props.value}
        min={props.min}
        max={props.max}
        required
        onChange={(e) => props.onChange(Number(e.target.value))}
        className={`${input} mt-1`}
      />
    </div>
  );
}
