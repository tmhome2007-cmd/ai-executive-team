"use client";

import { useCallback, useEffect, useState } from "react";
import OperatingFoundation from "./operating-foundation";
import type { ExecutiveProfile } from "./company-records";
const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const tabs = ["Evidence", "Plans", "Discussion rounds", "Access inventory", "Operations"] as const;
type Tab = typeof tabs[number];
interface Source { id: number; title: string; summary: string; reference: string; observed_at: string; expires_at: string | null; freshness: string; verification: string; version: number }
interface Work { id: number; agile_task_id: number; assignee: string; status: string; note: string; decision_id: number | null }
interface Plan { id: number; title: string; status: string; version: number; goal_id: number; review_note: string; tasks: { key: string; title: string; acceptance_criteria: string; assignee: string; depends_on: string[]; expected_cost: number; currency: string }[]; work: Work[] }
interface Grant { id: number; resource_request_id: number; provider: string; target: string; roles: string[]; scopes: string[]; status: string; health: string; fresh: boolean; verified_until: string | null; version: number; secret_ref: string | null }
interface Message { id: number; executive_key: string; phase: string; round_number: number; body: string; profile: ExecutiveProfile; quality_checks?: { status: string; warnings: string[]; scope: string } }
interface Evidence { items: (Source & { relation: string; claim: string })[]; missing: boolean; conflicting: boolean; no_supporting_evidence: boolean; truncated: boolean }
const csv = (value: FormDataEntryValue | null) => String(value || "").split(",").map(v => v.trim()).filter(Boolean);
function Field({ name, label, type = "text", optional = false, max = 200, value }: { name: string; label: string; type?: string; optional?: boolean; max?: number; value?: string }) {
  return <label className="block text-sm text-gray-300">{label}<input aria-label={label} className="agile-input w-full" name={name} type={type} min={type === "number" ? 1 : undefined} required={!optional} maxLength={max} defaultValue={value} /></label>;
}
const Button = ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button className="office-filter" {...props}>{children}</button>;

export default function OrganizationalWork({ apiKey, profiles, onAuthFailure }: { apiKey: string; profiles: Record<string, ExecutiveProfile>; onAuthFailure: () => void }) {
  const [tab, setTab] = useState<Tab>("Evidence");
  const [sources, setSources] = useState<Source[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [grants, setGrants] = useState<Grant[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [workload, setWorkload] = useState<{ assignee: string; status: string; count: number }[]>([]);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [discussionId, setDiscussionId] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [offset, setOffset] = useState(0);
  const [more, setMore] = useState(false);
  const [revision, setRevision] = useState(0);
  const [runKey, setRunKey] = useState("");
  const request = useCallback(async <T,>(path: string, body?: unknown, method = "POST", signal?: AbortSignal): Promise<T> => {
    const response = await fetch(API + path, { method: body === undefined ? "GET" : method, signal, headers: { "X-API-Key": apiKey, ...(body === undefined ? {} : { "Content-Type": "application/json" }) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    if (response.status === 401) { onAuthFailure(); throw new Error("Owner access expired. Unlock the dashboard again."); }
    if (!response.ok) { const result = await response.json().catch(() => ({})); throw new Error(typeof result.detail === "string" ? result.detail : "Request failed. Check the fields and refresh before retrying."); }
    return response.json();
  }, [apiKey, onAuthFailure]);
  useEffect(() => {
    const controller = new AbortController(); let active = true;
    async function load() {
      setLoading(true); setError(null);
      try {
        if (tab === "Evidence") { const rows = await request<Source[]>(`/evidence?limit=50&offset=${offset}`, undefined, "GET", controller.signal); if (active) { setSources(old => offset ? [...old, ...rows.filter(r => !old.some(o => o.id === r.id))] : rows); setMore(rows.length === 50); } }
        if (tab === "Plans") { const [rows, counts] = await Promise.all([request<Plan[]>(`/plans?limit=50&offset=${offset}`, undefined, "GET", controller.signal), request<typeof workload>("/executive-workload", undefined, "GET", controller.signal)]); if (active) { setPlans(old => offset ? [...old, ...rows.filter(r => !old.some(o => o.id === r.id))] : rows); setWorkload(counts); setMore(rows.length === 50); } }
        if (tab === "Access inventory") { const rows = await request<Grant[]>(`/capabilities?limit=50&offset=${offset}`, undefined, "GET", controller.signal); if (active) { setGrants(old => offset ? [...old, ...rows.filter(r => !old.some(o => o.id === r.id))] : rows); setMore(rows.length === 50); } }
      } catch (e) { if (active) setError(e instanceof Error ? e.message : "Records unavailable."); }
      finally { if (active) setLoading(false); }
    }
    load(); return () => { active = false; controller.abort(); };
  }, [tab, offset, revision, request]);
  const refresh = () => { setOffset(0); setRevision(r => r + 1); };
  async function mutate(callback: () => Promise<unknown>) {
    setBusy(true); setError(null);
    try { await callback(); refresh(); } catch (e) { setError(e instanceof Error ? e.message : "Change failed."); } finally { setBusy(false); }
  }
  function submit(event: React.FormEvent<HTMLFormElement>, callback: (data: FormData, key: string) => Promise<unknown>) {
    event.preventDefault(); const data = new FormData(event.currentTarget); const key = runKey || crypto.randomUUID(); setRunKey(key);
    void mutate(async () => { await callback(data, key); setRunKey(""); });
  }
  const executiveName = (key: string) => profiles[key]?.name || key.toUpperCase();
  const readDiscussion = async (id: number) => { const result = await request<{ messages: Message[] }>(`/decisions/${id}/discussion`); setMessages(result.messages); setDiscussionId(id); };
  return <section aria-label="Organizational work" className="space-y-5">
    <header className="command-heading"><div><p className="command-eyebrow">Evidence and reviewed company work</p><h2>Organizational work</h2></div><Button disabled={busy || loading} onClick={refresh}>Refresh work records</Button></header>
    <nav aria-label="Work sections" className="flex flex-wrap gap-2">{tabs.map(t => <Button key={t} disabled={busy} aria-pressed={tab === t} onClick={() => { setTab(t); setOffset(0); setMore(false); setError(null); setRunKey(""); }}>{t}</Button>)}</nav>
    {error && <p role="alert" className="text-amber-300">{error}</p>}{loading && <p>Loading work records…</p>}{busy && <p role="status" className="text-teal-300">{tab === "Discussion rounds" ? "Working on discussion rounds. Each selected executive contributes to three rounds, then the CEO synthesizes. Three executives require ten model responses; a local model can take 10–20 minutes. Keep the backend running. An interrupted run may need checkpoint review before retrying." : tab === "Plans" ? "Processing the plan request. Executive reasoning can take several minutes on a local model. Keep the backend running." : "Saving or checking the record…"}</p>}
    {tab === "Evidence" && <>
      <p className="text-sm text-gray-400">Dated sources make provenance visible. Owner confirmation records your review; references are never fetched automatically.</p>
      <form className="command-card grid gap-3 md:grid-cols-2" onSubmit={e => submit(e, (d, key) => request("/evidence", { source_key: key, title: d.get("title"), reference: d.get("reference"), summary: d.get("summary"), observed_at: new Date(String(d.get("observed"))).toISOString(), expires_at: d.get("expires") ? new Date(String(d.get("expires"))).toISOString() : null }))}>
        <h3 className="md:col-span-2 font-semibold">Register a source</h3><Field name="title" label="Source title" /><Field name="reference" label="Source reference" max={1000} /><Field name="observed" label="Source observation date" type="datetime-local" /><Field name="expires" label="Source expiry date (optional)" type="datetime-local" optional /><label className="md:col-span-2">Source summary<textarea aria-label="Source summary" name="summary" required maxLength={12000} className="agile-input w-full" rows={3} /></label><Button disabled={busy || loading}>Register source</Button>
      </form>
      {!loading && sources.length === 0 && <p>No sources recorded yet.</p>}
      {sources.map(s => <article key={s.id} className="command-card space-y-2"><h3>Source #{s.id} · {s.title}</h3><p className="text-sm text-gray-400">Observed {new Date(s.observed_at).toLocaleString()} · Freshness {s.freshness} · {s.verification.replaceAll("_", " ")}</p><p className="text-sm break-words">Reference: {s.reference}</p><p className="whitespace-pre-wrap break-words text-sm">{s.summary}</p><div className="flex gap-2 flex-wrap"><Button disabled={busy || loading} onClick={() => void mutate(() => request(`/evidence/${s.id}`, { expected_version: s.version, verification: "owner_confirmed" }, "PATCH"))}>Confirm source #{s.id}</Button><Button disabled={busy || loading} onClick={() => void mutate(() => request(`/evidence/${s.id}`, { expected_version: s.version, verification: "disputed" }, "PATCH"))}>Dispute source #{s.id}</Button></div></article>)}
      <form className="command-card grid gap-3 md:grid-cols-2" onSubmit={e => submit(e, async d => { const result = await request<Evidence>("/evidence-links", { source_id: Number(d.get("source")), entity_kind: d.get("kind"), entity_id: Number(d.get("entity")), relation: d.get("relation"), claim: d.get("claim") }); setEvidence(result); })}>
        <h3 className="md:col-span-2">Link evidence to a record</h3><Field name="source" label="Evidence source ID" type="number" /><Field name="entity" label="Evidence record ID" type="number" /><label>Record type<select aria-label="Evidence record type" name="kind" className="agile-input w-full"><option value="decision">Decision</option><option value="observation">Observation</option><option value="discussion">Published discussion message</option></select></label><label>Relationship<select aria-label="Evidence relationship" name="relation" className="agile-input w-full"><option value="context">Context</option><option value="supports">Supports</option><option value="contradicts">Contradicts</option></select></label><Field name="claim" label="Claim (optional)" optional max={2000} /><Button disabled={busy || loading}>Link evidence</Button>
      </form>
      <form className="command-card flex flex-wrap gap-3" onSubmit={e => submit(e, async d => setEvidence(await request<Evidence>(`/evidence-for/${d.get("kind")}/${Number(d.get("entity"))}`)))}><label>Review evidence for<select name="kind" aria-label="Review evidence record type" className="agile-input"><option value="decision">Decision</option><option value="observation">Observation</option><option value="discussion">Discussion message</option></select></label><Field name="entity" label="Review evidence record ID" type="number" /><Button disabled={busy || loading}>Review linked evidence</Button></form>
      {evidence && <article className="command-card"><p>{evidence.missing ? "No sources linked." : evidence.no_supporting_evidence ? "Context only: no supporting evidence linked." : "Supporting sources recorded; this does not establish independent verification."}</p>{evidence.conflicting && <p className="text-amber-300">Conflicting evidence requires review.</p>}{evidence.items.map((s, i) => <p key={`${s.id}:${i}`}>Source #{s.id} · {s.relation} · {s.freshness} · {s.claim}</p>)}{evidence.truncated && <p>First 100 links shown.</p>}</article>}
    </>}
    {tab === "Plans" && <>
      <p className="text-sm text-gray-400">Executives propose assignments and dependencies. Plan approval schedules tool-free recommendations; actions and spending require their existing separate approvals.</p>
      <form className="command-card grid gap-3 md:grid-cols-2" onSubmit={e => submit(e, (d, key) => request("/plans/generate", { run_key: key, goal_id: Number(d.get("goal")), board_id: Number(d.get("board")), title: d.get("title"), proposer: d.get("proposer") }))}>
        <h3 className="md:col-span-2">Ask an executive to propose a plan</h3><Field name="title" label="Plan title" /><Field name="goal" label="Active goal ID" type="number" /><Field name="board" label="Company board ID" type="number" /><label>Proposing executive<select aria-label="Proposing executive" name="proposer" className="agile-input w-full" defaultValue="coo">{Object.entries(profiles).map(([key, profile]) => <option key={key} value={key}>{profile.name} · {key.toUpperCase()}</option>)}</select></label><Button disabled={busy || loading}>Generate plan proposal</Button>
      </form>
      <label className="block">Owner review note<textarea aria-label="Owner review note" className="agile-input w-full" value={note} maxLength={4000} onChange={e => setNote(e.target.value)} /></label><Button disabled={busy || loading} onClick={() => void mutate(() => request("/planned-work/dispatch", {}))}>Run approved planning tasks</Button>
      {!loading && plans.length === 0 && <p>No work plans proposed yet.</p>}
      {plans.map(p => <article key={p.id} className="command-card space-y-3"><h3>Plan #{p.id} · {p.title}</h3><p>{p.status} · Goal #{p.goal_id}</p>{p.tasks.map(t => <div key={t.key} className="contribution"><p>{t.title} · {executiveName(t.assignee)}</p><p className="text-sm whitespace-pre-wrap break-words">{t.acceptance_criteria}</p><p className="text-xs text-gray-400">Dependencies: {t.depends_on.join(", ") || "None"} · Estimated cost {t.expected_cost} {t.currency}</p></div>)}{p.status === "proposed" && <div className="flex gap-2"><Button disabled={busy || loading || !note.trim()} onClick={() => void mutate(() => request(`/plans/${p.id}/review`, { expected_version: p.version, approved: true, note }))}>Approve plan #{p.id}</Button><Button disabled={busy || loading || !note.trim()} onClick={() => void mutate(() => request(`/plans/${p.id}/review`, { expected_version: p.version, approved: false, note }))}>Reject plan #{p.id}</Button></div>}{p.work.map(w => <div key={w.id} className="contribution"><p>Task #{w.agile_task_id} · {executiveName(w.assignee)} · {w.status}</p><p className="text-sm">{w.note}{w.decision_id ? ` · Recommendation decision #${w.decision_id}` : ""}</p>{w.status === "review" && <div className="flex gap-2"><Button disabled={busy || loading || !note.trim()} onClick={() => void mutate(() => request(`/planned-work/${w.id}/review`, { approved: true, note }))}>Accept work #{w.id}</Button><Button disabled={busy || loading || !note.trim()} onClick={() => void mutate(() => request(`/planned-work/${w.id}/review`, { approved: false, note }))}>Reject work #{w.id}</Button></div>}</div>)}</article>)}
      <article className="command-card"><h3>Executive workload</h3>{workload.length ? workload.map(w => <p key={`${w.assignee}:${w.status}`}>{executiveName(w.assignee)} · {w.count} {w.status}</p>) : <p>No planned work assigned.</p>}</article>
    </>}
    {tab === "Discussion rounds" && <>
      <p className="text-sm text-gray-400">Proposal → critique → revision → CEO synthesis. These are published model contributions. Each executive keeps their existing identity and personality; the final direction awaits your approval.</p>
      <form className="command-card grid gap-3 md:grid-cols-2" onSubmit={e => submit(e, async (d, key) => { const result = await request<{ decision_id: number }>("/discussions", { run_key: key, topic: d.get("topic"), task_description: d.get("task"), agent_keys: d.getAll("roles"), source_ids: csv(d.get("sources")).map(Number), goal_id: d.get("goal") ? Number(d.get("goal")) : null }); await readDiscussion(result.decision_id); })}>
        <h3 className="md:col-span-2">Start a structured discussion</h3><Field name="topic" label="Discussion topic" /><Field name="goal" label="Discussion goal ID (optional)" type="number" optional /><Field name="sources" label="Discussion source IDs (optional, comma separated)" optional max={200} /><label className="md:col-span-2">Evidence and question<textarea name="task" aria-label="Discussion evidence and question" required maxLength={12000} className="agile-input w-full" rows={3} /></label><fieldset className="md:col-span-2"><legend>Participants (CEO synthesis required)</legend><div className="flex gap-3 flex-wrap">{Object.entries(profiles).map(([key, profile]) => <label key={key}><input type="checkbox" name="roles" value={key} defaultChecked={key === "ceo" || key === "cfo"} /> {profile.name} ({key.toUpperCase()})</label>)}</div></fieldset><Button disabled={busy || loading}>Start discussion rounds</Button>
      </form>
      <form className="command-card flex gap-3 flex-wrap" onSubmit={e => submit(e, async d => readDiscussion(Number(d.get("decision"))))}><Field name="decision" label="Discussion decision ID" type="number" /><Button disabled={busy || loading}>Open discussion rounds</Button></form>
      {discussionId && <h3>Published rounds for decision #{discussionId}</h3>}{discussionId && messages.length === 0 && <p>No structured rounds recorded for this decision.</p>}
      {messages.map(m => <article key={m.id} className="command-card space-y-2"><h3>Round {m.round_number} · {m.phase} · {m.profile.name || executiveName(m.executive_key)}</h3><p className="text-xs text-gray-400">{m.profile.role} · Message #{m.id}</p><p className="whitespace-pre-wrap break-words">{m.body}</p>{m.quality_checks && <div className="rounded border border-amber-800 p-3 text-sm break-words"><p>{m.quality_checks.status === "review_required" ? "Discussion review required" : m.quality_checks.status === "not_assessed" ? "Quality not assessed" : "Basic format checks passed"}</p>{m.quality_checks.warnings.length > 0 && <ul className="list-disc pl-5">{m.quality_checks.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}<p className="text-xs text-gray-400">{m.quality_checks.scope}. Owner approval remains separate.</p></div>}</article>)}
    </>}
    {tab === "Access inventory" && <>
      <p className="text-sm text-gray-400">Provide a scope against an approved resource request, then verify it. Store credential values in the backend environment; enter only the GITHUB_TOKEN reference here. Manual connectors stay unverified. Browser checks establish local runtime readiness for an allowed host.</p>
      <form className="command-card grid gap-3 md:grid-cols-2" onSubmit={e => submit(e, d => request("/capabilities", { resource_request_id: Number(d.get("resource")), provider: d.get("provider"), target: d.get("target"), scopes: csv(d.get("scopes")), roles: csv(d.get("roles")), secret_ref: d.get("provider") === "github" ? "GITHUB_TOKEN" : null }))}>
        <h3 className="md:col-span-2">Provide scoped access</h3><Field name="resource" label="Approved resource request ID" type="number" /><label>Provider<select name="provider" aria-label="Access provider" className="agile-input w-full"><option value="github">GitHub</option><option value="browser">Browser</option><option value="manual">Manual inventory</option></select></label><Field name="target" label="Exact target (owner/repository or browser host)" /><Field name="scopes" label="Scopes (repo.read, repo.write, page.read or page.interact)" /><Field name="roles" label="Executive keys (comma separated)" /><Button disabled={busy || loading}>Provide access</Button>
      </form>
      {!loading && grants.length === 0 && <p>No scoped access provided yet. Approved resource requests remain separate.</p>}
      {grants.map(g => <article key={g.id} className="command-card space-y-2"><h3>Access #{g.id} · {g.provider} · {g.target}</h3><p>Resource #{g.resource_request_id} · {g.status} · {g.health} · {g.fresh ? "Current health check" : "Not currently verified"}</p><p className="text-sm">Scopes: {g.scopes.join(", ")} · Roles: {g.roles.map(executiveName).join(", ")}</p>{g.secret_ref && <p className="text-xs text-gray-400">Secret reference: {g.secret_ref}</p>}{g.verified_until && <p className="text-xs">Verification expires {new Date(g.verified_until).toLocaleString()}</p>}{g.status !== "revoked" && <div className="flex gap-2"><Button disabled={busy || loading} onClick={() => void mutate(() => request(`/capabilities/${g.id}/verify`, {}))}>Verify access #{g.id}</Button><Button disabled={busy || loading} onClick={() => void mutate(() => request(`/capabilities/${g.id}/revoke`, { expected_version: g.version }))}>Revoke access #{g.id}</Button></div>}</article>)}
      <form className="command-card grid gap-3 md:grid-cols-2" onSubmit={e => submit(e, d => request(`/actions/${Number(d.get("action"))}/capabilities`, { requirements: [{ grant_id: Number(d.get("grant")), scope: d.get("scope") }] }))}><h3 className="md:col-span-2">Require access for a pending action</h3><Field name="action" label="Pending action ID" type="number" /><Field name="grant" label="Required access ID" type="number" /><Field name="scope" label="Required action scope" /><Button disabled={busy || loading}>Bind action access requirement</Button></form>
    </>}
    {tab === "Operations" && <OperatingFoundation apiKey={apiKey} onAuthFailure={onAuthFailure} />}
    {more && tab !== "Operations" && tab !== "Discussion rounds" && <Button disabled={busy || loading} onClick={() => setOffset(o => o + 50)}>Load older work records</Button>}
  </section>;
}
