/** Owner-requested private speech playback for published text; no automatic synthesis. */
"use client";
import { useEffect, useRef, useState } from "react";
const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
export default function ConversationVoice({
  sourceKind,
  sourceId,
  apiKey,
  onAuthFailure,
}: {
  sourceKind: "contribution" | "discussion";
  sourceId: number;
  apiKey: string;
  onAuthFailure: () => void;
}) {
  const [savedKey, setSavedKey] = useState("");
  const [source, setSource] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const audio = useRef<HTMLAudioElement>(null),
    controller = useRef<AbortController | null>(null);
  const pending = useRef(""),
    objectUrl = useRef(""),
    key = useRef("");
  useEffect(() => {
    const stopOther = (event: Event) => {
      if ((event as CustomEvent).detail !== audio.current) audio.current?.pause();
    };
    window.addEventListener("company-neural-play", stopOther);
    return () => {
      window.removeEventListener("company-neural-play", stopOther);
      controller.current?.abort();
      if (pending.current)
        void fetch(`${API}/conversation-audio/requests/${pending.current}`, {
          method: "DELETE",
          headers: { "X-API-Key": apiKey },
          cache: "no-store",
        }).catch(() => {});
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    };
  }, [apiKey]);
  function stop() {
    controller.current?.abort();
    audio.current?.pause();
    if (pending.current)
      void fetch(`${API}/conversation-audio/requests/${pending.current}`, {
        method: "DELETE",
        headers: { "X-API-Key": apiKey },
        cache: "no-store",
      }).catch(() => {});
    pending.current = "";
    if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
    objectUrl.current = "";
    setSource("");
    setBusy(false);
  }
  async function checked(response: Response) {
    if (response.status === 401) {
      onAuthFailure();
      throw new Error("Unlock the dashboard again.");
    }
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(
        typeof data?.detail === "string"
          ? data.detail
          : "Local conversation speech unavailable.",
      );
    }
    return response;
  }
  async function load() {
    stop();
    setBusy(true);
    setMessage("Generating locally… Stop cancels the request and playback.");
    const current = new AbortController();
    controller.current = current;
    const requestId = crypto.randomUUID().replaceAll("-", "");
    pending.current = requestId;
    try {
      const response = await checked(
        await fetch(`${API}/conversation-audio`, {
          method: "POST",
          headers: { "X-API-Key": apiKey, "Content-Type": "application/json" },
          cache: "no-store",
          signal: current.signal,
          body: JSON.stringify({
            source_kind: sourceKind,
            source_id: sourceId,
            request_id: requestId,
          }),
        }),
      );
      const result = await response.json();
      if (current.signal.aborted) return;
      key.current = result.cache_key;
      setSavedKey(result.cache_key);
      const media = await checked(
        await fetch(`${API}/conversation-audio/${result.cache_key}`, {
          headers: { "X-API-Key": apiKey },
          cache: "no-store",
          signal: current.signal,
        }),
      );
      if (!media.headers.get("content-type")?.startsWith("audio/wav"))
        throw new Error("Invalid local audio response.");
      const blob = await media.blob();
      if (current.signal.aborted) return;
      if (!blob.size || blob.size > 64 * 1024 * 1024)
        throw new Error("Invalid local audio size.");
      objectUrl.current = URL.createObjectURL(blob);
      setSource(objectUrl.current);
      setMessage(
        `${result.cached ? "Loaded saved" : "Generated"} audio · ${result.voice} · character version ${result.profile_version} · ${Math.ceil(result.duration)} seconds. Expires ${new Date(result.expires_at * 1000).toLocaleString()}. Press Play below.`,
      );
    } catch (error) {
      if (!current.signal.aborted)
        setMessage(error instanceof Error ? error.message : "Speech failed.");
    } finally {
      if (!current.signal.aborted) {
        pending.current = "";
        setBusy(false);
      }
    }
  }
  async function remove() {
    const cacheKey = key.current;
    stop();
    setBusy(true);
    try {
      await checked(
        await fetch(`${API}/conversation-audio/${cacheKey}`, {
          method: "DELETE",
          headers: { "X-API-Key": apiKey },
          cache: "no-store",
        }),
      );
      key.current = "";
      setSavedKey("");
      setMessage("Audio deleted. Published text and history remain intact.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Audio deletion failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="mt-3 space-y-2"
      aria-label={`Local speech for ${sourceKind} ${sourceId}`}
    >
      <p className="text-xs text-gray-400">
        Read this published text aloud with the executive’s saved local neural voice. No
        cloud speech, new reasoning or automatic playback.
      </p>
      <div className="flex flex-wrap gap-2">
        <button type="button" className="office-filter" disabled={busy} onClick={load}>
          Load spoken contribution
        </button>
        <button
          type="button"
          className="office-filter"
          disabled={!busy && !source}
          onClick={() => {
            stop();
            setMessage(
              "Stopped. A completed saved audio file can be loaded again or deleted.",
            );
          }}
        >
          Stop conversation voice
        </button>
        <button
          type="button"
          className="office-filter"
          disabled={busy || !savedKey}
          onClick={remove}
        >
          Delete saved audio
        </button>
      </div>
      <audio
        ref={audio}
        controls
        preload="metadata"
        src={source || undefined}
        className={source ? "w-full" : "hidden"}
        aria-label="Spoken contribution playback"
        onPlay={() => {
          window.speechSynthesis?.cancel();
          window.dispatchEvent(
            new CustomEvent("company-neural-play", { detail: audio.current }),
          );
        }}
        onError={() => {
          if (objectUrl.current)
            setMessage(
              "Audio playback failed. Stop and reload; the published text is still available.",
            );
        }}
      />
      <p role="status" className="text-sm break-words">
        {message}
      </p>
    </section>
  );
}
