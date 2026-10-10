/** Owner-defined expectations and separately recorded outcome evidence. */
"use client";

import { useCallback, useEffect, useState } from "react";
const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
interface Observation {
  id: number;
  observed_at: string;
  value: number | null;
  evidence: string;
  notes: string;
  measurement_mode: string;
}
interface Experiment {
  id: number;
  action_id: number;
  action_status: string;
  version: number;
  title: string;
  hypothesis: string;
  baseline_note: string;
  baseline_value: number | null;
  metric_name: string;
  unit: string;
  target_value: number | null;
  direction: string;
  expected_result: string;
  budget_amount: number;
  risk_limit: number;
  currency: string;
  observation_due_at: string;
  actual_cost_amount: number | null;
  latest_observation: Observation | null;
  comparison: {
    assessment: string;
    change_from_baseline: number | null;
    cost_assessment: string;
    evidence_scope: string;
  };
}
const fields = [
  "title",
  "action_id",
  "hypothesis",
  "baseline_note",
  "baseline_value",
  "metric_name",
  "unit",
  "target_value",
  "expected_result",
  "budget_amount",
  "risk_limit",
  "currency",
  "observation_due_at",
] as const;
const blank = {
  title: "",
  action_id: "",
  hypothesis: "",
  baseline_note: "Unknown — baseline evidence required.",
  baseline_value: "",
  metric_name: "",
  unit: "",
  target_value: "",
  direction: "increase",
  expected_result: "",
  budget_amount: "0",
  risk_limit: "0",
  currency: "EUR",
  observation_due_at: "",
};
const localTime = (iso: string) => {
  const date = new Date(iso);
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 23);
};
const label = (value: string) => value.replaceAll("_", " ");

export default function Experiments({
  apiKey,
  onAuthFailure,
  onActions,
}: {
  apiKey: string;
  onAuthFailure: () => void;
  onActions: () => void;
}) {
  const [items, setItems] = useState<Experiment[]>([]);
  const [selected, setSelected] = useState<Experiment | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(blank);
  const [history, setHistory] = useState<Observation[]>([]);
  const [hasMore, setHasMore] = useState(false);
  const [moreHistory, setMoreHistory] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [observation, setObservation] = useState({
    idempotency_key: "",
    observed_at: "",
    value: "",
    evidence: "",
    notes: "",
  });
  const request = useCallback(
    async (path: string, method = "GET", body?: unknown, signal?: AbortSignal) => {
      const response = await fetch(`${API}${path}`, {
        method,
        signal,
        headers: {
          "X-API-Key": apiKey,
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      if (response.status === 401) {
        onAuthFailure();
        throw new Error("Sign in again.");
      }
      const data = await response.json().catch(() => null);
      if (!response.ok)
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : "Experiments unavailable. Restart the updated backend if needed.",
        );
      return data;
    },
    [apiKey, onAuthFailure],
  );
  useEffect(() => {
    const controller = new AbortController();
    request("/experiments", "GET", undefined, controller.signal)
      .then((data) => {
        setItems(data);
        setHasMore(data.length === 50);
        setError(null);
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setError(error instanceof Error ? error.message : "Experiments unavailable.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [request]);
  const refresh = async () => {
    setLoading(true);
    try {
      const data = await request("/experiments");
      setItems(data);
      setHasMore(data.length === 50);
      setError(null);
      if (selected) await open(selected.id);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Refresh failed.");
    } finally {
      setLoading(false);
    }
  };
  const open = async (id: number) => {
    setBusy(true);
    try {
      const [plan, observations] = await Promise.all([
        request(`/experiments/${id}`),
        request(`/experiments/${id}/observations`),
      ]);
      setSelected(plan);
      setHistory(observations);
      setMoreHistory(observations.length === 50);
      setEditing(false);
      setError(null);
      setObservation({
        idempotency_key: crypto.randomUUID(),
        observed_at: localTime(new Date().toISOString()),
        value: "",
        evidence: "",
        notes: "",
      });
    } catch (error) {
      setError(error instanceof Error ? error.message : "Experiment unavailable.");
    } finally {
      setBusy(false);
    }
  };
  const edit = () => {
    if (!selected) return;
    const values = { ...blank };
    for (const key of fields)
      values[key] = selected[key] === null ? "" : String(selected[key]);
    values.direction = selected.direction;
    values.observation_due_at = localTime(selected.observation_due_at);
    setDraft(values);
    setEditing(true);
  };
  const save = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      const payload = {
        ...draft,
        action_id: Number(draft.action_id),
        baseline_value:
          draft.baseline_value === "" ? null : Number(draft.baseline_value),
        target_value: draft.target_value === "" ? null : Number(draft.target_value),
        budget_amount: Number(draft.budget_amount),
        risk_limit: Number(draft.risk_limit),
        observation_due_at: new Date(draft.observation_due_at).toISOString(),
      };
      let plan: Experiment;
      if (selected) {
        const { action_id, ...patch } = payload;
        void action_id;
        plan = await request(`/experiments/${selected.id}`, "PATCH", {
          ...patch,
          expected_version: selected.version,
        });
      } else plan = await request("/experiments", "POST", payload);
      const data = await request("/experiments");
      setItems(data);
      setHasMore(data.length === 50);
      await open(plan.id);
      setError(null);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Plan failed.");
    } finally {
      setBusy(false);
    }
  };
  const observe = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setBusy(true);
    try {
      await request(`/experiments/${selected.id}/observations`, "POST", {
        ...observation,
        observed_at: new Date(observation.observed_at).toISOString(),
        value: observation.value === "" ? null : Number(observation.value),
      });
      await open(selected.id);
      const data = await request("/experiments");
      setItems(data);
      setHasMore(data.length === 50);
      setError(null);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Observation failed. Keep the retry key when retrying this measurement.",
      );
    } finally {
      setBusy(false);
    }
  };
  const older = async (observations = false) => {
    setBusy(true);
    try {
      if (observations && selected) {
        const data = await request(
          `/experiments/${selected.id}/observations?offset=${history.length}`,
        );
        setHistory((previous) => [...previous, ...data]);
        setMoreHistory(data.length === 50);
      } else {
        const data = await request(`/experiments?offset=${items.length}`);
        setItems((previous) => [...previous, ...data]);
        setHasMore(data.length === 50);
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : "Records unavailable.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <section aria-label="Experiments and observations" className="space-y-6">
      <header className="flex flex-wrap justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Experiments & observations</h2>
          <p className="text-sm text-gray-400 mt-2">
            Test a hypothesis against measured results, evidence and controlled costs.
          </p>
        </div>
        <div className="flex gap-3">
          <button
            className="office-filter"
            disabled={busy || loading}
            onClick={refresh}
          >
            Refresh experiments
          </button>
          <button
            className="office-filter"
            disabled={busy || loading}
            onClick={() => {
              setSelected(null);
              setDraft(blank);
              setEditing(true);
              setError(null);
            }}
          >
            New experiment
          </button>
        </div>
      </header>
      <p className="text-sm text-gray-500">
        Create the plan while its proposed action is pending. Approval and treasury
        gates still apply. Observation dates are recorded; automatic collection is a
        later board item.
      </p>
      {error && (
        <p role="alert" className="text-amber-300">
          {error}
        </p>
      )}
      {loading && <p className="text-gray-400">Loading experiments…</p>}
      {!loading && !error && items.length === 0 && (
        <p className="text-gray-400">No experiments recorded yet.</p>
      )}
      <div className="grid gap-3 md:grid-cols-2">
        {items.map((item) => (
          <button
            className="command-card text-left min-w-0"
            key={item.id}
            disabled={busy || loading}
            onClick={() => open(item.id)}
          >
            <h3 className="font-semibold break-words">
              #{item.id} · {item.title}
            </h3>
            <p className="text-sm text-gray-400 mt-2">
              Action #{item.action_id} · {label(item.comparison.assessment)}
            </p>
            <p className="text-xs text-gray-500 mt-2">
              Risk limit {item.risk_limit} {item.currency} · Observe{" "}
              {new Date(item.observation_due_at).toLocaleString()}
            </p>
          </button>
        ))}
      </div>
      {hasMore && (
        <button
          className="office-filter"
          disabled={busy || loading}
          onClick={() => older()}
        >
          Load older experiments
        </button>
      )}
      {editing && (
        <form onSubmit={save} className="command-card space-y-4">
          <h3 className="text-lg font-semibold">
            {selected ? "Edit experiment plan" : "New experiment plan"}
          </h3>
          <div className="grid gap-4 md:grid-cols-2">
            {fields.map((field) => (
              <label key={field} className="text-sm text-gray-300 min-w-0">
                {label(field)}
                {["baseline_value", "target_value"].includes(field) &&
                  " (optional; blank means unknown)"}
                <input
                  aria-label={`Experiment ${field}`}
                  className="agile-input w-full"
                  value={draft[field]}
                  disabled={busy || (Boolean(selected) && field === "action_id")}
                  required={!["baseline_value", "target_value"].includes(field)}
                  type={
                    field === "observation_due_at"
                      ? "datetime-local"
                      : [
                            "action_id",
                            "baseline_value",
                            "target_value",
                            "budget_amount",
                            "risk_limit",
                          ].includes(field)
                        ? "number"
                        : "text"
                  }
                  step="any"
                  maxLength={
                    field === "title"
                      ? 200
                      : field === "currency"
                        ? 3
                        : field === "metric_name"
                          ? 120
                          : field === "unit"
                            ? 40
                            : 4000
                  }
                  onChange={(e) =>
                    setDraft((previous) => ({ ...previous, [field]: e.target.value }))
                  }
                />
              </label>
            ))}
            <label className="text-sm text-gray-300">
              Target direction
              <select
                aria-label="Experiment direction"
                className="agile-input w-full"
                value={draft.direction}
                disabled={busy}
                onChange={(e) =>
                  setDraft((previous) => ({ ...previous, direction: e.target.value }))
                }
              >
                <option value="increase">At least target</option>
                <option value="decrease">At most target</option>
              </select>
            </label>
          </div>
          <p className="text-xs text-gray-500">
            Observation date uses your local time. Baseline note must state its source
            or that the baseline is unknown.
          </p>
          <button className="office-filter" disabled={busy}>
            Save experiment
          </button>
          <button
            type="button"
            className="office-filter ml-3"
            disabled={busy}
            onClick={() => setEditing(false)}
          >
            Cancel experiment edit
          </button>
        </form>
      )}
      {selected && !editing && (
        <article className="command-card space-y-4">
          <h3 className="text-xl font-semibold break-words">{selected.title}</h3>
          <p className="text-sm whitespace-pre-wrap break-words">
            Hypothesis: {selected.hypothesis}
          </p>
          <p className="text-sm text-gray-400 break-words">
            Baseline: {selected.baseline_value ?? "Unknown"} {selected.unit} ·{" "}
            {selected.baseline_note}
          </p>
          <p className="text-sm text-gray-400 break-words">
            Expected: {selected.expected_result} · Target{" "}
            {selected.target_value ?? "Unknown"} {selected.unit}
          </p>
          <p className="text-sm text-gray-400">
            Measured: {selected.latest_observation?.value ?? "Unknown"} {selected.unit}{" "}
            · Change from baseline:{" "}
            {selected.comparison.change_from_baseline ?? "Unknown"}
          </p>
          <p className="text-sm text-teal-300">
            Assessment: {label(selected.comparison.assessment)}
          </p>
          <p className="text-sm text-gray-400">
            Budget {selected.budget_amount} {selected.currency} · Risk limit{" "}
            {selected.risk_limit} {selected.currency} · Recorded cost{" "}
            {selected.actual_cost_amount ?? "Unknown"} {selected.currency} ·{" "}
            {label(selected.comparison.cost_assessment)}
          </p>
          <p className="text-xs text-gray-500">
            {selected.comparison.evidence_scope}. Comparison does not approve an action,
            credit revenue or verify a source.
          </p>
          <button className="command-link" onClick={onActions}>
            Action #{selected.action_id} & results →
          </button>
          {selected.action_status === "pending" && !selected.latest_observation && (
            <button
              className="office-filter ml-3"
              disabled={busy || loading}
              onClick={edit}
            >
              Edit plan
            </button>
          )}
          <h4 className="font-semibold">Recorded observations</h4>
          {history.length === 0 && (
            <p className="text-sm text-gray-400">No outcome measurements recorded.</p>
          )}
          {history.map((row) => (
            <article key={row.id} className="contribution">
              <p className="text-xs text-gray-500">
                {new Date(row.observed_at).toLocaleString()} · {row.measurement_mode}
              </p>
              <p className="text-sm mt-2">
                Value: {row.value ?? "Unknown"} {selected.unit}
              </p>
              <p className="whitespace-pre-wrap break-words text-sm text-gray-300 mt-2">
                Evidence: {row.evidence}
              </p>
              {row.notes && (
                <p className="whitespace-pre-wrap break-words text-sm text-gray-400 mt-2">
                  {row.notes}
                </p>
              )}
            </article>
          ))}
          {moreHistory && (
            <button
              className="office-filter"
              disabled={busy || loading}
              onClick={() => older(true)}
            >
              Load older observations
            </button>
          )}
          <form onSubmit={observe} className="space-y-3">
            <h4 className="font-semibold">Record an observation</h4>
            <p className="text-xs text-gray-500">
              Record results after execution, with the measurement time and source.
              Simulations remain labelled. Corrections add a new observation.
            </p>
            {(["observed_at", "value", "evidence", "notes"] as const).map((field) => (
              <label key={field} className="block text-sm text-gray-300">
                {label(field)}
                {field === "value" && " (blank means unknown)"}
                {["evidence", "notes"].includes(field) ? (
                  <textarea
                    aria-label={`Observation ${field}`}
                    className="agile-input w-full"
                    rows={3}
                    value={observation[field]}
                    disabled={busy || loading}
                    required={field === "evidence"}
                    maxLength={field === "evidence" ? 12000 : 4000}
                    onChange={(e) =>
                      setObservation((previous) => ({
                        ...previous,
                        [field]: e.target.value,
                      }))
                    }
                  />
                ) : (
                  <input
                    aria-label={`Observation ${field}`}
                    className="agile-input w-full"
                    value={observation[field]}
                    disabled={busy || loading}
                    type={
                      field === "value"
                        ? "number"
                        : field === "observed_at"
                          ? "datetime-local"
                          : "text"
                    }
                    step="any"
                    required={!["value", "notes"].includes(field)}
                    maxLength={
                      field === "evidence"
                        ? 12000
                        : field === "notes"
                          ? 4000
                          : undefined
                    }
                    onChange={(e) =>
                      setObservation((previous) => ({
                        ...previous,
                        [field]: e.target.value,
                      }))
                    }
                  />
                )}
              </label>
            ))}
            <button className="office-filter" disabled={busy || loading}>
              Save observation
            </button>
          </form>
        </article>
      )}
    </section>
  );
}
