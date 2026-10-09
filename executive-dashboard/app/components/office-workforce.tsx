"use client";

import { useEffect, useState } from "react";
import CharacterAvatar, { type CharacterPresentation } from "./character-avatar";
const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
type Staff = { id: number; name: string; job_title: string; status: string; department_name: string; floor: string; allocated_hours: number; presentation: CharacterPresentation };
export default function OfficeWorkforce({ apiKey, floor, onAuthFailure }: { apiKey: string | null; floor: string; onAuthFailure: () => void }) {
  const [staff, setStaff] = useState<Staff[]>([]);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!apiKey) return;
    const controller = new AbortController();
    fetch(`${API}/organization/office-roster?limit=50&offset=${offset}${floor === "all" ? "" : `&floor=${encodeURIComponent(floor)}`}`, { headers: { "X-API-Key": apiKey }, signal: controller.signal, cache: "no-store" })
      .then(async r => { if (r.status === 401) { onAuthFailure(); throw new Error("Unlock the dashboard again."); } if (!r.ok) throw new Error("Staff records unavailable; restart the updated backend."); return r.json(); })
      .then(rows => { if (!controller.signal.aborted) { setStaff(rows); setError(""); } }).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [apiKey, floor, offset, onAuthFailure]);
  return <article className="command-card"><h3 className="font-semibold">Virtual employees</h3><p className="text-sm text-gray-400">Recorded lifecycle and allocated work, refreshed when this view opens. Assignment does not mean an employee is executing a task.</p>{error && <p role="alert">{error}</p>}
    {!error && !staff.length && <p className="mt-3">No virtual staff in this roster page. Create them under Organizational work → People & simulation.</p>}
    <div className="flex flex-wrap gap-4 mt-4">{staff.filter(s => floor === "all" || s.floor === floor).map(s => <div className="office-panel p-3" key={s.id}><CharacterAvatar compact presentation={s.presentation} name={s.name} /><h4>{s.name}</h4><p>{s.job_title} · {s.department_name}</p><p>{s.status} · {s.allocated_hours} hours assigned</p></div>)}</div>
    <div className="flex gap-2 mt-3"><button className="office-filter" disabled={!offset} onClick={() => setOffset(o => Math.max(0, o - 50))}>Newer staff</button><button className="office-filter" disabled={staff.length < 50} onClick={() => setOffset(o => o + 50)}>Older staff</button></div>
  </article>;
}
