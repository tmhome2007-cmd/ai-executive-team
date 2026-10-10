/** Private inert downloads from immutable saved samples; assessments remain separate. */
"use client";
import { useCallback, useEffect, useState } from "react";
const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
interface Artifact {
  id: number;
  sample_id: number;
  version: number;
  kind: string;
  sha256: string;
  filename: string;
  expires_at: number;
  availability: string;
  provenance: {
    rubric_digest: string;
    parent_sample_id: number | null;
    feedback_review_id: number | null;
    scope: string;
  };
}
export default function PracticeArtifacts({
  briefId,
  samples,
  apiKey,
  onAuthFailure,
}: {
  briefId: number;
  samples: { id: number; attempt: number }[];
  apiKey: string;
  onAuthFailure: () => void;
}) {
  const [rows, setRows] = useState<Artifact[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState("");
  const [kind, setKind] = useState("txt");
  const [before, setBefore] = useState("");
  const [after, setAfter] = useState("");
  const [diff, setDiff] = useState<string | null>(null);
  const request = useCallback(
    async (path: string, body?: object) => {
      const response = await fetch(`${API}${path}`, {
        method: body ? "POST" : "GET",
        headers: {
          "X-API-Key": apiKey,
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
        cache: "no-store",
      });
      if (response.status === 401) {
        onAuthFailure();
        throw new Error("Please unlock the dashboard again.");
      }
      if (!response.ok) {
        const value = await response.json().catch(() => ({}));
        throw new Error(
          typeof value.detail === "string"
            ? value.detail
            : `Request failed (${response.status})`,
        );
      }
      return response;
    },
    [apiKey, onAuthFailure],
  );
  const refresh = useCallback(async () => {
    setRows(await (await request(`/practice-artifacts?brief_id=${briefId}`)).json());
  }, [request, briefId]);
  useEffect(() => {
    let active = true;
    request(`/practice-artifacts?brief_id=${briefId}`)
      .then((r) => r.json())
      .then((v) => {
        if (active) setRows(v);
      })
      .catch((e) => {
        if (active) setError(String(e.message));
      });
    return () => {
      active = false;
    };
  }, [briefId, request]);
  async function act(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="space-y-3 rounded border border-white/20 p-3 min-w-0"
      aria-label="Private deliverable workspace"
    >
      <h4 className="font-semibold">Private deliverable files</h4>
      <p className="text-sm">
        Export the exact saved sample. Files expire after 30 days; source text, hashes
        and review history remain. Downloading grants no approval.
      </p>
      {error && <p role="alert">{error}</p>}
      <div className="flex flex-wrap gap-2">
        <select
          aria-label="Sample to export"
          className="office-input"
          value={source}
          onChange={(e) => setSource(e.target.value)}
        >
          <option value="">Choose saved sample…</option>
          {samples.map((s) => (
            <option key={s.id} value={s.id}>
              Sample {s.attempt} · record #{s.id}
            </option>
          ))}
        </select>
        <select
          aria-label="Artifact format"
          className="office-input"
          value={kind}
          onChange={(e) => setKind(e.target.value)}
        >
          <option value="txt">Plain text (.txt)</option>
          <option value="md">Markdown (.md)</option>
        </select>
        <button
          className="office-filter"
          disabled={busy || !source}
          onClick={() =>
            act(async () => {
              await request("/practice-artifacts", { sample_id: Number(source), kind });
              await refresh();
            })
          }
        >
          Export saved sample
        </button>
        <button className="office-filter" disabled={busy} onClick={() => act(refresh)}>
          Refresh files
        </button>
      </div>
      {rows.length === 0 && <p>No exported files yet.</p>}
      {rows.map((row) => (
        <div key={row.id} className="space-y-1 text-sm break-words">
          <p>
            {row.filename} · {row.availability} · expires{" "}
            {new Date(row.expires_at * 1000).toLocaleString()}
          </p>
          <p>
            SHA-256: <code className="break-all">{row.sha256}</code>
          </p>
          <p>
            Rubric: {row.provenance.rubric_digest.slice(0, 12)} · source sample #
            {row.sample_id}
            {row.provenance.parent_sample_id
              ? ` · revises #${row.provenance.parent_sample_id}`
              : ""}
            {row.provenance.feedback_review_id
              ? ` · feedback #${row.provenance.feedback_review_id}`
              : ""}
          </p>
          <button
            className="office-filter"
            disabled={busy || row.availability !== "available"}
            onClick={() =>
              act(async () => {
                const response = await request(
                  `/practice-artifacts/${row.id}/download`,
                );
                const url = URL.createObjectURL(await response.blob());
                const anchor = document.createElement("a");
                anchor.href = url;
                anchor.download = row.filename;
                document.body.appendChild(anchor);
                anchor.click();
                anchor.remove();
                setTimeout(() => URL.revokeObjectURL(url), 10000);
              })
            }
          >
            Download {row.kind.toUpperCase()} sample {row.version}
          </button>
        </div>
      ))}
      {rows.length >= 100 && (
        <button
          className="office-filter"
          disabled={busy}
          onClick={() =>
            act(async () => {
              const next = await (
                await request(
                  `/practice-artifacts?brief_id=${briefId}&offset=${rows.length}`,
                )
              ).json();
              setRows([...rows, ...next]);
            })
          }
        >
          Load older files
        </button>
      )}
      <div className="flex flex-wrap gap-2">
        <select
          aria-label="Original artifact"
          className="office-input"
          value={before}
          onChange={(e) => setBefore(e.target.value)}
        >
          <option value="">Original file…</option>
          {rows.map((r) => (
            <option key={r.id} value={r.id}>
              {r.filename} · #{r.id}
            </option>
          ))}
        </select>
        <select
          aria-label="Revised artifact"
          className="office-input"
          value={after}
          onChange={(e) => setAfter(e.target.value)}
        >
          <option value="">Revised file…</option>
          {rows.map((r) => (
            <option key={r.id} value={r.id}>
              {r.filename} · #{r.id}
            </option>
          ))}
        </select>
        <button
          className="office-filter"
          disabled={busy || !before || !after || before === after}
          onClick={() =>
            act(async () => {
              setDiff(null);
              const result = await (
                await request(
                  `/practice-artifacts/compare?before_id=${before}&after_id=${after}`,
                )
              ).json();
              setDiff(
                result.identical ? "The saved bytes are identical." : result.diff,
              );
            })
          }
        >
          Compare files
        </button>
      </div>
      {diff !== null && (
        <>
          <p className="text-sm">
            Text differences only. Review the sample separately to assess quality.
          </p>
          <pre className="whitespace-pre-wrap break-all text-sm">{diff}</pre>
        </>
      )}
    </section>
  );
}
