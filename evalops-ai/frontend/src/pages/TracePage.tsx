import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { Trace } from "../api/types";
import { Badge } from "../components/Badge";
import { DataState } from "../components/DataState";
import { PageTitle, link } from "../components/Layout";
import { SpanWaterfall } from "../components/SpanWaterfall";
import { dateTime, ms } from "../lib/format";
import { useApi } from "../lib/useApi";

export function TracePage() {
  const { traceId = "" } = useParams();
  const state = useApi((signal) => api<Trace>(`/api/v1/traces/${traceId}`, { signal }), [traceId]);
  return (
    <DataState {...state} loadingLabel="Loading trace">
      {(t) => (
        <>
          {t.run_id && (
            <p className="mb-1 text-sm">
              <Link to={`/runs/${t.run_id}`} className={link}>
                Back to run
              </Link>
            </p>
          )}
          <PageTitle
            sub={
              <span className="flex flex-wrap items-center gap-2">
                <Badge tone={t.status === "ok" ? "green" : "red"}>{t.status}</Badge>
                <span>{dateTime(t.started_at)}</span>
                <span>duration {ms(t.duration_ms)}</span>
                <span>{t.spans.length} spans</span>
              </span>
            }
          >
            Trace: {t.name}
          </PageTitle>
          {t.spans.length === 0 ? (
            <p className="text-sm text-slate-600">This trace has no spans.</p>
          ) : (
            <SpanWaterfall spans={t.spans} traceStartedAt={t.started_at} traceDurationMs={t.duration_ms} />
          )}
        </>
      )}
    </DataState>
  );
}
