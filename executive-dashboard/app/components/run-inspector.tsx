/** Metadata-only inspection; controls are limited to owner-run private generation. */
"use client";
import { useCallback, useEffect, useState } from "react";
const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
interface Run {
  id: number;
  brief_id: number;
  stage: string;
  phase: string;
  checkpoint_status: string;
  duration_seconds: number | null;
  error_category: string;
  pending_input: string;
  prompt_version: string;
  prompt_digest: string;
  model_version: string;
  model_note: string;
  control_version: number;
  can_stop: boolean;
  can_continue: boolean;
  worker_active: boolean;
  continued_from: number | null;
  continued_by: number | null;
}
interface Existing {
  reference: string;
  checkpoint_status: string;
  duration_seconds: number | null;
  pending_input: string;
}
export default function RunInspector({
  apiKey,
  onAuthFailure,
  active = true,
}: {
  apiKey: string;
  onAuthFailure: () => void;
  active?: boolean;
}) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [steps, setSteps] = useState<Existing[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const request = useCallback(
    async (path: string, body?: object, signal?: AbortSignal) => {
      const r = await fetch(API + path, {
        method: body ? "POST" : "GET",
        headers: {
          "X-API-Key": apiKey,
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
        cache: "no-store",
        signal,
      });
      if (r.status === 401) {
        onAuthFailure();
        throw new Error("Unlock the dashboard again.");
      }
      const value = await r.json().catch(() => null);
      if (!r.ok)
        throw new Error(
          typeof value?.detail === "string"
            ? value.detail
            : `Run request failed (${r.status})`,
        );
      return value;
    },
    [apiKey, onAuthFailure],
  );
  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      const data = await request(`/runs?limit=50&offset=${offset}`, undefined, signal);
      setRuns(data.private_runs);
      setSteps(data.existing_steps);
    },
    [offset, request],
  );
  useEffect(() => {
    if (!active) return;
    const controller = new AbortController();
    const poll = () => {
      if (!document.hidden)
        refresh(controller.signal).catch((e) => {
          if (!controller.signal.aborted) setError(e.message);
        });
    };
    poll();
    const timer = setInterval(poll, 15000);
    return () => {
      controller.abort();
      clearInterval(timer);
    };
  }, [refresh, active]);
  async function control(r: Run, action: "stop" | "continue") {
    setBusy(true);
    setError("");
    try {
      let body: object = { expected_version: r.control_version };
      if (action === "continue") {
        const brief = await request(`/business-discovery/${r.brief_id}`);
        body = {
          expected_version: r.control_version,
          expected_brief_version: brief.version,
        };
      }
      await request(`/runs/${r.id}/${action}`, body);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="space-y-3 rounded border border-white/20 p-3 min-w-0"
      aria-label="Run inspector"
    >
      <h3 className="font-semibold">Run inspector</h3>
      <p className="text-sm">
        Progress and checkpoints only; private prompts and results stay hidden. Time
        includes waiting and laptop sleep. Refreshing or reopening the laptop never
        retries work.
      </p>
      <p className="text-sm">
        Stop blocks publication; the current local model call may finish before the
        worker releases. After a restart, private work can be continued explicitly.
        Uncertain external actions require reconciliation.
      </p>
      <button
        className="office-filter"
        disabled={busy}
        onClick={() => {
          setError("");
          refresh().catch((e) => setError(e.message));
        }}
      >
        Refresh runs
      </button>
      {error && <p role="alert">{error}</p>}
      {runs.length === 0 && (
        <p>
          No inspected private runs on this page. New research and practice generations
          appear here.
        </p>
      )}
      {runs.map((r) => (
        <article
          key={r.id}
          className="space-y-2 text-sm border-t border-white/20 pt-2 break-words"
        >
          <h4>
            Run #{r.id} · brief #{r.brief_id} · {r.stage}
          </h4>
          <p>
            Phase: {r.phase} · checkpoint: {r.checkpoint_status} · elapsed:{" "}
            {r.duration_seconds === null ? "unknown" : `${r.duration_seconds}s`}
          </p>
          {r.error_category && <p>Error category: {r.error_category}</p>}
          {r.pending_input && <p>{r.pending_input}</p>}
          <details>
            <summary>Prompt and model versions</summary>
            <p>
              Configured model: {r.model_version}. {r.model_note}
            </p>
            <p className="break-all">Prompt implementation: {r.prompt_version}</p>
            <p className="break-all">Input digest: {r.prompt_digest}</p>
          </details>
          {r.continued_from && <p>Continues run #{r.continued_from}</p>}
          {r.continued_by && <p>Continued by run #{r.continued_by}</p>}
          {r.can_stop && (
            <button
              className="office-filter"
              disabled={busy}
              onClick={() => control(r, "stop")}
            >
              Stop private run #{r.id}
            </button>
          )}
          {r.can_continue && (
            <button
              className="office-filter"
              disabled={busy}
              onClick={() => control(r, "continue")}
            >
              Continue private run #{r.id}
            </button>
          )}
        </article>
      ))}
      <details>
        <summary>Other workflow checkpoints ({steps.length} on this page)</summary>
        {steps.map((s) => (
          <p key={s.reference} className="text-sm">
            Step {s.reference} · {s.checkpoint_status} ·{" "}
            {s.duration_seconds ?? "unknown"}s. {s.pending_input}
          </p>
        ))}
      </details>
      <div className="flex gap-2">
        <button
          className="office-filter"
          disabled={busy || offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 50))}
        >
          Newer runs
        </button>
        <button
          className="office-filter"
          disabled={busy || (runs.length < 50 && steps.length < 50)}
          onClick={() => setOffset(offset + 50)}
        >
          Older runs
        </button>
      </div>
    </section>
  );
}
