/** Reviewed patterns and explicit public reads; neither grants practice approval. */
"use client";
import { useCallback, useEffect, useState } from "react";
export interface WorkflowTemplate {
  id: number;
  template_key: string;
  name: string;
  version: number;
  state: string;
  review_version: number;
  usable: boolean;
  digest: string;
  steps: {
    id: string;
    kind: string;
    depends_on: string[];
    inputs: string[];
    outputs: string[];
    gate: string;
    capability: string;
  }[];
}
type Request = (
  path: string,
  method?: string,
  body?: unknown,
  signal?: AbortSignal,
) => Promise<unknown>;
interface Proposal {
  id: number;
  url: string;
  purpose: string;
  proposed_category: string;
  state: string;
  version: number;
  source_id: number | null;
  source_category: string | null;
}
export default function ResearchWorkflow({
  request,
  onTemplates,
  onEvidenceChanged,
  refreshToken,
}: {
  request: Request;
  onTemplates: (items: WorkflowTemplate[]) => void;
  onEvidenceChanged: () => Promise<void>;
  refreshToken: number;
}) {
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]),
    [queue, setQueue] = useState<Proposal[]>([]);
  const [offset, setOffset] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [url, setUrl] = useState(""),
    [purpose, setPurpose] = useState(""),
    [category, setCategory] = useState("unknown"),
    [snapshot, setSnapshot] = useState(false);
  const [note, setNote] = useState("");
  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      const [patterns, proposals] = await Promise.all([
        request("/workflow-templates?limit=100", "GET", undefined, signal),
        request(`/research-queue?limit=50&offset=${offset}`, "GET", undefined, signal),
      ]);
      setTemplates(patterns as WorkflowTemplate[]);
      onTemplates(patterns as WorkflowTemplate[]);
      setQueue(proposals as Proposal[]);
    },
    [request, onTemplates, offset],
  );
  useEffect(() => {
    const c = new AbortController();
    Promise.resolve()
      .then(() => {
        if (!c.signal.aborted) return refresh(c.signal);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(String(e.message));
      });
    return () => c.abort();
  }, [refresh, refreshToken]);
  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      try {
        await refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Refresh failed");
      }
      setBusy(false);
    }
  }
  return (
    <section
      aria-label="Workflow templates and research queue"
      className="command-card space-y-4"
    >
      <h3>Workflow templates &amp; research queue</h3>
      <p>
        Review a reusable pattern, then optionally bind it to a new brief. Each practice
        plan and sample still needs its own existing approval and assessment.
      </p>
      {error && <p role="alert">{error}</p>}
      <fieldset disabled={busy} className="space-y-3">
        <legend>Review a workflow pattern</legend>
        <label className="block">
          Template review note
          <input
            className="command-input"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            maxLength={2000}
          />
        </label>
        {templates.map((t) => (
          <article key={t.id} className="space-y-2">
            <p>
              {t.name} · version {t.version} · {t.state}
            </p>
            <details>
              <summary>Inputs, outputs and approval gates</summary>
              <ol>
                {t.steps.map((s) => (
                  <li key={s.id} className="my-2 break-words">
                    {s.kind}: {s.inputs.join(", ")} → {s.outputs.join(", ")} · gate:{" "}
                    {s.gate} · capability: {s.capability} · depends on:{" "}
                    {s.depends_on.join(", ") || "none"}
                  </li>
                ))}
              </ol>
              <p className="break-all">Definition digest: {t.digest}</p>
            </details>
            {t.state === "proposed" && (
              <button
                className="office-filter"
                disabled={!note.trim()}
                onClick={() =>
                  act(() =>
                    request(`/workflow-templates/${t.id}/review`, "POST", {
                      expected_version: t.review_version,
                      state: "reviewed",
                      note,
                    }),
                  )
                }
              >
                Review template for reuse
              </button>
            )}
            {t.usable && (
              <button
                className="office-filter"
                disabled={!note.trim()}
                onClick={() =>
                  act(() =>
                    request(`/workflow-templates/${t.id}/review`, "POST", {
                      expected_version: t.review_version,
                      state: "withdrawn",
                      note,
                    }),
                  )
                }
              >
                Withdraw template version
              </button>
            )}
            {t.state === "withdrawn" && (
              <button
                className="office-filter"
                onClick={() =>
                  act(() =>
                    request("/workflow-templates", "POST", {
                      key: t.template_key,
                      name: t.name,
                      steps: t.steps.map(
                        ({ id, kind, depends_on, capability, gate }) => ({
                          id,
                          kind,
                          depends_on,
                          capability,
                          gate,
                        }),
                      ),
                    }),
                  )
                }
              >
                Create new proposed version
              </button>
            )}
          </article>
        ))}
      </fieldset>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          act(async () => {
            await request("/research-queue", "POST", {
              url,
              purpose,
              proposed_category: category,
              new_snapshot: snapshot,
            });
            setUrl("");
            setPurpose("");
          });
        }}
      >
        <fieldset disabled={busy} className="space-y-3">
          <legend>Queue a public source — no read yet</legend>
          <label className="block">
            Proposed public URL
            <input
              required
              type="url"
              className="command-input"
              maxLength={1000}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </label>
          <label className="block">
            Research purpose
            <input
              required
              className="command-input"
              maxLength={1000}
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
            />
          </label>
          <label className="block">
            Category hypothesis
            <select
              className="command-input"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {[
                "unknown",
                "buyer",
                "demand",
                "platform",
                "constraint",
                "contradiction",
              ].map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label>
            <input
              type="checkbox"
              checked={snapshot}
              onChange={(e) => setSnapshot(e.target.checked)}
            />{" "}
            Queue a new snapshot of an already fetched URL
          </label>
          <button className="office-filter">Queue source</button>
        </fieldset>
      </form>
      <p>
        Queuing sends no request to the website. An explicit read uses the public page
        reader. Successfully fetched records remain unverified; classify them separately
        in the evidence controls.
      </p>
      {queue.map((q) => (
        <article key={q.id} className="space-y-2 break-words">
          <p>
            Source proposal #{q.id} · {q.state} · category hypothesis:{" "}
            {q.proposed_category}
          </p>
          <p>{q.url}</p>
          <p>{q.purpose}</p>
          {q.source_id ? (
            <p>
              Fetched evidence record #{q.source_id}. Its classification is separate
              from this hypothesis.
            </p>
          ) : (
            <p>Not an evidence record.</p>
          )}
          {["proposed", "failed", "needs_review"].includes(q.state) && (
            <button
              className="office-filter"
              disabled={busy}
              onClick={() =>
                act(async () => {
                  await request(`/research-queue/${q.id}/read`, "POST", {
                    expected_version: q.version,
                  });
                  await onEvidenceChanged();
                })
              }
            >
              Read queued public page #{q.id}
            </button>
          )}
        </article>
      ))}
      <div className="flex gap-2">
        <button
          className="office-filter"
          disabled={busy || offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 50))}
        >
          Previous proposals
        </button>
        <button
          className="office-filter"
          disabled={busy || queue.length < 50}
          onClick={() => setOffset(offset + 50)}
        >
          Next proposals
        </button>
        <button
          className="office-filter"
          disabled={busy}
          onClick={() => act(async () => {})}
        >
          Refresh queue
        </button>
      </div>
    </section>
  );
}
