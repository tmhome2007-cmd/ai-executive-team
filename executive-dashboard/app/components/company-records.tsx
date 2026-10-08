"use client";

import { useEffect, useState } from "react";

export interface ExecutiveProfile { name: string; role: string; goal: string; backstory: string }
interface Contribution {
  id: number; executive_key: string; body: string; phase: string; sequence: number;
  captured_at: string; profile: Partial<ExecutiveProfile>;
}
interface Activity {
  event_key: string; timestamp: string; category: string; title: string; detail: string;
  decision_id: number | null; action_id: number | null; resource_id: number | null; goal_id: number | null;
}
interface Decision { id: number; topic: string }
const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");

export default function CompanyRecords({ apiKey, decisions, profiles, onAuthFailure, onNavigate }: {
  apiKey: string; decisions: Decision[]; profiles: Record<string, ExecutiveProfile>;
  onAuthFailure: () => void; onNavigate: (view: "decisions" | "actions" | "resources" | "goals" | "activity" | "treasury" | "boards") => void;
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
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    const load = async () => {
      setTimelineLoading(true);
      try {
        const response = await fetch(`${API_BASE}/company/activity?limit=50&offset=${offset}`, { headers: { "X-API-Key": apiKey }, signal: controller.signal });
        if (response.status === 401) { onAuthFailure(); return; }
        if (!response.ok) throw new Error("Activity timeline unavailable. The backend may need a restart after updating.");
        const data = await response.json();
        if (!active) return;
        setItems(previous => offset ? [...previous, ...data.items.filter((item: Activity) => !previous.some(p => p.event_key === item.event_key))] : data.items);
        setHasMore(data.items.length === 50);
        setTimelineError(null);
      } catch (error) { if (active) setTimelineError(error instanceof Error ? error.message : "Activity unavailable."); }
      finally { if (active) setTimelineLoading(false); }
    };
    load();
    return () => { active = false; controller.abort(); };
  }, [apiKey, offset, revision, onAuthFailure]);

  useEffect(() => {
    if (!decisionId) return;
    const controller = new AbortController();
    let active = true;
    const load = async () => {
      setLoading(true);
      setContributions([]);
      setConversationError(null);
      try {
        const response = await fetch(`${API_BASE}/decisions/${decisionId}/conversations`, { headers: { "X-API-Key": apiKey }, signal: controller.signal });
        if (response.status === 401) { onAuthFailure(); return; }
        if (!response.ok) throw new Error("Recorded contributions unavailable. Restart the updated backend if this endpoint is missing.");
        const data = await response.json();
        if (active) setContributions(data.contributions);
      } catch (error) { if (active) setConversationError(error instanceof Error ? error.message : "Contributions unavailable."); }
      finally { if (active) setLoading(false); }
    };
    load();
    return () => { active = false; controller.abort(); };
  }, [apiKey, decisionId, revision, onAuthFailure]);

  const refresh = () => { setOffset(0); setRevision(r => r + 1); };
  return <section aria-label="Conversations and timeline" className="space-y-6">
    <header className="flex flex-wrap justify-between gap-4"><div><h2 className="text-2xl font-semibold">Conversations & activity</h2><p className="text-sm text-gray-400 mt-2">Published executive contributions and a timeline of recorded company work.</p></div><button className="office-filter" onClick={refresh} disabled={timelineLoading || loading}>Refresh records</button></header>
    <article className="command-card">
      <h3 className="text-lg font-semibold">Recorded executive contributions</h3>
      <p className="text-xs text-gray-500 my-3">These are final task outputs in task order, not a verbatim chat or hidden model reasoning. Older meetings may have no recorded individual contributions.</p>
      <div className="flex flex-wrap gap-3">
        <label className="text-sm text-gray-300">Meeting<select aria-label="Meeting for contributions" value={decisionId} onChange={e => { setDecisionId(e.target.value); setContributions([]); setLoading(false); }} className="block mt-2 bg-gray-950 border border-gray-700 rounded p-2 max-w-full"><option value="">Select a recorded decision</option>{decisionId && !decisions.some(d => String(d.id) === decisionId) && <option value={decisionId}>Decision #{decisionId} · from timeline</option>}{decisions.map(d => <option key={d.id} value={d.id}>#{d.id} · {d.topic}</option>)}</select></label>
        <label className="text-sm text-gray-300">Phase<select aria-label="Contribution phase" value={phase} onChange={e => setPhase(e.target.value)} className="block mt-2 bg-gray-950 border border-gray-700 rounded p-2"><option value="all">All phases</option><option value="decision">Decision</option><option value="preparation">Preparation</option></select></label>
      </div>
      {conversationError && <p role="alert" className="text-amber-300 mt-4">{conversationError}</p>}
      {loading ? <p className="text-gray-400 mt-4">Loading recorded contributions…</p> : decisionId && !conversationError && contributions.filter(c => phase === "all" || c.phase === phase).length === 0 ? <p className="text-gray-400 mt-4">No individual contributions were recorded for this meeting and phase. The final decision remains in Decisions.</p> : contributions.filter(c => phase === "all" || c.phase === phase).map(c => <article className="contribution" key={c.id}>
        <header className="flex flex-wrap justify-between gap-3"><div><h4 className="font-semibold text-teal-300">{c.profile.name || profiles[c.executive_key]?.name || c.executive_key.toUpperCase()}</h4><p className="text-xs text-gray-500">{c.profile.role || profiles[c.executive_key]?.role || c.executive_key} · {c.phase} · Task {c.sequence}</p></div><time className="text-xs text-gray-500">Captured {new Date(c.captured_at).toLocaleString()}</time></header>
        <p className="whitespace-pre-wrap text-sm text-gray-300 mt-4 break-words">{c.body}</p>
      </article>)}
    </article>
    <article className="command-card"><h3 className="text-lg font-semibold">Company activity timeline</h3><p className="text-xs text-gray-500 my-3">Meetings, contributions, proposals, results and the latest retained status transitions. Earlier transitions overwritten by existing status tables are not reconstructed.</p>
      {timelineError && <p role="alert" className="text-amber-300">{timelineError} Existing items may be stale.</p>}
      {!timelineLoading && !timelineError && items.length === 0 && <p className="text-gray-400">No company activity recorded yet.</p>}
      <ol className="company-timeline">{items.map(item => <li key={item.event_key}>
        <p className="text-xs text-gray-500 uppercase tracking-wide">{item.category} · <time>{new Date(item.timestamp).toLocaleString()}</time></p><h4 className="font-medium mt-1">{item.title}</h4><p className="text-sm text-gray-400 mt-1 break-words">{item.detail}</p>
        <div className="flex flex-wrap gap-x-4">{item.decision_id && <button className="command-link" onClick={() => { setDecisionId(String(item.decision_id)); setPhase("all"); }}>Contributions for decision #{item.decision_id} ↑</button>}{item.decision_id && <button className="command-link" onClick={() => onNavigate("decisions")}>Decision #{item.decision_id} →</button>}{item.action_id && <button className="command-link" onClick={() => onNavigate("actions")}>Action #{item.action_id} →</button>}{item.resource_id && <button className="command-link" onClick={() => onNavigate("resources")}>Resource #{item.resource_id} →</button>}{item.category === "task" && <button className="command-link" onClick={() => onNavigate("boards")}>Company board →</button>}{item.category === "treasury" && <button className="command-link" onClick={() => onNavigate("treasury")}>Treasury →</button>}{item.goal_id && <button className="command-link" onClick={() => onNavigate("goals")}>Goal #{item.goal_id} →</button>}</div>
      </li>)}</ol>
      {timelineLoading && <p className="text-gray-400">Loading activity…</p>}{hasMore && !timelineError && <button disabled={timelineLoading} className="office-filter" onClick={() => setOffset(o => o + 50)}>Load older activity</button>}
    </article>
  </section>;
}
