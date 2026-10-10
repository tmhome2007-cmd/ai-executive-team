"use client";

import { useCallback, useEffect, useState } from "react";
import NeuralVoiceAudition from "./neural-voice-audition";
import CharacterAvatar, { type CharacterPresentation } from "./character-avatar";
import type { ExecutiveProfile } from "./company-records";
const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
type Department = { id: number; name: string; executive_key: string; floor: string; status: string; version: number };
type Employee = { id: number; name: string; job_title: string; department_id: number; department_name: string; capacity_hours: number; allocated_hours: number; status: string; version: number; character_key: string };
type Assignment = { id: number; employee_name: string; task_title: string; employee_id: number; task_id: number; hours: number; status: string; version: number };
type Settings = { enabled: boolean; version: number };
type PersonalEvent = { id: number; kind: string; character_key: string; partner_key: string | null; narrative: string; simulated_at: string; resulting_state: string | null };
function Field({ name, label, type = "text", optional = false }: { name: string; label: string; type?: string; optional?: boolean }) {
  return <label className="block text-sm">{label}<input className="agile-input w-full" aria-label={label} type={type} name={name} min={type === "number" ? 0 : undefined} step={type === "number" ? "any" : undefined} maxLength={2000} required={!optional} /></label>;
}
function VoicePreview({ profile, name, onSave, busy, apiKey, onAuthFailure }: { profile: CharacterPresentation; name: string; onSave: (voice: CharacterPresentation["voice"]) => void; busy: boolean; apiKey: string; onAuthFailure: () => void }) {
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [candidate, setCandidate] = useState("");
  const [message, setMessage] = useState("");
  const [playing, setPlaying] = useState(false);
  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const load = () => setVoices(window.speechSynthesis.getVoices().filter(v => v.localService).sort((a, b) => a.lang.localeCompare(b.lang) || a.name.localeCompare(b.name)));
    load(); window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => { window.speechSynthesis.removeEventListener("voiceschanged", load); window.speechSynthesis.cancel(); };
  }, []);
  const saved = profile.voice.provider === "browser_local" ? voices.find(v => v.name === profile.voice.voice_name && v.lang === profile.voice.language) : undefined;
  const chosen = voices.find(v => v.voiceURI === candidate) || (!candidate ? saved : undefined);
  function preview(natural: boolean) {
    if (!chosen) { setMessage("Choose an installed local voice first. No remote or automatic voice fallback is used."); return; }
    window.speechSynthesis.cancel();
    const text = new SpeechSynthesisUtterance(`Hello, I am ${name}. Here is my recommendation: review the evidence, identify what is unknown, and choose the next step together.`);
    text.voice = chosen; text.lang = chosen.lang; text.pitch = natural ? 1 : profile.voice.pitch; text.rate = natural ? 1 : profile.voice.rate;
    text.onend = () => setPlaying(false);
    text.onerror = event => { setPlaying(false); if (event.error !== "canceled" && event.error !== "interrupted") setMessage("Voice preview failed. Check your installed voices."); };
    setPlaying(true); setMessage(`Preview: ${chosen.name} · ${chosen.lang} · ${natural ? "natural pitch and pace" : "saved pitch and pace"}`);
    window.speechSynthesis.speak(text);
  }
  return <section className="grid gap-2" aria-label="Local voice comparison">
    <p>{profile.voice.style}</p><p>Saved: {profile.voice.voice_name || "No voice chosen"} · pitch {profile.voice.pitch} · pace {profile.voice.rate}</p>
    <label>Compare installed local voice<select aria-label="Compare installed local voice" className="agile-input w-full" value={candidate || saved?.voiceURI || ""} onChange={e => { window.speechSynthesis.cancel(); setPlaying(false); setCandidate(e.target.value); }}><option value="">Choose a voice</option>{voices.map((v, i) => <option key={`${v.voiceURI}-${i}`} value={v.voiceURI}>{v.name} · {v.lang}</option>)}</select></label>
    <div className="flex flex-wrap gap-2"><button className="office-filter" disabled={!chosen} onClick={() => preview(true)}>Preview natural voice</button><button className="office-filter" disabled={!chosen} onClick={() => preview(false)}>Compare saved pitch / pace</button><button className="office-filter" disabled={!playing} onClick={() => { window.speechSynthesis.cancel(); setPlaying(false); }}>Stop voice</button></div>
    <button className="office-filter" disabled={!chosen || busy} onClick={() => { if (chosen) onSave({ ...profile.voice, provider: "browser_local", voice_name: chosen.name, language: chosen.lang, pitch: 1, rate: 1 }); }}>Save selected voice at natural pitch</button>
    <p className="text-sm">Compare clarity, naturalness and fit for this character. Previewing does not change the saved profile. Saving creates a retained profile version.</p>
    {!voices.length && <p className="text-sm text-amber-300">No local voices are exposed by this browser. Install a system voice, then reload. No cloud fallback is used.</p>}
    {profile.voice.provider === "browser_local" && profile.voice.voice_name && !saved && <p className="text-sm text-amber-300">Your saved voice is unavailable on this device. Select a replacement explicitly.</p>}
    <p role="status" className="text-sm">{message}</p>
    <details><summary>Voice quality and provider options</summary><p>Only voices reported as local by this browser are offered. Availability and quality vary by device. Natural pitch avoids artificial deepening; it cannot improve the underlying voice model.</p><p>On macOS, use System Settings → Accessibility → Read &amp; Speak (or Spoken Content) to manage/download system voices. Downloads need internet; not every installed voice is exposed to every browser.</p><p>Other candidates: Kokoro for a separately installed local neural engine; ElevenLabs for cloud synthesis with text leaving this computer, an account and plan/licensing constraints. Kokoro fixed local auditions are available below; ElevenLabs remains unconnected.</p></details>
    <NeuralVoiceAudition profile={profile} apiKey={apiKey} onSave={onSave} onAuthFailure={onAuthFailure} busy={busy} />
  </section>;
}
export default function PeopleSimulation({ apiKey, profiles, onAuthFailure }: { apiKey: string; profiles: Record<string, ExecutiveProfile>; onAuthFailure: () => void }) {
  const [tab, setTab] = useState("Characters");
  const [selected, setSelected] = useState("executive:ceo");
  const [character, setCharacter] = useState<CharacterPresentation | null>(null);
  const [profileHistory, setProfileHistory] = useState<CharacterPresentation[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [events, setEvents] = useState<PersonalEvent[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [relation, setRelation] = useState<{ version: number; state: string } | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [offset, setOffset] = useState(0);
  const request = useCallback(async <T,>(path: string, body?: unknown, method = "POST", signal?: AbortSignal): Promise<T> => {
    const response = await fetch(API + path, { method: body === undefined ? "GET" : method, signal, cache: "no-store", headers: { "X-API-Key": apiKey, ...(body === undefined ? {} : { "Content-Type": "application/json" }) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    if (response.status === 401) { onAuthFailure(); throw new Error("Unlock the dashboard again."); }
    if (!response.ok) { const result = await response.json().catch(() => ({})); throw new Error(typeof result.detail === "string" ? result.detail : "Check the fields and refresh before retrying."); }
    return response.json();
  }, [apiKey, onAuthFailure]);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([request<Department[]>(`/organization/departments?limit=50&offset=${offset}`, undefined, "GET", controller.signal), request<Employee[]>(`/organization/employees?limit=50&offset=${offset}`, undefined, "GET", controller.signal), request<Assignment[]>(`/organization/assignments?limit=50&offset=${offset}`, undefined, "GET", controller.signal), request<Settings>("/simulation/settings", undefined, "GET", controller.signal), request<PersonalEvent[]>(`/simulation/events?limit=50&offset=${offset}`, undefined, "GET", controller.signal)])
      .then(([d, e, a, s, p]) => { if (!controller.signal.aborted) { setDepartments(d); setEmployees(e); setAssignments(a); setSettings(s); setEvents(p); } }).catch(e => { if (!controller.signal.aborted) setMessage(e.message); });
    return () => controller.abort();
  }, [request, offset, revision]);
  useEffect(() => {
    const controller = new AbortController();
    request<CharacterPresentation>(`/characters/${encodeURIComponent(selected)}`, undefined, "GET", controller.signal).then(p => { if (!controller.signal.aborted) setCharacter(p); }).catch(e => { if (!controller.signal.aborted) { setCharacter(null); setMessage(e.message); } });
    return () => controller.abort();
  }, [selected, request, revision]);
  const executive = selected.startsWith("executive:") ? profiles[selected.split(":")[1]] : null;
  const name = executive?.name || employees.find(e => e.character_key === selected)?.name || selected;
  async function mutate(callback: () => Promise<unknown>) {
    setBusy(true); setMessage("");
    try { await callback(); setRevision(r => r + 1); setMessage("Saved. These records do not grant execution authority."); }
    catch (e) { setMessage(e instanceof Error ? e.message : "Change failed."); } finally { setBusy(false); }
  }
  function submit(event: React.FormEvent<HTMLFormElement>, callback: (data: FormData) => Promise<unknown>) { event.preventDefault(); const data = new FormData(event.currentTarget); mutate(() => callback(data)); }
  return <section aria-label="People and simulation" className="space-y-5">
    <div className="flex flex-wrap gap-2">{["Characters", "Workforce", "Personal lives"].map(label => <button className="office-filter" key={label} aria-pressed={tab === label} onClick={() => setTab(label)}>{label}</button>)}</div>
    {message && <p role="status">{message}</p>}
    {tab === "Characters" && <>
      <p>Original fictional adult characters. Presentation is separate from the executives’ existing personalities and business authority. These are editable 2D previews for the future 3D office.</p>
      <label>Character<select aria-label="Character" className="agile-input" value={selected} onChange={e => setSelected(e.target.value)}>{Object.entries(profiles).map(([key, p]) => <option key={key} value={`executive:${key}`}>{p.name}</option>)}{employees.map(e => <option key={e.id} value={e.character_key}>{e.name} · employee</option>)}</select></label>
      {character && character.character_key === selected && <div className="grid md:grid-cols-2 gap-5"><article className="office-panel p-4"><CharacterAvatar presentation={character} name={name} /><h3 className="text-xl">{name}</h3><p>{character.appearance.description}</p><p>{character.body.height_cm} cm · {character.body.build.replaceAll("_", " ")} · version {character.version}</p><div className="flex justify-center"><CharacterAvatar presentation={character} name={name} compact /></div><VoicePreview key={`${selected}-${character.version}`} profile={character} name={name} apiKey={apiKey} onAuthFailure={onAuthFailure} busy={busy} onSave={voice => mutate(() => request(`/characters/${encodeURIComponent(selected)}`, { expected_version: character.version, appearance: character.appearance, body: character.body, voice }, "PUT"))} /><button className="office-filter" disabled={busy} onClick={() => mutate(() => request<CharacterPresentation[]>(`/characters/${encodeURIComponent(selected)}/history?limit=10`).then(setProfileHistory))}>Show character history</button>{profileHistory.filter(p => p.character_key === selected).map(p => <p key={p.version}>Version {p.version}: {p.appearance.description} · {p.voice.style}</p>)}{executive && <details><summary>Existing role and personality</summary><p className="whitespace-pre-wrap">{executive.backstory}</p></details>}</article>
        <form key={`${selected}-${character.version}`} className="office-panel p-4 grid grid-cols-2 gap-3" onSubmit={e => submit(e, data => request(`/characters/${encodeURIComponent(selected)}`, { expected_version: character.version, appearance: { ...character.appearance, portrait_style: data.get("portrait_style"), description: String(data.get("description")), hair_style: String(data.get("hair")), beard: data.get("beard") === "on", skin_tone: data.get("skin"), hair_color: data.get("hair_color"), eye_color: data.get("eyes"), eye_tint: data.get("tint") }, body: { ...character.body, height_cm: Number(data.get("height")), build: data.get("build"), outfit_color: data.get("outfit") }, voice: { ...character.voice, voice_name: data.get("voice_name"), language: data.get("language"), pitch: Number(data.get("pitch")), rate: Number(data.get("rate")), style: data.get("style") } }, "PUT"))}>
          <h3 className="col-span-2">Edit presentation</h3><label className="col-span-2">Appearance description<textarea aria-label="Appearance description" className="agile-input w-full" name="description" defaultValue={character.appearance.description} maxLength={1000} required /></label>
          {([['skin', 'Skin color', character.appearance.skin_tone], ['hair_color', 'Hair color', character.appearance.hair_color], ['eyes', 'Eye color', character.appearance.eye_color], ['tint', 'Eye tint', character.appearance.eye_tint], ['outfit', 'Outfit color', character.body.outfit_color]] as const).map(([field, label, value]) => <label key={field}>{label}<input aria-label={label} name={field} type="color" defaultValue={value} /></label>)}
          <label>Portrait presentation<select aria-label="Portrait presentation" name="portrait_style" className="agile-input" defaultValue={character.appearance.portrait_style || "androgynous"}>{["masculine", "feminine", "androgynous"].map(style => <option key={style}>{style}</option>)}</select></label><label>Hair style<select aria-label="Hair style" name="hair" className="agile-input" defaultValue={character.appearance.hair_style}>{["dreadlocks", "short", "bob", "long", "curly", "bun"].map(v => <option key={v}>{v}</option>)}</select></label><label><input name="beard" type="checkbox" defaultChecked={character.appearance.beard} /> Beard</label>
          <label>Height (cm)<input aria-label="Height (cm)" name="height" className="agile-input w-full" type="number" min="140" max="220" required defaultValue={character.body.height_cm} /></label><label>Body build<select aria-label="Body build" name="build" className="agile-input" defaultValue={character.body.build}>{["slender", "average", "athletic", "well_built"].map(v => <option key={v}>{v}</option>)}</select></label>
          {([['voice_name', 'Installed voice name (optional)', character.voice.voice_name], ['language', 'Voice language', character.voice.language], ['style', 'Voice style description', character.voice.style]] as const).map(([field, label, value]) => <label key={field}>{label}<input aria-label={label} className="agile-input w-full" name={field} defaultValue={value} maxLength={field === "style" ? 400 : 120} required={field !== "voice_name"} /></label>)}
          {([['pitch', 'Voice pitch', character.voice.pitch], ['rate', 'Voice pace', character.voice.rate]] as const).map(([field, label, value]) => <label key={field}>{label}<input aria-label={label} className="agile-input w-full" name={field} type="number" min=".5" max="1.5" step=".01" required defaultValue={value} /></label>)}
          <button className="office-filter col-span-2" disabled={busy}>Save character version</button>
        </form></div>}
    </>}
    {tab === "Workforce" && <>
      <p>Employees are virtual adult characters with task allocations. They do not inherit executive tools, approve spending or automatically execute assigned tasks. Allocated hours remain committed until work is completed or cancelled.</p>
      <div className="grid md:grid-cols-2 gap-3">{departments.map(d => <article className="office-panel p-3" key={d.id}><h3>{d.name}</h3><p>Department #{d.id} · floor {d.floor} · {profiles[d.executive_key]?.name || d.executive_key} · {d.status} · version {d.version}</p></article>)}</div>
      <form className="office-panel p-4 grid md:grid-cols-2 gap-3" onSubmit={e => submit(e, data => request("/organization/departments", { department_key: data.get("key"), name: data.get("name"), executive_key: data.get("executive"), floor: data.get("floor") }))}><h3 className="md:col-span-2">Create department</h3><Field name="key" label="Department key" /><Field name="name" label="Department name" /><Field name="executive" label="Responsible executive key" /><Field name="floor" label="Office floor (01, 02 or 03)" /><button className="office-filter" disabled={busy}>Create department</button></form>
      <form className="office-panel p-4 grid md:grid-cols-2 gap-3" onSubmit={e => submit(e, data => request(`/organization/departments/${Number(data.get("department"))}`, { expected_version: Number(data.get("version")), name: data.get("name"), executive_key: data.get("executive"), floor: data.get("floor"), status: data.get("status") }, "PUT"))}><h3 className="md:col-span-2">Update department</h3><Field name="department" label="Department ID to update" type="number" /><Field name="version" label="Current department version" type="number" /><Field name="name" label="Updated department name" /><Field name="executive" label="Updated responsible executive key" /><Field name="floor" label="Updated office floor" /><label>Department status<select aria-label="Department status" name="status" className="agile-input"><option>active</option><option>archived</option></select></label><button className="office-filter" disabled={busy}>Update department</button></form>
      {employees.map(e => <article className="office-panel p-3" key={e.id}><h3>{e.name} · {e.job_title}</h3><p>Employee #{e.id} · {e.department_name} · {e.status} · {e.allocated_hours}/{e.capacity_hours} hours allocated · version {e.version}</p><button className="office-filter" onClick={() => { setSelected(e.character_key); setTab("Characters"); }}>View employee character</button></article>)}
      <form className="office-panel p-4 grid md:grid-cols-2 gap-3" onSubmit={e => submit(e, data => request("/organization/employees", { creation_key: data.get("key"), name: data.get("name"), job_title: data.get("title"), department_id: Number(data.get("department")), capacity_hours: Number(data.get("capacity")) }))}><h3 className="md:col-span-2">Create virtual employee</h3><Field name="key" label="Unique employee creation key" /><Field name="name" label="Employee name" /><Field name="title" label="Employee job title" /><Field name="department" label="Employee department ID" type="number" /><Field name="capacity" label="Employee capacity hours" type="number" /><button className="office-filter" disabled={busy}>Create virtual employee</button></form>
      <form className="office-panel p-4 grid md:grid-cols-2 gap-3" onSubmit={e => submit(e, data => request(`/organization/employees/${Number(data.get("employee"))}`, { expected_version: Number(data.get("version")), department_id: Number(data.get("department")), capacity_hours: Number(data.get("capacity")), status: data.get("status") }, "PUT"))}><h3 className="md:col-span-2">Employee lifecycle and capacity</h3><Field name="employee" label="Employee ID to update" type="number" /><Field name="version" label="Current employee version" type="number" /><Field name="department" label="Updated department ID" type="number" /><Field name="capacity" label="Updated employee capacity" type="number" /><label>Employee status<select aria-label="Employee status" className="agile-input" name="status">{["onboarding", "active", "suspended", "retired"].map(s => <option key={s}>{s}</option>)}</select></label><button className="office-filter" disabled={busy}>Update employee</button></form>
      <h3>Employee assignments</h3>{assignments.map(a => <article className="office-panel p-3" key={a.id}><p>Assignment #{a.id} · {a.employee_name} → {a.task_title} · {a.hours} hours · {a.status} · version {a.version}</p></article>)}
      <form className="office-panel p-4 grid md:grid-cols-2 gap-3" onSubmit={e => submit(e, data => request("/organization/assignments", { employee_id: Number(data.get("employee")), task_id: Number(data.get("task")), hours: Number(data.get("hours")) }))}><h3 className="md:col-span-2">Assign existing company work</h3><Field name="employee" label="Assigned employee ID" type="number" /><Field name="task" label="Ready company task ID" type="number" /><Field name="hours" label="Assignment hours" type="number" /><button className="office-filter" disabled={busy}>Assign company work</button></form>
      <form className="office-panel p-4 grid md:grid-cols-2 gap-3" onSubmit={e => submit(e, data => request(`/organization/assignments/${Number(data.get("assignment"))}/review`, { expected_version: Number(data.get("version")), status: data.get("status"), note: data.get("note") }))}><h3 className="md:col-span-2">Record assignment progress</h3><Field name="assignment" label="Assignment ID to review" type="number" /><Field name="version" label="Current assignment version" type="number" /><label>Assignment status<select aria-label="Assignment status" className="agile-input" name="status">{["in_progress", "completed", "cancelled"].map(s => <option key={s}>{s}</option>)}</select></label><Field name="note" label="Assignment review note" /><button className="office-filter" disabled={busy}>Record assignment progress</button></form>
    </>}
    {tab === "Personal lives" && <>
      <p className="text-amber-300">Fictional simulation only. These events never become business evidence, owner consent, spending authority or executive memory.</p>
      {settings && <form className="office-panel p-4 flex flex-wrap gap-3" onSubmit={e => submit(e, data => request("/simulation/settings", { expected_version: settings.version, enabled: data.get("enabled") === "on", note: data.get("note") }, "PUT"))}><label key={settings.version}><input type="checkbox" name="enabled" defaultChecked={settings.enabled} /> Enable personal simulation</label><Field name="note" label="Simulation policy note" /><button className="office-filter" disabled={busy}>Save simulation settings</button></form>}
      <form className="office-panel p-4 grid md:grid-cols-2 gap-3" onSubmit={e => submit(e, data => request<{ version: number; state: string }>(`/simulation/relationship?left=${encodeURIComponent(String(data.get("left")))}&right=${encodeURIComponent(String(data.get("right")))}`).then(value => setRelation(value)))}><h3 className="md:col-span-2">Check current fictional relationship</h3><Field name="left" label="First character key (executive:ceo or employee:1)" /><Field name="right" label="Second character key" /><button className="office-filter" disabled={busy}>Check relationship</button>{relation && <p>Relationship: {relation.state} · version {relation.version}</p>}</form>
      <form className="office-panel p-4 grid md:grid-cols-2 gap-3" onSubmit={e => submit(e, data => request("/simulation/events", { event_key: data.get("key"), kind: data.get("kind"), character_key: data.get("character"), partner_key: data.get("partner") || null, expected_relationship_version: Number(data.get("version") || 0), narrative: data.get("narrative"), simulated_at: new Date(String(data.get("time"))).toISOString() }))}><h3 className="md:col-span-2">Record a fictional personal event</h3><Field name="key" label="Unique personal event key" /><label>Event type<select aria-label="Event type" name="kind" className="agile-input">{["friendship", "dating", "marriage", "separation", "divorce", "hobby", "milestone"].map(s => <option key={s}>{s}</option>)}</select></label><Field name="character" label="Personal event character key" /><Field name="partner" label="Partner key for relationship events" optional /><Field name="version" label="Current relationship version (0 for new)" type="number" /><Field name="time" label="Fictional event time" type="datetime-local" /><Field name="narrative" label="Fictional event narrative" /><button className="office-filter" disabled={busy || !settings?.enabled}>Record fictional event</button></form>
      {events.map(e => <article className="office-panel p-3" key={e.id}><p>FICTIONAL · #{e.id} · {e.kind} · {e.character_key}{e.partner_key ? ` + ${e.partner_key}` : ""} · {new Date(e.simulated_at).toLocaleString()}</p><p className="whitespace-pre-wrap">{e.narrative}</p>{e.resulting_state && <p>Relationship state: {e.resulting_state}</p>}</article>)}
    </>}
    <div className="flex gap-2"><button className="office-filter" disabled={!offset || busy} onClick={() => setOffset(o => Math.max(0, o - 50))}>Newer people records</button><button className="office-filter" disabled={busy || Math.max(departments.length, employees.length, assignments.length, events.length) < 50} onClick={() => setOffset(o => o + 50)}>Older people records</button><button className="office-filter" disabled={busy} onClick={() => setRevision(r => r + 1)}>Refresh people records</button></div>
  </section>;
}
