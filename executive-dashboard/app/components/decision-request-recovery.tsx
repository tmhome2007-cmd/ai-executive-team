"use client";

import { useCallback, useState, useSyncExternalStore } from "react";

type RequestState = {
  request_id: string;
  status: "generating" | "completed" | "failed" | "interrupted" | "closed" | "unknown";
  decision_id?: number | null;
};

export function useDecisionRequestRecovery(
  apiBase: string,
  apiKey: string | null,
  onUnauthorized: () => void,
) {
  const storageKey = `decision-request:${apiBase}`;
  const snapshot = useCallback(() => {
    const saved = localStorage.getItem(storageKey);
    return saved && /^[A-Za-z0-9:_-]{1,80}$/.test(saved) ? saved : null;
  }, [storageKey]);
  const subscribe = useCallback(
    (notify: () => void) => {
      const storageChanged = (event: StorageEvent) => {
        if (event.key === storageKey) notify();
      };
      window.addEventListener("storage", storageChanged);
      window.addEventListener("decision-request-change", notify);
      return () => {
        window.removeEventListener("storage", storageChanged);
        window.removeEventListener("decision-request-change", notify);
      };
    },
    [storageKey],
  );
  const requestId = useSyncExternalStore(subscribe, snapshot, () => null);
  const [state, setState] = useState<RequestState | null>(null);
  const [notice, setNotice] = useState("");

  const begin = () => {
    if (snapshot()) return null;
    const id = `decision:${crypto.randomUUID()}`;
    localStorage.setItem(storageKey, id);
    window.dispatchEvent(new Event("decision-request-change"));
    setState(null);
    setNotice("");
    return id;
  };

  const clear = () => {
    localStorage.removeItem(storageKey);
    window.dispatchEvent(new Event("decision-request-change"));
    setState(null);
    setNotice("");
  };

  const accept = (value: RequestState) => {
    if (value.request_id === snapshot()) setState(value);
  };

  const inspect = useCallback(async () => {
    const id = snapshot();
    if (!id || !apiKey) return;
    try {
      const response = await fetch(
        `${apiBase}/decisions/requests/${encodeURIComponent(id)}`,
        {
          headers: { "X-API-Key": apiKey },
          cache: "no-store",
        },
      );
      if (snapshot() !== id) return;
      if (response.status === 401) {
        onUnauthorized();
        return;
      }
      if (response.status === 404) {
        setState({ request_id: id, status: "unknown" });
        setNotice(
          "Delivery may still be pending. Closing recovery will block this request if it has not started.",
        );
        return;
      }
      if (!response.ok)
        throw new Error(
          "Request status is unavailable. Keep this request reference and check again.",
        );
      const value: RequestState = await response.json();
      if (snapshot() === id && value.request_id === id) {
        setState(value);
        setNotice("");
      }
    } catch (error) {
      if (snapshot() === id)
        setNotice(
          error instanceof Error ? error.message : "Request status is unavailable.",
        );
    }
  }, [apiBase, apiKey, onUnauthorized, snapshot]);

  const close = async () => {
    const id = snapshot();
    if (!id || !apiKey) return false;
    try {
      const response = await fetch(
        `${apiBase}/decisions/requests/${encodeURIComponent(id)}/close`,
        {
          method: "POST",
          headers: { "X-API-Key": apiKey },
        },
      );
      if (snapshot() !== id) return false;
      if (response.status === 401) {
        onUnauthorized();
        return false;
      }
      if (!response.ok) {
        setNotice(
          "This request cannot be closed yet. A meeting may still be queued or running; check status again.",
        );
        return false;
      }
      clear();
      return true;
    } catch {
      if (snapshot() === id)
        setNotice("Recovery could not be closed. Keep this request and check again.");
      return false;
    }
  };

  return {
    requestId,
    state,
    notice,
    begin,
    clear,
    accept,
    inspect,
    close,
    isActive: (id: string) => snapshot() === id,
  };
}

export default function DecisionRequestRecovery({
  recovery,
  onRefreshHistory,
  onClosed,
}: {
  recovery: ReturnType<typeof useDecisionRequestRecovery>;
  onRefreshHistory: () => void;
  onClosed: () => void;
}) {
  const status = recovery.state?.status;
  const message =
    status === "generating"
      ? "The meeting is queued or running. Keep the terminal open and check again."
      : status === "completed"
        ? `Saved as decision #${recovery.state?.decision_id}. Review it in Decision History.`
        : status === "failed"
          ? "Generation failed. Review the local model and errors before starting another decision."
          : status === "interrupted"
            ? "The server stopped before a confirmed completion. Review history before starting another decision."
            : status === "closed"
              ? "This request is closed and will not start a meeting."
              : "The request outcome is uncertain. Check this request and history before starting another meeting.";
  return (
    <div
      role="status"
      aria-label="Decision request recovery"
      className="p-3 border border-amber-900 rounded text-sm text-amber-200 space-y-2"
    >
      <p>{message}</p>
      {recovery.notice && <p>{recovery.notice}</p>}
      <div className="flex flex-wrap gap-4">
        <button
          type="button"
          className="text-cyan-300 underline"
          onClick={recovery.inspect}
        >
          Check Request Status
        </button>
        <button
          type="button"
          className="text-cyan-300 underline"
          onClick={onRefreshHistory}
        >
          Refresh Decision History
        </button>
        <button
          type="button"
          className="text-cyan-300 underline"
          onClick={async () => {
            if (await recovery.close()) onClosed();
          }}
        >
          Close Recovery
        </button>
      </div>
      <p>
        An empty history is not proof the request stopped. Closing recovery never starts
        a new meeting and cannot cancel one that is already running.
      </p>
    </div>
  );
}
