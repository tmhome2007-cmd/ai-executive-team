"use client";

import { useCallback, useEffect, useState } from "react";
import type { ExecutiveProfile } from "./company-records";

const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const COLUMNS = ["backlog", "ready", "in_progress", "review", "done", "blocked"] as const;
interface Board { id: number; name: string; kind: "company" | "development" }
interface Task {
  id: number; board_id: number; title: string; description: string; acceptance_criteria: string;
  assignee: string; priority: string; status: string; blocked_reason: string; completion_note: string;
  goal_id: number | null; decision_id: number | null; action_id: number | null; version: number;
}
const blank = { title: "", description: "", acceptance_criteria: "", assignee: "owner", priority: "medium", status: "backlog", blocked_reason: "", completion_note: "", goal_id: "", decision_id: "", action_id: "" };

export default function AgileBoard({ apiKey, profiles, onAuthFailure, onNavigate }: {
  apiKey: string; profiles: Record<string, ExecutiveProfile>; onAuthFailure: () => void;
  onNavigate: (view: "goals" | "decisions" | "actions") => void;
}) {
  const [boards, setBoards] = useState<Board[]>([]);
  const [boardId, setBoardId] = useState("");
  const [boardName, setBoardName] = useState("");
  const [kind, setKind] = useState<Board["kind"]>("company");
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selected, setSelected] = useState<Task | null>(null);
  const [draft, setDraft] = useState(blank);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const board = boards.find(b => String(b.id) === boardId);
  const request = useCallback(async (path: string, method = "GET", body?: unknown) => {
    const response = await fetch(`${API}${path}`, { method, headers: { "X-API-Key": apiKey, ...(body ? { "Content-Type": "application/json" } : {}) }, ...(body ? { body: JSON.stringify(body) } : {}) });
    if (response.status === 401) { onAuthFailure(); throw new Error("Sign in again."); }
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(typeof data?.detail === "string" ? data.detail : "Board unavailable. Restart the updated backend if this endpoint is missing.");
    return data;
  }, [apiKey, onAuthFailure]);
  const loadBoards = useCallback(async () => {
    try { setBoards(await request("/boards")); setError(null); }
    catch (error) { setError(error instanceof Error ? error.message : "Boards unavailable."); }
  }, [request]);
  useEffect(() => {
    let active = true;
    request("/boards").then(data => { if (active) { setBoards(data); setError(null); } })
      .catch(error => { if (active) setError(error instanceof Error ? error.message : "Boards unavailable."); });
    return () => { active = false; };
  }, [request]);
  useEffect(() => {
    if (!boardId) return;
    let active = true;
    const load = async () => {
      setLoading(true);
      try { const data = await request(`/boards/${boardId}/tasks?limit=100`); if (active) { setTasks(data); setHasMore(data.length === 100); setError(null); } }
      catch (error) { if (active) setError(error instanceof Error ? error.message : "Tasks unavailable."); }
      finally { if (active) setLoading(false); }
    };
    load();
    return () => { active = false; };
  }, [boardId, request]);
  const refresh = async (older = false) => {
    if (!boardId) { await loadBoards(); return; }
    setLoading(true);
    try {
      const data = await request(`/boards/${boardId}/tasks?limit=100&offset=${older ? tasks.length : 0}`);
      setTasks(previous => older ? [...previous, ...data.filter((task: Task) => !previous.some(p => p.id === task.id))] : data);
      setHasMore(data.length === 100); setError(null);
    } catch (error) { setError(error instanceof Error ? error.message : "Tasks unavailable."); }
    finally { setLoading(false); }
  };
  const createBoard = async (roadmap = false) => {
    if (!roadmap && !boardName.trim()) { setError("Enter a board name."); return; }
    setBusy(true);
    try {
      const created = await request(roadmap ? "/boards/roadmap" : "/boards", "POST", roadmap ? {} : { name: boardName.trim(), kind });
      await loadBoards(); setTasks([]); setBoardId(String(created.id)); setBoardName(""); setEditing(false); setSelected(null);
      if (String(created.id) === boardId) await refresh();
    } catch (error) { setError(error instanceof Error ? error.message : "Could not create board."); }
    finally { setBusy(false); }
  };
  const edit = (task: Task | null) => {
    setSelected(task); setEditing(true);
    setDraft(task ? { ...task, goal_id: task.goal_id ? String(task.goal_id) : "", decision_id: task.decision_id ? String(task.decision_id) : "", action_id: task.action_id ? String(task.action_id) : "" } : blank);
  };
  const save = async () => {
    if (!boardId) return;
    setBusy(true); setError(null);
    try {
      const fields: Record<string, unknown> = { title: draft.title, description: draft.description, acceptance_criteria: draft.acceptance_criteria, assignee: draft.assignee, priority: draft.priority };
      for (const field of ["goal_id", "decision_id", "action_id"] as const) {
        if (draft[field] && (!Number.isSafeInteger(Number(draft[field])) || Number(draft[field]) < 1)) throw new Error("Company record links must be positive IDs.");
        fields[field] = draft[field] ? Number(draft[field]) : null;
      }
      if (selected) Object.assign(fields, { expected_version: selected.version, status: draft.status, blocked_reason: draft.blocked_reason, completion_note: draft.completion_note });
      await request(selected ? `/tasks/${selected.id}` : `/boards/${boardId}/tasks`, selected ? "PATCH" : "POST", fields);
      setEditing(false); setSelected(null); await refresh();
    } catch (error) { setError(error instanceof Error ? error.message : "Could not save task."); }
    finally { setBusy(false); }
  };

  return <section aria-label="Agile boards" className="space-y-6">
    <header><h2 className="text-2xl font-semibold">Agile boards</h2><p className="text-sm text-gray-400 mt-2">Plan product development separately from executive company work.</p></header>
    <div className="command-card"><div className="flex flex-wrap gap-3 items-end">
      <label className="text-sm min-w-0 max-w-full">Board<select aria-label="Selected agile board" disabled={loading || busy} value={boardId} onChange={e => { setBoardId(e.target.value); setTasks([]); setEditing(false); setSelected(null); }} className="agile-input"><option value="">Choose a board</option>{boards.map(b => <option key={b.id} value={b.id}>{b.kind === "development" ? "Development" : "Company"} · {b.name}</option>)}</select></label>
      <button className="office-filter" onClick={() => refresh()} disabled={loading || busy}>Refresh board</button>
      <button className="office-filter" onClick={() => createBoard(true)} disabled={busy}>Create development roadmap</button>
    </div><div className="flex flex-wrap gap-3 items-end mt-5">
      <label className="text-sm">New board name<input aria-label="New board name" value={boardName} onChange={e => setBoardName(e.target.value)} maxLength={120} className="agile-input" placeholder="Company work" /></label>
      <label className="text-sm">Purpose<select aria-label="New board purpose" value={kind} onChange={e => setKind(e.target.value as Board["kind"])} className="agile-input"><option value="company">Company work</option><option value="development">Product development</option></select></label>
      <button className="office-filter" onClick={() => createBoard()} disabled={busy}>Create board</button>
    </div><p className="text-xs text-gray-500 mt-4">Tasks organize work. Business approval and execution remain in Decisions and Actions. Up to 100 boards are listed.</p></div>
    {error && <p role="alert" className="text-amber-300 border border-amber-900 rounded-lg p-4">{error} Refresh to reload current records before retrying a stale edit.</p>}
    {board && <><div className="flex flex-wrap justify-between gap-3"><div><h3 className="font-semibold">{board.name}</h3><p className="text-xs text-teal-300 capitalize">{board.kind} · {tasks.length} loaded tasks</p></div><button className="office-filter" disabled={loading || busy} onClick={() => edit(null)}>New task</button></div>
      {editing && <form className="command-card space-y-4" onSubmit={e => { e.preventDefault(); save(); }}><h3 className="font-semibold">{selected ? `Edit task #${selected.id}` : "New task · starts in Backlog"}</h3>
        <label className="block text-sm">Title<input aria-label="Task title" required maxLength={200} value={draft.title} onChange={e => setDraft({ ...draft, title: e.target.value })} className="agile-input w-full" /></label>
        <label className="block text-sm">Description<textarea aria-label="Task description" maxLength={10000} value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} className="agile-input w-full" /></label>
        <label className="block text-sm">Acceptance criteria<textarea aria-label="Task acceptance criteria" maxLength={10000} value={draft.acceptance_criteria} onChange={e => setDraft({ ...draft, acceptance_criteria: e.target.value })} className="agile-input w-full" placeholder="What observable result makes this task complete?" /></label>
        <div className="flex flex-wrap gap-4"><label className="text-sm">Assigned to<select aria-label="Task assignee" value={draft.assignee} onChange={e => setDraft({ ...draft, assignee: e.target.value })} className="agile-input"><option value="owner">Owner</option>{draft.assignee !== "owner" && !profiles[draft.assignee] && <option value={draft.assignee}>{draft.assignee.toUpperCase()}</option>}{Object.entries(profiles).map(([key, profile]) => <option value={key} key={key}>{profile.name}</option>)}</select></label><label className="text-sm">Priority<select aria-label="Task priority" value={draft.priority} onChange={e => setDraft({ ...draft, priority: e.target.value })} className="agile-input">{["critical", "high", "medium", "low"].map(p => <option key={p}>{p}</option>)}</select></label>{selected && <label className="text-sm">Status<select aria-label="Task status" value={draft.status} onChange={e => setDraft({ ...draft, status: e.target.value })} className="agile-input">{COLUMNS.map(c => <option value={c} key={c}>{c.replaceAll("_", " ")}</option>)}</select></label>}</div>
        {board.kind === "company" && <div className="grid sm:grid-cols-3 gap-3">{(["goal_id", "decision_id", "action_id"] as const).map(field => <label className="text-sm" key={field}>{field.replace("_id", " ID")}<input aria-label={`Task ${field}`} type="number" min="1" step="1" value={draft[field]} onChange={e => setDraft({ ...draft, [field]: e.target.value })} className="agile-input w-full" /></label>)}</div>}
        {selected && <><label className="block text-sm">Blocked reason<textarea aria-label="Task blocked reason" maxLength={2000} value={draft.blocked_reason} onChange={e => setDraft({ ...draft, blocked_reason: e.target.value })} className="agile-input w-full" /></label><label className="block text-sm">Completion note<textarea aria-label="Task completion note" maxLength={10000} value={draft.completion_note} onChange={e => setDraft({ ...draft, completion_note: e.target.value })} className="agile-input w-full" placeholder="Record what was verified and where the evidence is." /></label></>}
        <div className="flex gap-3"><button className="office-filter" type="submit" disabled={busy}>{busy ? "Saving…" : "Save task"}</button><button className="office-filter" type="button" onClick={() => setEditing(false)}>Cancel edit</button></div>
      </form>}
      {loading && <p className="text-gray-400">Loading tasks…</p>}
      <div className="agile-columns">{COLUMNS.map(column => <section key={column} tabIndex={0} className="agile-column" aria-label={`Tasks ${column}`}><h4 className="capitalize font-semibold text-sm mb-4">{column.replaceAll("_", " ")} <span className="text-gray-500">{tasks.filter(t => t.status === column).length}</span></h4>{tasks.filter(t => t.status === column).map(task => <article className="agile-task" key={task.id}>
        <p className="text-xs uppercase text-teal-300">#{task.id} · {task.priority}</p><button className="text-left font-medium mt-2" onClick={() => edit(task)}>{task.title}</button><p className="text-xs text-gray-500 mt-3">{profiles[task.assignee]?.name || task.assignee}</p><details className="text-xs text-gray-400 mt-3"><summary className="cursor-pointer">Acceptance criteria</summary><p className="whitespace-pre-wrap mt-2">{task.acceptance_criteria || "Not defined yet"}</p></details>{task.blocked_reason && task.status === "blocked" && <p className="text-xs text-amber-300 mt-3">{task.blocked_reason}</p>}{task.status === "done" && <p className="text-xs text-gray-400 mt-3">{task.completion_note}</p>}
        <div className="flex flex-wrap gap-2">{task.goal_id && <button className="command-link" onClick={() => onNavigate("goals")}>Goal #{task.goal_id}</button>}{task.decision_id && <button className="command-link" onClick={() => onNavigate("decisions")}>Decision #{task.decision_id}</button>}{task.action_id && <button className="command-link" onClick={() => onNavigate("actions")}>Action #{task.action_id}</button>}</div>
      </article>)}{!tasks.some(t => t.status === column) && <p className="text-xs text-gray-600">No loaded tasks</p>}</section>)}</div>
      {hasMore && <button className="office-filter" disabled={loading} onClick={() => refresh(true)}>Load older tasks</button>}
    </>}
    {!boardId && <p className="text-gray-400">Create the development roadmap or a company board to begin planning.</p>}
  </section>;
}
