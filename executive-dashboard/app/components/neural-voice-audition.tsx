"use client";
import { useEffect, useRef, useState } from "react";
import type { CharacterPresentation } from "./character-avatar";
const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
type Catalog = { voices: { id: string; label: string; available: boolean }[]; text: string; scope: string };
export default function NeuralVoiceAudition({ profile, apiKey, onSave, onAuthFailure, busy }: { profile: CharacterPresentation; apiKey: string; onSave: (voice: CharacterPresentation["voice"]) => void; onAuthFailure: () => void; busy: boolean }) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [choice, setChoice] = useState(profile.voice.provider === "kokoro_local" ? profile.voice.voice_name : "");
  const [message, setMessage] = useState("");
  const [source, setSource] = useState("");
  const [loading, setLoading] = useState(false);
  const audio = useRef<HTMLAudioElement>(null);
  const download = useRef<AbortController | null>(null);
  const objectUrl = useRef("");
  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API}/characters/voice-samples`, { headers: { "X-API-Key": apiKey }, cache: "no-store", signal: controller.signal })
      .then(async r => { if (r.status === 401) { onAuthFailure(); throw new Error("Unlock the dashboard again."); } if (!r.ok) throw new Error("Neural audition catalog unavailable."); return r.json() as Promise<Catalog>; })
      .then(result => { if (!controller.signal.aborted) setCatalog(result); })
      .catch(error => { if (!controller.signal.aborted) setMessage(error.message); });
    return () => { controller.abort(); download.current?.abort(); if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); };
  }, [apiKey, onAuthFailure]);
  function stop() {
    download.current?.abort(); audio.current?.pause();
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = ""; setSource(""); setLoading(false);
  }
  async function load() {
    stop(); window.speechSynthesis?.cancel();
    const controller = new AbortController(); download.current = controller; setLoading(true); setMessage("");
    try {
      const response = await fetch(`${API}/characters/voice-samples/${encodeURIComponent(choice)}`, { headers: { "X-API-Key": apiKey }, cache: "no-store", signal: controller.signal });
      if (response.status === 401) { onAuthFailure(); throw new Error("Unlock the dashboard again."); }
      if (!response.ok) throw new Error("Sample unavailable. Run ./company voices, then refresh Characters.");
      if (!response.headers.get("content-type")?.startsWith("audio/wav")) throw new Error("Invalid audition response.");
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      if (blob.size > 4 * 1024 * 1024) throw new Error("Audition is too large.");
      objectUrl.current = URL.createObjectURL(blob); setSource(objectUrl.current); setMessage("Press Play below. Compare clarity, naturalness and fit; saving is separate.");
    } catch (error) { if (!controller.signal.aborted) setMessage(error instanceof Error ? error.message : "Audition failed."); }
    finally { if (!controller.signal.aborted) setLoading(false); }
  }
  const selected = catalog?.voices.find(v => v.id === choice);
  return <section className="office-panel p-3 grid gap-2" aria-label="Neural voice auditions">
    <h4>Local neural voices — Kokoro</h4>
    <p>Try these instead of the system voices. These are fixed auditions generated on this computer, with no cloud speech service.</p>
    <label>Neural audition voice<select className="agile-input w-full" aria-label="Neural audition voice" value={choice} onChange={e => { stop(); setChoice(e.target.value); }}><option value="">Choose an audition</option>{catalog?.voices.map(v => <option key={v.id} value={v.id} disabled={!v.available}>{v.label}{!v.available ? " · not installed" : ""}</option>)}</select></label>
    {catalog && !catalog.voices.some(v => v.available) && <p>Install once with <code>./company voices</code>, then refresh Characters. Downloads use internet; synthesis is local.</p>}
    <div className="flex flex-wrap gap-2"><button className="office-filter" disabled={!selected?.available || loading} onClick={load}>{loading ? "Loading audition…" : "Load neural audition"}</button><button className="office-filter" disabled={!source && !loading} onClick={stop}>Stop neural audition</button></div>
    <audio ref={audio} controls src={source || undefined} className={source ? "w-full" : "hidden"} aria-label="Neural audition playback" onPlay={() => window.speechSynthesis?.cancel()} />
    <button className="office-filter" disabled={!selected?.available || busy} onClick={() => onSave({ ...profile.voice, provider: "kokoro_local", language: "en-US", voice_name: choice, pitch: 1, rate: 1 })}>Save neural voice preference</button>
    <p className="text-sm">{catalog?.scope || "Fixed audition only. Voicing generated conversations is future work."} No voice quality acceptance is recorded automatically.</p>
    <p role="status">{message}</p>
  </section>;
}
