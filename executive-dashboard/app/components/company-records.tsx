/** Published executive contributions and company activity with owner-facing playback. */
"use client";
import ConversationVoice from "./conversation-voice";
import AiReport from "./ai-report";

import { useEffect, useState } from "react";

import type { CharacterPresentation } from "./character-avatar";

export interface ExecutiveProfile {
  name: string;
  role: string;
  goal: string;
  backstory: string;
  presentation?: CharacterPresentation | null;
}
interface Contribution {
  id: number;
  executive_key: string;
  body: string;
  phase: string;
  sequence: number;
  captured_at: string;
  profile: Partial<ExecutiveProfile>;
}
interface Activity {
  event_key: string;
  timestamp: string;
  category: string;
  title: string;
  detail: string;
  actor?: string;
  source?: string;
  previous_state?: Record<string, unknown> | null;
  new_state?: Record<string, unknown>;
  legacy_snapshot?: number;
  decision_id: number | null;
  action_id: number | null;
  resource_id: number | null;
  goal_id: number | null;
}
interface Decision {
  id: number;
  topic: string;
}
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);

export default function CompanyRecords({
  apiKey,
  decisions,
  profiles,
  onAuthFailure,
  onNavigate,
}: {
  apiKey: string;
  decisions: Decision[];
  profiles: Record<string, ExecutiveProfile>;
  onAuthFailure: () => void;
  onNavigate: (
    view:
      | "decisions"
      | "actions"
      | "resources"
      | "goals"
      | "activity"
      | "treasury"
      | "boards"
      | "experiments",
  ) => void;
}) {
  const [items, setItems] = useState<Activity[]>([]);
  const [contributions, setContributions] = useState<Contribution[]>([]);
  const [decisionId, setDecisionId] = useState("");
  const [phase, setPhase] = useState("all");
  const [timelineError, setTimelineError] = useState<string | null>(null);
  const [conversationError, setConversationError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [revision, setRevision] = useState(0);
  const [beforeId, setBeforeId] = useState<number | null>(null);
  const [nextBeforeId, setNextBeforeId] = useState<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const load = async () => {
      setTimelineLoading(true);
      try {
        const response = await fetch(
          `${API_BASE}/company/activity?limit=50${beforeId ? `&before_id=${beforeId}` : ""}`,
          { headers: { "X-API-Key": apiKey }, signal: controller.signal },
        );
        if (response.status === 401) {
          onAuthFailure();
          return;
        }
        if (!response.ok)
          throw new Error(
            "Activity timeline unavailable. The backend may need a restart after updating.",
          );
        const data = await response.json();
        if (!active) return;
        setItems((previous) =>
          beforeId
            ? [
                ...previous,
                ...data.items.filter(
                  (item: Activity) =>
                    !previous.some((p) => p.event_key === item.event_key),
                ),
              ]
            : data.items,
        );
        setHasMore(Boolean(data.next_before_id));
        setNextBeforeId(data.next_before_id || null);
        setTimelineError(null);
      } catch (error) {
        if (active)
          setTimelineError(
            error instanceof Error ? error.message : "Activity unavailable.",
          );
      } finally {
        if (active) setTimelineLoading(false);
      }
    };
    load();
    return () => {
      active = false;
      controller.abort();
    };
  }, [apiKey, beforeId, revision, onAuthFailure]);

  useEffect(() => {
    if (!decisionId) return;
    const controller = new AbortController();
    let active = true;
    const load = async () => {
      setLoading(true);
      setContributions([]);
      setConversationError(null);
      try {
        const response = await fetch(
          `${API_BASE}/decisions/${decisionId}/conversations`,
          { headers: { "X-API-Key": apiKey }, signal: controller.signal },
        );
        if (response.status === 401) {
          onAuthFailure();
          return;
        }
        if (!response.ok)
          throw new Error(
            "Recorded contributions unavailable. Restart the updated backend if this endpoint is missing.",
          );
        const data = await response.json();
        if (active) setContributions(data.contributions);
      } catch (error) {
        if (active)
          setConversationError(
            error instanceof Error ? error.message : "Contributions unavailable.",
          );
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => {
      active = false;
      controller.abort();
    };
  }, [apiKey, decisionId, revision, onAuthFailure]);

  const refresh = () => {
    setBeforeId(null);
    setRevision((r) => r + 1);
  };
  return (
    <section aria-label="Conversations and timeline" className="space-y-6">
      <header className="flex flex-wrap justify-between gap-4">
        <div>
          <h2 className="text-2xl font-semibold">Conversations & activity</h2>
          <p className="text-sm text-gray-400 mt-2">
            Published executive contributions and a timeline of recorded company work.
          </p>
        </div>
        <button
          className="office-filter"
          onClick={refresh}
          disabled={timelineLoading || loading}
        >
          Refresh records
        </button>
      </header>
      <article className="command-card">
        <h3 className="text-lg font-semibold">Recorded executive contributions</h3>
        <p className="text-xs text-gray-500 my-3">
          These are final task outputs in task order, not a verbatim chat or hidden
          model reasoning. Older meetings may have no recorded individual contributions.
        </p>
        <div className="flex flex-wrap gap-3">
          <label className="text-sm text-gray-300">
            Meeting
            <select
              aria-label="Meeting for contributions"
              value={decisionId}
              onChange={(e) => {
                setDecisionId(e.target.value);
                setContributions([]);
                setLoading(false);
              }}
              className="block mt-2 bg-gray-950 border border-gray-700 rounded p-2 max-w-full"
            >
              <option value="">Select a recorded decision</option>
              {decisionId && !decisions.some((d) => String(d.id) === decisionId) && (
                <option value={decisionId}>
                  Decision #{decisionId} · from timeline
                </option>
              )}
              {decisions.map((d) => (
                <option key={d.id} value={d.id}>
                  #{d.id} · {d.topic}
                </option>
              ))}
            </select>
          </label>
          <label className="text-sm text-gray-300">
            Phase
            <select
              aria-label="Contribution phase"
              value={phase}
              onChange={(e) => setPhase(e.target.value)}
              className="block mt-2 bg-gray-950 border border-gray-700 rounded p-2"
            >
              <option value="all">All phases</option>
              <option value="decision">Decision</option>
              <option value="preparation">Preparation</option>
            </select>
          </label>
        </div>
        {conversationError && (
          <p role="alert" className="text-amber-300 mt-4">
            {conversationError}
          </p>
        )}
        {loading ? (
          <p className="text-gray-400 mt-4">Loading recorded contributions…</p>
        ) : decisionId &&
          !conversationError &&
          contributions.filter((c) => phase === "all" || c.phase === phase).length ===
            0 ? (
          <p className="text-gray-400 mt-4">
            No individual contributions were recorded for this meeting and phase. The
            final decision remains in Decisions.
          </p>
        ) : (
          contributions
            .filter((c) => phase === "all" || c.phase === phase)
            .map((c) => (
              <article className="contribution" key={c.id}>
                <header className="flex flex-wrap justify-between gap-3">
                  <div>
                    <h4 className="font-semibold text-teal-300">
                      {c.profile.name ||
                        profiles[c.executive_key]?.name ||
                        c.executive_key.toUpperCase()}
                    </h4>
                    <p className="text-xs text-gray-500">
                      {c.profile.role ||
                        profiles[c.executive_key]?.role ||
                        c.executive_key}{" "}
                      · {c.phase} · Task {c.sequence}
                    </p>
                  </div>
                  <time className="text-xs text-gray-500">
                    Captured {new Date(c.captured_at).toLocaleString()}
                  </time>
                </header>
                <AiReport text={c.body} />
                <ConversationVoice
                  sourceKind="contribution"
                  sourceId={c.id}
                  apiKey={apiKey}
                  onAuthFailure={onAuthFailure}
                />
              </article>
            ))
        )}
      </article>
      <article className="command-card">
        <h3 className="text-lg font-semibold">Company activity timeline</h3>
        <p className="text-xs text-gray-500 my-3">
          Database changes are retained from ledger installation onward. Legacy
          snapshots show the state when history recording began; earlier transitions
          remain unknown.
        </p>
        {timelineError && (
          <p role="alert" className="text-amber-300">
            {timelineError} Existing items may be stale.
          </p>
        )}
        {!timelineLoading && !timelineError && items.length === 0 && (
          <p className="text-gray-400">No company activity recorded yet.</p>
        )}
        <ol className="company-timeline">
          {items.map((item) => (
            <li key={item.event_key}>
              <p className="text-xs text-gray-500 uppercase tracking-wide">
                {item.category} ·{" "}
                <time>{new Date(item.timestamp).toLocaleString()}</time>
              </p>
              <h4 className="font-medium mt-1">{item.title}</h4>
              <p className="text-sm text-gray-400 mt-1 break-words">{item.detail}</p>
              {item.actor && (
                <p className="text-xs text-gray-500 mt-2">
                  Initiator: {item.actor} · Source: {item.source}
                </p>
              )}
              {item.new_state && (
                <details className="text-xs text-gray-400 mt-2">
                  <summary>Recorded state change</summary>
                  <p className="break-words mt-2">
                    Previous:{" "}
                    {item.previous_state
                      ? JSON.stringify(item.previous_state)
                      : item.legacy_snapshot
                        ? "Unknown earlier history"
                        : "No previous record"}
                  </p>
                  <p className="break-words mt-1">
                    New: {JSON.stringify(item.new_state)}
                  </p>
                </details>
              )}
              <div className="flex flex-wrap gap-x-4">
                {item.decision_id && (
                  <button
                    className="command-link"
                    onClick={() => {
                      setDecisionId(String(item.decision_id));
                      setPhase("all");
                    }}
                  >
                    Contributions for decision #{item.decision_id} ↑
                  </button>
                )}
                {item.decision_id && (
                  <button
                    className="command-link"
                    onClick={() => onNavigate("decisions")}
                  >
                    Decision #{item.decision_id} →
                  </button>
                )}
                {item.action_id && (
                  <button
                    className="command-link"
                    onClick={() => onNavigate("actions")}
                  >
                    Action #{item.action_id} →
                  </button>
                )}
                {item.resource_id && (
                  <button
                    className="command-link"
                    onClick={() => onNavigate("resources")}
                  >
                    Resource #{item.resource_id} →
                  </button>
                )}
                {item.category === "experiment" && (
                  <button
                    className="command-link"
                    onClick={() => onNavigate("experiments")}
                  >
                    Experiment records →
                  </button>
                )}
                {item.category === "task" && (
                  <button className="command-link" onClick={() => onNavigate("boards")}>
                    Company board →
                  </button>
                )}
                {item.category === "treasury" && (
                  <button
                    className="command-link"
                    onClick={() => onNavigate("treasury")}
                  >
                    Treasury →
                  </button>
                )}
                {item.goal_id && (
                  <button className="command-link" onClick={() => onNavigate("goals")}>
                    Goal #{item.goal_id} →
                  </button>
                )}
              </div>
            </li>
          ))}
        </ol>
        {timelineLoading && <p className="text-gray-400">Loading activity…</p>}
        {hasMore && !timelineError && (
          <button
            disabled={timelineLoading}
            className="office-filter"
            onClick={() => setBeforeId(nextBeforeId)}
          >
            Load older activity
          </button>
        )}
      </article>
    </section>
  );
}
