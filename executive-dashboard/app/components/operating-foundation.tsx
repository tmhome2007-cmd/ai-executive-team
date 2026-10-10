/** Owner policies, memory review, observation jobs and bounded activity streams. */
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
type Policy = {
  version: number;
  currency: string;
  max_action_cost: number | null;
  max_daily_cost: number | null;
  max_experiment_risk: number | null;
  require_known_cost: boolean;
  prohibited_types: string[];
};
type Memory = {
  id: number;
  version: number;
  executive_key: string;
  lesson: string;
  lifecycle_state: string;
  conflict_review_required: boolean;
  expired: boolean;
};
type Job = {
  id: number;
  version: number;
  collector: string;
  experiment_id: number;
  status: string;
  note: string;
  due_at: string;
  observation_id: number | null;
};
type Activity = {
  id: number;
  category: string;
  entity_table: string;
  entity_id: number;
  operation: string;
  timestamp: string;
  new_state: Record<string, string | number | null>;
};
type Page = {
  after_id: number;
  reset_required: boolean;
  items: Activity[];
  executives: Record<string, string>;
};
function Input({
  name,
  label,
  type = "text",
  optional = false,
}: {
  name: string;
  label: string;
  type?: string;
  optional?: boolean;
}) {
  return (
    <label className="block text-sm">
      {label}
      <input
        className="agile-input w-full"
        aria-label={label}
        name={name}
        type={type}
        min={type === "number" ? 0 : undefined}
        step={type === "number" ? "any" : undefined}
        maxLength={2000}
        required={!optional}
      />
    </label>
  );
}
const numberOrNull = (data: FormData, name: string) =>
  data.get(name) === "" ? null : Number(data.get(name));
export default function OperatingFoundation({
  apiKey,
  onAuthFailure,
}: {
  apiKey: string;
  onAuthFailure: () => void;
}) {
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [events, setEvents] = useState<Activity[]>([]);
  const [states, setStates] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const cursor = useRef(0);
  const request = useCallback(
    async <T,>(
      path: string,
      body?: unknown,
      method = "POST",
      signal?: AbortSignal,
    ): Promise<T> => {
      const response = await fetch(API + path, {
        method: body === undefined ? "GET" : method,
        signal,
        cache: "no-store",
        headers: {
          "X-API-Key": apiKey,
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
      if (response.status === 401) {
        onAuthFailure();
        throw new Error("Unlock the dashboard again.");
      }
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : "Check the fields and refresh before retrying.",
        );
      }
      return response.json();
    },
    [apiKey, onAuthFailure],
  );
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      request<Policy>("/operating-policy", undefined, "GET", controller.signal),
      request<Memory[]>(
        `/memory-review?limit=50&offset=${offset}`,
        undefined,
        "GET",
        controller.signal,
      ),
      request<Job[]>(
        `/observation-jobs?limit=50&offset=${offset}`,
        undefined,
        "GET",
        controller.signal,
      ),
    ])
      .then(([p, m, j]) => {
        if (!controller.signal.aborted) {
          setPolicy(p);
          setMemories(m);
          setJobs(j);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setMessage(e.message);
      });
    return () => controller.abort();
  }, [request, offset, revision]);
  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        if (!document.hidden) {
          const page = await request<Page>(
            `/activity-stream/page?after_id=${cursor.current}`,
            undefined,
            "GET",
            controller.signal,
          );
          if (!controller.signal.aborted) {
            if (page.reset_required) {
              cursor.current = page.after_id;
              setEvents([]);
              setMessage("Activity replay reset to the retained 30-day window.");
            }
            if (page.items.length) {
              cursor.current = page.items[page.items.length - 1].id;
              setEvents((old) =>
                [...(page.reset_required ? [] : old), ...page.items].slice(-200),
              );
            }
            setStates(page.executives);
          }
        }
      } catch (e) {
        if (!controller.signal.aborted)
          setMessage(e instanceof Error ? e.message : "Activity unavailable.");
      }
      if (!controller.signal.aborted) timer = setTimeout(poll, 5000);
    }
    poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [request]);
  async function submit(
    event: React.FormEvent<HTMLFormElement>,
    operation: (data: FormData) => Promise<unknown>,
  ) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const form = event.currentTarget;
    try {
      await operation(new FormData(form));
      setMessage("Saved. Approval remains a separate owner decision.");
      setRevision((r) => r + 1);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Change failed.");
    } finally {
      setBusy(false);
    }
  }
  const button = "office-filter";
  return (
    <div className="space-y-6">
      <p>
        Operating rules constrain actions; they never approve them. Sources and results
        retain their provenance.
      </p>
      {message && <p role="status">{message}</p>}
      <section className="office-panel p-4 space-y-3">
        <h3>Company operating policy</h3>
        {policy && (
          <form
            key={policy.version}
            className="grid md:grid-cols-2 gap-3"
            onSubmit={(e) =>
              submit(e, (data) =>
                request(
                  "/operating-policy",
                  {
                    expected_version: policy.version,
                    currency: String(data.get("currency")).toUpperCase(),
                    max_action_cost: numberOrNull(data, "action"),
                    max_daily_cost: numberOrNull(data, "daily"),
                    max_experiment_risk: numberOrNull(data, "risk"),
                    require_known_cost: data.get("known") === "on",
                    prohibited_types: data.getAll("prohibited"),
                    note: data.get("note"),
                  },
                  "PUT",
                ),
              )
            }
          >
            <p className="md:col-span-2">
              Version {policy.version}. Blank limits mean no additional cap. Daily limit
              includes spend over the last 24 hours plus all active commitments.
            </p>
            <label>
              Currency
              <input
                className="agile-input w-full"
                name="currency"
                required
                pattern="[A-Za-z]{3}"
                maxLength={3}
                defaultValue={policy.currency}
              />
            </label>
            {(
              [
                ["action", "Maximum action cost", policy.max_action_cost],
                ["daily", "Daily spend and commitments", policy.max_daily_cost],
                ["risk", "Maximum experiment risk", policy.max_experiment_risk],
              ] as const
            ).map(([name, label, value]) => (
              <label key={name}>
                {label}
                <input
                  className="agile-input w-full"
                  type="number"
                  name={name}
                  min="0"
                  step="any"
                  defaultValue={value ?? ""}
                />
              </label>
            ))}
            <label>
              <input
                type="checkbox"
                name="known"
                defaultChecked={policy.require_known_cost}
              />{" "}
              Require a known estimated cost, including zero
            </label>
            <fieldset>
              <legend>Prohibited action types</legend>
              {["shell", "file_operation", "browser_action"].map((type) => (
                <label className="block" key={type}>
                  <input
                    type="checkbox"
                    name="prohibited"
                    value={type}
                    defaultChecked={policy.prohibited_types.includes(type)}
                  />{" "}
                  {type}
                </label>
              ))}
            </fieldset>
            <Input name="note" label="Policy review note" />
            <button className={button} disabled={busy}>
              Save policy version
            </button>
          </form>
        )}
      </section>
      <section className="office-panel p-4 space-y-3">
        <h3>Memory reconciliation</h3>
        <p>
          Corrections create a replacement; the original lesson and revision history
          remain. Disputed, conflicting or expired memories are excluded from executive
          context.
        </p>
        {memories.map((m) => (
          <article key={m.id} className="border border-gray-700 p-3">
            <p>
              #{m.id} · {m.executive_key} · version {m.version} · {m.lifecycle_state}
              {m.conflict_review_required ? " · conflict review required" : ""}
              {m.expired ? " · expired" : ""}
            </p>
            <p className="whitespace-pre-wrap">{m.lesson}</p>
          </article>
        ))}
        <form
          className="grid md:grid-cols-2 gap-3"
          onSubmit={(e) =>
            submit(e, (data) => {
              const operation = String(data.get("operation"));
              return request(`/memory-review/${Number(data.get("memory"))}`, {
                expected_version: Number(data.get("version")),
                operation,
                source_ids: String(data.get("sources"))
                  .split(",")
                  .map((s) => Number(s.trim())),
                note: data.get("note"),
                claim_key: data.get("claim") || "",
                lesson: operation === "correct" ? data.get("lesson") : null,
                expires_at: data.get("expiry")
                  ? new Date(String(data.get("expiry"))).toISOString()
                  : null,
              });
            })
          }
        >
          <Input name="memory" label="Memory ID" type="number" />
          <Input name="version" label="Current memory version" type="number" />
          <label>
            Operation
            <select
              aria-label="Operation"
              className="agile-input w-full"
              name="operation"
            >
              <option value="annotate">Attach sources / expiry</option>
              <option value="correct">Correct lesson</option>
              <option value="conflict">Flag conflict</option>
              <option value="expire">Expire</option>
            </select>
          </label>
          <Input name="sources" label="Source IDs, comma separated" />
          <Input
            name="claim"
            label="Shared claim key for conflict detection"
            optional
          />
          <Input
            name="expiry"
            label="Memory expiry (local time)"
            type="datetime-local"
            optional
          />
          <Input name="lesson" label="Replacement lesson for corrections" optional />
          <Input name="note" label="Memory review note" />
          <button className={button} disabled={busy}>
            Record memory review
          </button>
        </form>
      </section>
      <section className="office-panel p-4 space-y-3">
        <h3>Scheduled observations</h3>
        <p>
          Collectors accept an owner-confirmed JSON source or an independently approved
          file-read action. They do not approve actions or infer missing measurements.
        </p>
        {jobs.map((j) => (
          <article key={j.id} className="border border-gray-700 p-3">
            <p>
              Job #{j.id} · experiment #{j.experiment_id} · {j.collector} · {j.status} ·
              due {new Date(j.due_at).toLocaleString()}
            </p>
            <p>
              {j.note}
              {j.observation_id ? ` · Observation #${j.observation_id}` : ""}
            </p>
            {!["running", "completed", "cancelled"].includes(j.status) && (
              <div className="flex gap-2">
                {j.collector === "owner_source" && (
                  <button
                    className={button}
                    disabled={busy}
                    onClick={() => {
                      setBusy(true);
                      request(`/observation-jobs/${j.id}/review`, {
                        expected_version: j.version,
                        operation: "retry",
                      })
                        .then(() => setRevision((r) => r + 1))
                        .catch((e) => setMessage(e.message))
                        .finally(() => setBusy(false));
                    }}
                  >
                    Retry source collection
                  </button>
                )}
                <button
                  className={button}
                  disabled={busy}
                  onClick={() => {
                    setBusy(true);
                    request(`/observation-jobs/${j.id}/review`, {
                      expected_version: j.version,
                      operation: "cancel",
                    })
                      .then(() => setRevision((r) => r + 1))
                      .catch((e) => setMessage(e.message))
                      .finally(() => setBusy(false));
                  }}
                >
                  Cancel job
                </button>
              </div>
            )}
          </article>
        ))}
        <form
          className="grid md:grid-cols-2 gap-3"
          onSubmit={(e) =>
            submit(e, (data) => {
              const collector = String(data.get("collector"));
              return request("/observation-jobs", {
                job_key: data.get("key"),
                experiment_id: Number(data.get("experiment")),
                collector,
                due_at: new Date(String(data.get("due"))).toISOString(),
                source_id:
                  collector === "owner_source" ? Number(data.get("source")) : null,
                collection_action_id:
                  collector === "approved_file_read"
                    ? Number(data.get("action"))
                    : null,
              });
            })
          }
        >
          <Input name="key" label="Unique observation job key" />
          <Input name="experiment" label="Experiment ID" type="number" />
          <label>
            Collector
            <select
              aria-label="Collector"
              name="collector"
              className="agile-input w-full"
            >
              <option value="owner_source">Owner-confirmed source</option>
              <option value="approved_file_read">Approved file read</option>
            </select>
          </label>
          <Input
            name="due"
            label="Observation due (local time)"
            type="datetime-local"
          />
          <Input
            name="source"
            label="Source ID for source collector"
            type="number"
            optional
          />
          <Input
            name="action"
            label="Read action ID for file collector"
            type="number"
            optional
          />
          <button className={button} disabled={busy}>
            Schedule observation
          </button>
        </form>
      </section>
      <div className="flex gap-2">
        <button
          className={button}
          disabled={offset === 0 || busy}
          onClick={() => setOffset((o) => Math.max(0, o - 50))}
        >
          Newer records
        </button>
        <button
          className={button}
          disabled={busy || (memories.length < 50 && jobs.length < 50)}
          onClick={() => setOffset((o) => o + 50)}
        >
          Older records
        </button>
        <button
          className={button}
          disabled={busy}
          onClick={() => setRevision((r) => r + 1)}
        >
          Refresh records
        </button>
      </div>
      <section className="office-panel p-4 space-y-3">
        <h3>Executive activity</h3>
        <p>
          Observed states refresh every five seconds while this tab is visible. Running
          work older than 15 minutes becomes unknown. Only activity metadata is
          replayed.
        </p>
        <div className="flex flex-wrap gap-3">
          {Object.entries(states).map(([role, state]) => (
            <span key={role}>
              {role}: {state}
            </span>
          ))}
        </div>
        <ol className="max-h-96 overflow-auto">
          {events
            .slice()
            .reverse()
            .map((item) => (
              <li key={item.id}>
                {new Date(item.timestamp).toLocaleString()} · {item.category} ·{" "}
                {item.entity_table} #{item.entity_id} · {item.operation} ·{" "}
                {JSON.stringify(item.new_state)}
              </li>
            ))}
        </ol>
      </section>
    </div>
  );
}
