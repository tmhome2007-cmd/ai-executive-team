"use client";

import { useState } from "react";
import ApplicationAnswer from "./application-answer";

export interface IntakeValue {
  intent: "first_user";
  request: string;
  source_ids: number[];
  correction: string;
  lead_status: string | null;
  tool_status: string | null;
  owner_minutes: number | null;
  timezone: string;
}

export interface ConfirmedIntake extends IntakeValue {
  review_hash: string;
}

interface Question {
  key: "lead_status" | "tool_status" | "owner_minutes";
  prompt: string;
  options: { value: string; label: string }[];
}

interface Preview {
  questions: Question[];
  brief: string;
  checklist: string;
  review_hash: string;
  conditions: string[];
  records: {
    id: number;
    title: string;
    observed_at: string;
    summary: string;
    freshness: string;
  }[];
}

export default function DecisionIntake({
  apiBase,
  apiKey,
  onConfirmed,
  onInvalidate,
}: {
  apiBase: string;
  apiKey: string;
  onConfirmed: (value: ConfirmedIntake, brief: string) => void;
  onInvalidate: () => void;
}) {
  const [request, setRequest] = useState("");
  const [correction, setCorrection] = useState("");
  const [sources, setSources] = useState<{ id: number; title: string }[]>([]);
  const [sourceIds, setSourceIds] = useState<number[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [questions, setQuestions] = useState<Question[]>([]);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [used, setUsed] = useState(false);
  const headers = { "Content-Type": "application/json", "X-API-Key": apiKey };

  const input = (): IntakeValue => ({
    intent: "first_user",
    request,
    source_ids: sourceIds,
    correction,
    lead_status: answers.lead_status || null,
    tool_status: answers.tool_status || null,
    owner_minutes:
      answers.owner_minutes && answers.owner_minutes !== "unknown"
        ? Number(answers.owner_minutes)
        : null,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
  });
  const changed = () => {
    setPreview(null);
    setUsed(false);
    onInvalidate();
  };
  const call = async (path: string, body: unknown) => {
    const response = await fetch(`${apiBase}${path}`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "Unable to prepare the brief.");
    return data;
  };
  const review = async () => {
    setBusy(true);
    setError("");
    setUsed(false);
    try {
      const data: Preview = await call("/decisions/intake", input());
      setPreview(data);
      if (questions.length === 0) setQuestions(data.questions);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to prepare the brief.");
    } finally {
      setBusy(false);
    }
  };
  const confirm = async () => {
    if (!preview) return;
    setBusy(true);
    setError("");
    try {
      const value = { ...input(), review_hash: preview.review_hash };
      const data = await call("/decisions/intake/confirm", value);
      onConfirmed(value, data.brief);
      setUsed(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review the brief again.");
      changed();
    } finally {
      setBusy(false);
    }
  };
  const loadSources = async () => {
    setError("");
    try {
      const response = await fetch(`${apiBase}/evidence?limit=50`, { headers });
      if (!response.ok) throw new Error("Could not load reviewed context.");
      const data = await response.json();
      setSources(
        data.filter(
          (source: { verification: string }) =>
            source.verification === "owner_confirmed",
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load context.");
    }
  };

  return (
    <section
      aria-label="First-user request intake"
      className="bg-gray-900 border border-gray-700 rounded-lg p-5 space-y-4"
    >
      <h2 className="text-lg font-semibold">Plan a first real-user test</h2>
      <p className="text-sm text-gray-400">
        Write a short request. Review up to three questions and a conditional brief
        before starting the team. This helper currently supports first-user testing.
      </p>
      <label className="block text-sm">
        What would you like help with?
        <input
          value={request}
          maxLength={1200}
          onChange={(e) => {
            setRequest(e.target.value);
            changed();
          }}
          placeholder="Help me get the first real user for my tool"
          className="block w-full bg-gray-800 rounded p-2 mt-1"
        />
      </label>
      <p className="text-sm text-amber-200">
        {sourceIds.length
          ? `${sourceIds.length} project record(s) selected.`
          : "No saved project records selected. Add relevant facts below so the team can consider what your product does and what you have already tried."}
      </p>
      <details>
        <summary className="cursor-pointer text-sm">
          Add project facts or choose reviewed records
        </summary>
        <button
          type="button"
          onClick={loadSources}
          className="text-sm text-blue-300 my-2"
        >
          Load reviewed records
        </button>
        {sources.length === 0 && (
          <p className="text-xs text-gray-400">
            No reviewed records loaded. Nothing is assumed from other projects.
          </p>
        )}
        {sources.map((source) => (
          <label key={source.id} className="block text-sm">
            <input
              type="checkbox"
              checked={sourceIds.includes(source.id)}
              disabled={!sourceIds.includes(source.id) && sourceIds.length >= 5}
              onChange={() => {
                setSourceIds((ids) =>
                  ids.includes(source.id)
                    ? ids.filter((id) => id !== source.id)
                    : [...ids, source.id],
                );
                changed();
              }}
            />{" "}
            {source.title}
          </label>
        ))}
        <label className="block text-sm mt-2">
          Project facts or corrections
          <textarea
            value={correction}
            maxLength={1200}
            placeholder="Briefly: what the product does, who it helps, what you tried, and any corrections. Leave unconfirmed details unknown."
            onChange={(e) => {
              setCorrection(e.target.value);
              changed();
            }}
            className="block w-full bg-gray-800 rounded p-2"
          />
        </label>
      </details>
      {questions.map((question) => (
        <label key={question.key} className="block text-sm">
          {question.prompt}
          <select
            value={answers[question.key] || ""}
            onChange={(e) => {
              setAnswers((old) => ({ ...old, [question.key]: e.target.value }));
              changed();
            }}
            className="block bg-gray-800 p-2 rounded mt-1"
          >
            <option value="">Unknown / skip</option>
            {question.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      ))}
      <button
        type="button"
        disabled={busy || !request.trim()}
        onClick={review}
        className="px-4 py-2 rounded bg-blue-700 disabled:opacity-50"
      >
        {busy
          ? "Preparing…"
          : questions.length
            ? "Review brief with these answers"
            : "Clarify my request"}
      </button>
      {preview && (
        <div className="space-y-3">
          <p className="text-sm text-amber-200">
            Unanswered facts remain unknown. This brief authorizes no outreach or
            execution.
          </p>
          {preview.records.map((record) => (
            <p key={record.id} className="text-sm">
              Last recorded: {record.title} · {record.observed_at} · {record.freshness}.
              Not verified current.
            </p>
          ))}
          <ApplicationAnswer text={preview.checklist} />
          <details>
            <summary className="cursor-pointer text-sm font-medium">
              Practical owner checklist (application guidance)
            </summary>
            <div
              aria-label="Application owner checklist"
              className="whitespace-pre-wrap text-sm bg-gray-950 p-3 rounded mt-2"
            >
              {preview.checklist}
            </div>
          </details>
          <details>
            <summary className="cursor-pointer text-sm font-medium">
              Full context and instructions sent to the team
            </summary>
            <div
              aria-label="Intake brief preview"
              className="whitespace-pre-wrap text-sm bg-gray-950 p-3 rounded"
            >
              {preview.brief}
            </div>
          </details>
          <button
            type="button"
            disabled={busy || used}
            onClick={confirm}
            className="px-4 py-2 bg-teal-700 rounded disabled:opacity-50"
          >
            Confirm brief and fill decision form
          </button>
          {used && (
            <p role="status" className="text-sm text-teal-200">
              Brief confirmed. Review the filled form below, then choose Start Decision.
            </p>
          )}
        </div>
      )}
      {error && (
        <p role="alert" className="text-red-300">
          {error}
        </p>
      )}
    </section>
  );
}
