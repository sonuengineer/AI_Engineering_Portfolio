import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, post } from "../api/client";
import type { DocumentRow } from "../api/types";
import { hasRole, useAuth } from "../components/auth";
import { useAsync } from "../components/useAsync";
import { Badge, Button, Card, EmptyState, ErrorBanner, Loading, StatusBadge } from "../components/ui";

interface ChunkRow { id: string; ordinal: number; page: number | null; section: string | null; text: string; flags: { suspicious_instructions?: string[] } }

export function Documents() {
  const { me } = useAuth();
  const docs = useAsync(() => api<DocumentRow[]>("/documents"));
  const [uploadError, setUploadError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [open, setOpen] = useState<{ doc: DocumentRow; chunks: ChunkRow[] } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const canWrite = hasRole(me, "analyst");

  const pending = (docs.data ?? []).some((d) => d.status === "pending" || d.status === "processing");
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => void docs.reload(true), 1500);
    return () => clearInterval(t);
  }, [pending, docs]);

  const upload = async (e: FormEvent) => {
    e.preventDefault();
    const f = fileRef.current?.files?.[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    setBusy(true); setUploadError(undefined); setNotice(null);
    try {
      const d = await api<DocumentRow>("/documents/upload", { method: "POST", body: fd });
      setNotice(`Queued "${d.title}" for ingestion.`);
      if (fileRef.current) fileRef.current.value = "";
      await docs.reload(true);
    } catch (err) { setUploadError(err); } finally { setBusy(false); }
  };

  const ingestUrl = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true); setUploadError(undefined); setNotice(null);
    try {
      const d = await post<DocumentRow>("/documents/url", { url });
      setNotice(`Queued web page "${d.title}".`); setUrl("");
      await docs.reload(true);
    } catch (err) { setUploadError(err); } finally { setBusy(false); }
  };

  const view = async (doc: DocumentRow) => {
    try { setOpen({ doc, chunks: await api<ChunkRow[]>(`/documents/${doc.id}/chunks`) }); } catch (err) { setUploadError(err); }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Documents</h1>
      {canWrite && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Upload a file">
            <form onSubmit={upload} className="space-y-3">
              <label htmlFor="file" className="block text-sm text-slate-600">PDF, DOCX, XLSX, CSV, TXT or MD. Content is verified by file signature, not by extension alone.</label>
              <input id="file" ref={fileRef} type="file" accept=".pdf,.docx,.xlsx,.csv,.txt,.md" className="block w-full text-sm" />
              <Button type="submit" busy={busy}>Upload</Button>
            </form>
          </Card>
          <Card title="Ingest a web page">
            <form onSubmit={ingestUrl} className="space-y-3">
              <label htmlFor="url" className="block text-sm text-slate-600">Only allowlisted public hosts (URL_INGEST_ALLOWLIST). Private and metadata IPs are blocked.</label>
              <input id="url" type="url" required value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/page" className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm" />
              <Button type="submit" busy={busy} disabled={!url}>Fetch and index</Button>
            </form>
          </Card>
        </div>
      )}
      {notice && <p role="status" className="rounded-md bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</p>}
      <ErrorBanner error={uploadError} />
      <Card title={`Indexed documents${docs.data ? ` (${docs.data.length})` : ""}`}>
        {docs.loading ? <Loading /> : docs.error ? <ErrorBanner error={docs.error} onRetry={() => void docs.reload()} /> :
          !docs.data?.length ? <EmptyState title="No documents yet">Upload a file to start building the knowledge base.</EmptyState> :
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left text-xs uppercase text-slate-500"><th className="py-2">Title</th><th>Type</th><th>Status</th><th>Chunks</th><th>Pages</th><th /></tr></thead>
              <tbody>
                {docs.data.map((d) => (
                  <tr key={d.id} className="border-t border-slate-100">
                    <td className="py-2 pr-3">{d.title} {Number(d.meta.flagged_chunks ?? 0) > 0 && <Badge tone="red" title="Contains text matching prompt-injection patterns">injection flagged</Badge>}
                      {d.error && <p className="text-xs text-rose-700">{d.error}</p>}</td>
                    <td className="text-xs text-slate-500">{d.mime_type.split("/").pop()?.split(".").pop()}</td>
                    <td><StatusBadge status={d.status} /></td>
                    <td>{d.chunk_count}</td><td>{d.page_count ?? "-"}</td>
                    <td><Button variant="ghost" onClick={() => void view(d)} disabled={d.status !== "ready"}>View chunks</Button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>}
      </Card>
      {open && (
        <Card title={`Chunks: ${open.doc.title}`} actions={<Button variant="ghost" onClick={() => setOpen(null)}>Close</Button>}>
          <ol className="space-y-2">
            {open.chunks.map((c) => (
              <li key={c.id} className="rounded border border-slate-100 p-2 text-xs">
                <p className="mb-1 text-slate-500">#{c.ordinal}{c.page ? ` -- page ${c.page}` : ""}{c.section ? ` -- ${c.section}` : ""}
                  {c.flags.suspicious_instructions && <Badge tone="red">flagged: {c.flags.suspicious_instructions.join(", ")}</Badge>}</p>
                <p className="whitespace-pre-wrap text-slate-700">{c.text}</p>
              </li>
            ))}
          </ol>
        </Card>
      )}
    </div>
  );
}
