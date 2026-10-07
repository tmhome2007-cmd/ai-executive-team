"use client";

import { useState, useEffect, useCallback } from "react";

const API_BASE = "http://localhost:8000";

// --- Types ---

interface DecisionHistoryItem {
  id: number;
  timestamp: string;
  topic: string;
  agents_involved: string;
  task_description: string;
  decision_outcome: string;
  sandbox_mode: number;
}

interface DailyResearchStatus {
  last_run_time: string | null;
  success: boolean | null;
  database_id: number | null;
  message: string;
}

interface DecisionResponse {
  database_id: number;
  topic: string;
  final_decision: string;
  participants: string[];
  individual_outputs?: Record<string, string>;
  quality_warnings?: {
    unsupported_quantitative_claims?: string[];
    individual_outputs?: Record<string, string[]>;
    repeated_analysis?: Record<string, string[]>;
  };
}

interface PendingAction {
  id: number;
  timestamp: string;
  proposed_by: string;
  action_description: string;
  action_detail: string;
  status: string;
  reviewed_at: string | null;
  action_type?: string;
  result_detail?: string | null;
}

interface ExecutionResult {
  success: boolean;
  mode: string;
  action_id: number;
  detail?: string;
  stdout?: string;
  stderr?: string;
  error?: string;
  screenshot_path?: string;
}

const AGENT_OPTIONS: { key: string; label: string }[] = [
  { key: "ceo", label: "CEO" },
  { key: "cfo", label: "CFO" },
  { key: "coo", label: "COO" },
  { key: "cso", label: "CSO" },
  { key: "cmo", label: "CMO" },
  { key: "cto", label: "CTO" },
  { key: "chro", label: "CHRO" },
  { key: "general_counsel", label: "General Counsel" },
  { key: "cpo", label: "CPO" },
  { key: "board_director", label: "Board Director" },
];

// Human-readable labels + colors for every possible action status, used by
// both the Pending Actions cards and the new Action History list.
const STATUS_STYLES: Record<string, { label: string; className: string }> = {
  pending: { label: "Pending", className: "bg-gray-800 text-gray-300 border-gray-700" },
  approved: { label: "Approved", className: "bg-blue-900/60 text-blue-300 border-blue-700" },
  executing: { label: "Executing", className: "bg-yellow-900/60 text-yellow-300 border-yellow-700" },
  rejected: { label: "Rejected", className: "bg-red-900/60 text-red-300 border-red-700" },
  executed: { label: "Executed", className: "bg-green-900/60 text-green-300 border-green-700" },
  executed_dry_run: { label: "Executed (Dry Run)", className: "bg-purple-900/60 text-purple-300 border-purple-700" },
  blocked_dangerous: { label: "Blocked (Dangerous)", className: "bg-orange-900/60 text-orange-300 border-orange-700" },
  execution_failed: { label: "Execution Failed", className: "bg-red-900/60 text-red-300 border-red-700" },
};

// /screenshots/{filename} now requires X-API-Key, and a plain <img src="..."> tag
// cannot send custom headers (a real browser limitation, not a bug) — so this
// component fetches the image manually with the header, then renders it via a
// short-lived blob: URL instead. Cleans up the blob URL on unmount to avoid
// leaking memory across many screenshots viewed in one session.
function AuthenticatedScreenshot({ filename, apiKey }: { filename: string; apiKey: string }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    fetch(`${API_BASE}/screenshots/${filename}`, {
      headers: { "X-API-Key": apiKey },
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to load screenshot");
        return res.blob();
      })
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setBlobUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [filename, apiKey]);

  if (failed) return <p className="text-xs text-red-400 mt-1">Could not load screenshot.</p>;
  if (!blobUrl) return <p className="text-xs text-gray-500 mt-1">Loading screenshot...</p>;
  return (
    <img
      src={blobUrl}
      alt="Browser action screenshot"
      className="mt-1 rounded border border-gray-700 max-w-full"
    />
  );
}

function statusBadge(status: string) {
  const style = STATUS_STYLES[status] || {
    label: status,
    className: "bg-gray-800 text-gray-400 border-gray-700",
  };
  return (
    <span className={`text-xs border px-2 py-0.5 rounded font-mono ${style.className}`}>
      {style.label}
    </span>
  );
}

// Renders action_detail appropriately depending on action_type: a raw shell
// string stays as-is (monospace), while a file_operation's JSON gets parsed
// into a friendly "📄 write notes.txt" summary instead of showing raw JSON.
function renderActionDetail(actionType: string | undefined, actionDetail: string) {
  if (actionType === "file_operation") {
    try {
      const parsed = JSON.parse(actionDetail);
      const icon = parsed.operation === "read" ? "📖" : "📄";
      return (
        <div>
          <span className="text-blue-300">
            {icon} {parsed.operation} → {parsed.file_path}
          </span>
          {parsed.content && (
            <pre className="mt-1 text-gray-400 whitespace-pre-wrap">{parsed.content}</pre>
          )}
        </div>
      );
    } catch {
      // Fall through to raw rendering below if JSON parsing ever fails
    }
  }

  if (actionType === "browser_action") {
    try {
      const parsed = JSON.parse(actionDetail);
      return (
        <div>
          <span className="text-blue-300">🌐 navigate → {parsed.url}</span>
          {parsed.click_selector && (
            <div className="text-gray-400 mt-1">🖱️ click → <code>{parsed.click_selector}</code></div>
          )}
        </div>
      );
    } catch {
      // Fall through to raw rendering below if JSON parsing ever fails
    }
  }

  return <>{actionDetail}</>;
}

export default function DashboardPage() {
  // --- Auth gate state ---
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [keyInput, setKeyInput] = useState("");

  useEffect(() => {
    const stored = sessionStorage.getItem("dashboard_api_key");
    if (stored) setApiKey(stored);
  }, []);

  const handleKeySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    sessionStorage.setItem("dashboard_api_key", keyInput);
    setApiKey(keyInput);
  };

  const handleAuthFailure = useCallback(() => {
    sessionStorage.removeItem("dashboard_api_key");
    setApiKey(null);
    setKeyInput("");
  }, []);

  // --- Sandbox state ---
  const [sandboxMode, setSandboxMode] = useState<boolean | null>(null);

  const fetchSandboxStatus = useCallback(async () => {
    if (!apiKey) return;
    try {
      const res = await fetch(`${API_BASE}/system/sandbox-status`, {
        headers: { "X-API-Key": apiKey },
      });
      if (res.status === 401) {
        handleAuthFailure();
        return;
      }
      if (res.ok) {
        const data = await res.json();
        setSandboxMode(data.sandbox_mode);
      }
    } catch (err) {
      console.error("Error fetching sandbox status:", err);
    }
  }, [apiKey, handleAuthFailure]);

  useEffect(() => {
    fetchSandboxStatus();
  }, [fetchSandboxStatus]);

  const [togglingSandbox, setTogglingSandbox] = useState(false);
  const [sandboxToggleError, setSandboxToggleError] = useState<string | null>(null);

  const handleToggleSandboxMode = async () => {
    if (sandboxMode === null || apiKey === null) return;
    const switchingToLive = sandboxMode === true; // currently sandbox -> would become live

    // Switching TO live mode is the dangerous direction — require an explicit
    // confirmation. Switching back to sandbox is always safe, no gate needed.
    if (switchingToLive) {
      const confirmed = window.confirm(
        "This will switch the system to LIVE MODE. Approved actions will run for real on this machine from now on. Are you sure?"
      );
      if (!confirmed) return;
    }

    setTogglingSandbox(true);
    setSandboxToggleError(null);

    try {
      const response = await fetch(`${API_BASE}/system/sandbox-mode`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify({ enabled: !sandboxMode }),
      });

      if (response.status === 401) {
        handleAuthFailure();
        return;
      }

      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || "Failed to switch mode.");
      }

      const data = await response.json();
      setSandboxMode(data.sandbox_mode);
    } catch (err: any) {
      setSandboxToggleError(err.message || "Failed to switch mode.");
    } finally {
      setTogglingSandbox(false);
    }
  };

  // --- Dashboard data state ---
  const [status, setStatus] = useState<DailyResearchStatus | null>(null);
  const [history, setHistory] = useState<DecisionHistoryItem[]>([]);
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([]);
  const [actionHistory, setActionHistory] = useState<PendingAction[]>([]);
  const [actionErrors, setActionErrors] = useState<Record<number, string>>({});
  const [executionResults, setExecutionResults] = useState<Record<number, ExecutionResult>>({});
  const [executingIds, setExecutingIds] = useState<Set<number>>(new Set());
  const [loadError, setLoadError] = useState<string | null>(null);
  const [expandedHistoryIds, setExpandedHistoryIds] = useState<Set<number>>(new Set());
  const [expandedActionHistoryIds, setExpandedActionHistoryIds] = useState<Set<number>>(new Set());

  const fetchPendingActions = useCallback(async (currentKey: string) => {
    try {
      const res = await fetch(`${API_BASE}/actions/pending`, {
        headers: {
          "X-API-Key": currentKey,
        },
      });

      if (res.status === 401) {
        handleAuthFailure();
        return;
      }

      if (!res.ok) {
        throw new Error("Could not fetch pending actions.");
      }

      const data: PendingAction[] = await res.json();

      // Defensive merge: never let an action that's already been approved or
      // executed on this screen silently vanish just because a re-fetch
      // happened to not include it (e.g. a backend still filtering strictly
      // on status = 'pending'). A card should only disappear because it was
      // rejected, never because a background refresh raced past its update.
      setPendingActions((prev) => {
        const fetchedIds = new Set(data.map((a) => a.id));
        const preserved = prev.filter(
          (a) =>
            !fetchedIds.has(a.id) &&
            a.status !== "pending" &&
            a.status !== "rejected"
        );
        return [...data, ...preserved];
      });
    } catch (err: any) {
      console.error("Error fetching pending actions:", err);
    }
  }, []);

  const fetchActionHistory = useCallback(async (currentKey: string) => {
    try {
      const res = await fetch(`${API_BASE}/actions/history?limit=20`, {
        headers: {
          "X-API-Key": currentKey,
        },
      });

      if (res.status === 401) {
        handleAuthFailure();
        return;
      }

      if (!res.ok) {
        throw new Error("Could not fetch action history.");
      }

      const data: PendingAction[] = await res.json();
      setActionHistory(data);
    } catch (err: any) {
      console.error("Error fetching action history:", err);
    }
  }, []);

  const fetchDashboardData = useCallback(async () => {
    try {
      const [statusRes, historyRes] = await Promise.all([
        fetch(`${API_BASE}/workflows/daily-research/status`, {
          headers: { "X-API-Key": apiKey || "" },
        }),
        fetch(`${API_BASE}/decisions/history?limit=20`, {
          headers: { "X-API-Key": apiKey || "" },
        }),
      ]);
      if (statusRes.status === 401 || historyRes.status === 401) {
        handleAuthFailure();
        return;
      }
      if (!statusRes.ok || !historyRes.ok) {
        throw new Error("Could not connect to the backend.");
      }
      setStatus(await statusRes.json());
      setHistory(await historyRes.json());
      setLoadError(null);
    } catch (err: any) {
      setLoadError(err.message || "Could not connect to the backend.");
    }
  }, [apiKey]);

  useEffect(() => {
    if (apiKey !== null) {
      fetchDashboardData();
      fetchPendingActions(apiKey);
      fetchActionHistory(apiKey);
    }
  }, [apiKey, fetchDashboardData, fetchPendingActions, fetchActionHistory]);

  const handleActionDecision = async (id: number, type: "approve" | "reject") => {
    if (type === "approve") {
      // Optimistically update the status to 'approved' locally
      setPendingActions((prev) =>
        prev.map((act) => (act.id === id ? { ...act, status: "approved" } : act))
      );
    } else {
      // On reject, remove the card immediately
      setPendingActions((prev) => prev.filter((action) => action.id !== id));
    }

    setActionErrors((prev) => {
      const newErrors = { ...prev };
      delete newErrors[id];
      return newErrors;
    });

    try {
      const response = await fetch(`${API_BASE}/actions/${id}/${type}`, {
        method: "POST",
        headers: {
          "X-API-Key": apiKey || "",
        },
      });

      if (response.status === 401) {
        handleAuthFailure();
        return;
      }

      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || `Error while ${type === "approve" ? "approving" : "rejecting"}`);
      }

      if (apiKey) {
        fetchPendingActions(apiKey);
        fetchActionHistory(apiKey);
      }
    } catch (err: any) {
      if (apiKey) fetchPendingActions(apiKey);
      setActionErrors((prev) => ({
        ...prev,
        [id]: err.message || "An error occurred while processing this action.",
      }));
    }
  };

  const handleExecuteAction = async (action: PendingAction) => {
    // Confirmation dialog in Live Mode
    if (sandboxMode === false) {
      const confirmed = window.confirm(
        "This will run a real command on this machine. Are you sure?"
      );
      if (!confirmed) return;
    }

    setExecutingIds((prev) => new Set(prev).add(action.id));
    setActionErrors((prev) => {
      const copy = { ...prev };
      delete copy[action.id];
      return copy;
    });

    try {
      const response = await fetch(`${API_BASE}/actions/${action.id}/execute`, {
        method: "POST",
        headers: {
          "X-API-Key": apiKey || "",
        },
      });

      if (response.status === 401) {
        handleAuthFailure();
        return;
      }

      const data: ExecutionResult = await response.json();

      if (!response.ok) {
        throw new Error(data.error || "Execution failed.");
      }

      // Store the result to show it inline
      setExecutionResults((prev) => ({ ...prev, [action.id]: data }));

      // Update the visible status on the card
      const newStatus = data.mode === "dry_run" ? "executed_dry_run" : "executed";
      setPendingActions((prev) =>
        prev.map((act) => (act.id === action.id ? { ...act, status: newStatus } : act))
      );

      if (apiKey) fetchActionHistory(apiKey);
    } catch (err: any) {
      setActionErrors((prev) => ({
        ...prev,
        [action.id]: err.message || "Error while executing action.",
      }));
      if (apiKey) fetchActionHistory(apiKey);
    } finally {
      setExecutingIds((prev) => {
        const copy = new Set(prev);
        copy.delete(action.id);
        return copy;
      });
    }
  };

  const toggleHistoryExpand = (id: number) => {
    setExpandedHistoryIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleActionHistoryExpand = (id: number) => {
    setExpandedActionHistoryIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // --- Ad-hoc decision form state ---
  const [topic, setTopic] = useState("");
  const [taskDescription, setTaskDescription] = useState("");
  const [selectedAgents, setSelectedAgents] = useState<string[]>(["cfo", "ceo"]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DecisionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const toggleAgent = (key: string) => {
    setSelectedAgents((prev) =>
      prev.includes(key) ? prev.filter((a) => a !== key) : [...prev, key]
    );
  };

  const handleTriggerDecision = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!topic.trim() || !taskDescription.trim()) {
      setError("Please fill in both a topic and a task description.");
      return;
    }
    if (selectedAgents.length === 0) {
      setError("Select at least 1 agent.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(`${API_BASE}/decisions/trigger`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey || "",
        },
        body: JSON.stringify({
          topic,
          task_description: taskDescription,
          agent_keys: selectedAgents,
        }),
      });

      if (response.status === 401) {
        handleAuthFailure();
        setError("Invalid key — please try again.");
        return;
      }

      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || `Error: ${response.statusText}`);
      }

      const data: DecisionResponse = await response.json();
      setResult(data);
      fetchDashboardData();
      if (apiKey) {
        fetchPendingActions(apiKey);
        fetchActionHistory(apiKey);
      }
    } catch (err: any) {
      setError(err.message || "An unknown error occurred.");
    } finally {
      setLoading(false);
    }
  };

  // --- Password gate screen ---
  if (apiKey === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <form
          onSubmit={handleKeySubmit}
          className="bg-gray-900 p-8 rounded-lg shadow space-y-4 w-full max-w-sm"
        >
          <h1 className="text-xl font-semibold text-white">Access Required</h1>
          <input
            type="password"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            placeholder="API Key"
            className="w-full rounded-md border border-gray-700 bg-gray-800 text-white p-2"
            autoFocus
          />
          <button
            type="submit"
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Confirm
          </button>
        </form>
      </div>
    );
  }

  // --- Main dashboard ---
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Persistent Banner top of page — now an interactive toggle */}
      {sandboxMode !== null && (
        <div
          className={`w-full border-b shadow-sm ${
            sandboxMode
              ? "bg-blue-950/80 border-blue-800"
              : "bg-red-900 border-red-700"
          }`}
        >
          <button
            onClick={handleToggleSandboxMode}
            disabled={togglingSandbox}
            className={`w-full py-2.5 px-4 text-center font-medium text-sm transition-colors ${
              sandboxMode ? "text-blue-200 hover:bg-blue-900/60" : "text-white font-bold hover:bg-red-950"
            } disabled:opacity-60 disabled:cursor-wait`}
            title="Click to switch modes"
          >
            {togglingSandbox
              ? "Switching mode..."
              : sandboxMode
              ? "🧪 SANDBOX MODE — executions are simulated, nothing real happens. (Click to switch to Live)"
              : "🔴 LIVE MODE — approved actions WILL run for real on this machine. (Click to switch to Sandbox)"}
          </button>
          {sandboxToggleError && (
            <p className="text-center text-xs text-red-300 pb-2">{sandboxToggleError}</p>
          )}
        </div>
      )}

      <div className="max-w-4xl mx-auto p-6 space-y-8">
        <div>
          <h1 className="text-3xl font-bold">AI Executive Team Dashboard</h1>
          <p className="text-gray-400 mt-1">
            Overview of autonomous decisions and daily research status.
          </p>
        </div>

        {loadError && (
          <div className="p-4 bg-red-950 border-l-4 border-red-500 text-red-300 rounded">
            {loadError}
          </div>
        )}

        {/* Daily research status card */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
          <div className="flex justify-between items-start">
            <h2 className="text-lg font-semibold">Daily Research Status</h2>
            {status && (
              <span
                className={`px-3 py-1 rounded-full text-sm font-medium ${
                  status.success === true
                    ? "bg-green-900 text-green-300"
                    : status.success === false
                    ? "bg-red-900 text-red-300"
                    : "bg-gray-800 text-gray-400"
                }`}
              >
                {status.success === true
                  ? "Successful"
                  : status.success === false
                  ? "Failed"
                  : "Not run yet"}
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
            <div>
              <p className="text-gray-500">Last run:</p>
              <p className="text-gray-200">
                {status?.last_run_time
                  ? new Date(status.last_run_time).toLocaleString("en-US")
                  : "Not run yet"}
              </p>
            </div>
            <div>
              <p className="text-gray-500">Message / Details:</p>
              <p className="text-gray-200">{status?.message || "No run yet."}</p>
            </div>
          </div>
        </div>

        {/* Pending Actions section */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">
              Actions Awaiting Approval ({pendingActions.length})
            </h2>
          </div>

          {pendingActions.length === 0 ? (
            <p className="text-gray-500 text-sm">No actions pending.</p>
          ) : (
            <div className="space-y-4">
              {pendingActions.map((action) => {
                const isApproved = action.status === "approved";
                const isExecuting = executingIds.has(action.id);
                const execResult = executionResults[action.id];

                return (
                  <div
                    key={action.id}
                    className="bg-gray-950 border border-gray-800 rounded-md p-4 space-y-3"
                  >
                    <div className="flex justify-between items-center">
                      <div className="flex items-center gap-2">
                        <span className="inline-block bg-blue-900/60 border border-blue-700 text-blue-300 text-xs font-semibold px-2.5 py-0.5 rounded uppercase tracking-wider">
                          {action.proposed_by}
                        </span>
                        {statusBadge(action.status)}
                      </div>
                      <span className="text-xs text-gray-500">
                        {new Date(action.timestamp).toLocaleString("en-US")}
                      </span>
                    </div>

                    <p className="text-sm text-gray-200">{action.action_description}</p>

                    <div className="bg-gray-900 border border-gray-800 rounded p-3 text-xs font-mono text-green-400 overflow-x-auto whitespace-pre-wrap">
                      {renderActionDetail(action.action_type, action.action_detail)}
                    </div>

                    {/* Error message for this action */}
                    {actionErrors[action.id] && (
                      <div className="p-2 bg-red-950/80 border border-red-800 text-red-300 text-xs rounded">
                        {actionErrors[action.id]}
                      </div>
                    )}

                    {/* Inline execution result */}
                    {execResult && (
                      <div className="p-3 bg-gray-900 border border-blue-900 rounded text-xs space-y-1">
                        <div className="font-semibold text-blue-400">
                          Execution Result ({execResult.mode}):
                        </div>
                        {execResult.detail && (
                          <p className="text-gray-300 font-mono">{execResult.detail}</p>
                        )}
                        {execResult.stdout && (
                          <div>
                            <span className="text-gray-500">stdout:</span>
                            <pre className="text-green-300 bg-black/40 p-1.5 rounded mt-0.5 overflow-x-auto">
                              {execResult.stdout}
                            </pre>
                          </div>
                        )}
                        {execResult.stderr && (
                          <div>
                            <span className="text-gray-500">stderr:</span>
                            <pre className="text-red-300 bg-black/40 p-1.5 rounded mt-0.5 overflow-x-auto">
                              {execResult.stderr}
                            </pre>
                          </div>
                        )}
                        {execResult.screenshot_path && (
                          <div>
                            <span className="text-gray-500">screenshot:</span>
                            <AuthenticatedScreenshot
                              filename={execResult.screenshot_path.split("/").pop()!}
                              apiKey={apiKey || ""}
                            />
                          </div>
                        )}
                      </div>
                    )}

                    <div className="flex gap-2 pt-1">
                      <button
                        onClick={() => handleActionDecision(action.id, "approve")}
                        className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-medium rounded transition-colors"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => handleActionDecision(action.id, "reject")}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-medium rounded transition-colors"
                      >
                        Reject
                      </button>
                      <button
                        onClick={() => handleExecuteAction(action)}
                        disabled={!isApproved || isExecuting}
                        title={!isApproved ? "Approve first" : "Execute action"}
                        className={`px-3 py-1.5 text-xs font-medium rounded transition-colors ${
                          isApproved && !isExecuting
                            ? "bg-purple-600 hover:bg-purple-700 text-white cursor-pointer"
                            : "bg-gray-800 text-gray-500 border border-gray-700 cursor-not-allowed opacity-60"
                        }`}
                      >
                        {isExecuting ? "Executing..." : "Execute"}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Ad-hoc decision trigger form */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold">Start New Ad-Hoc Decision</h2>

          {result && (
            <div className="border border-green-800 bg-green-950/40 rounded-md p-5 space-y-4">
              <div className="flex justify-between items-start">
                <h3 className="text-lg font-bold text-green-300">{result.topic}</h3>
                <span className="text-xs bg-gray-800 text-gray-400 rounded-full px-2 py-1">
                  ID: #{result.database_id}
                </span>
              </div>
              <p className="text-sm text-green-400">
                Participants: {result.participants.join(", ")}
              </p>

              <div>
                <h4 className="font-semibold text-gray-200 mb-1">Final Decision:</h4>
                <div className="bg-gray-950 rounded-md p-4 text-sm text-gray-200 whitespace-pre-wrap border border-gray-800">
                  {result.final_decision}
                </div>
              </div>

              {result.individual_outputs &&
                Object.keys(result.individual_outputs).length > 0 && (
                  <div className="pt-2 border-t border-gray-800 space-y-2">
                    <h4 className="font-semibold text-gray-200">
                      Individual Input Per Agent:
                    </h4>
                    {Object.entries(result.individual_outputs).map(
                      ([agentKey, outputText]) => (
                        <details
                          key={agentKey}
                          className="group border border-gray-800 rounded-md bg-gray-950 overflow-hidden"
                        >
                          <summary className="flex justify-between items-center p-3 font-medium cursor-pointer bg-gray-900 hover:bg-gray-800 text-gray-200 uppercase tracking-wide text-xs">
                            <span>{agentKey.replace("_", " ")}</span>
                            <span className="text-gray-500 group-open:rotate-180 transition-transform">
                              ▼
                            </span>
                          </summary>
                          <div className="p-4 text-sm text-gray-300 whitespace-pre-wrap border-t border-gray-800">
                            {outputText}
                          </div>
                        </details>
                      )
                    )}
                  </div>
                )}
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-950 border-l-4 border-red-500 text-red-300 text-sm rounded">
              {error}
            </div>
          )}

          <form onSubmit={handleTriggerDecision} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1">
                Topic
              </label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="E.g. Expansion into the German market"
                className="w-full rounded-md border border-gray-700 bg-gray-800 text-gray-100 p-2 placeholder-gray-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1">
                Task Description
              </label>
              <textarea
                value={taskDescription}
                onChange={(e) => setTaskDescription(e.target.value)}
                rows={3}
                placeholder="Provide a detailed explanation of the situation and question..."
                className="w-full rounded-md border border-gray-700 bg-gray-800 text-gray-100 p-2 placeholder-gray-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Participating Agents
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {AGENT_OPTIONS.map((agent) => (
                  <label
                    key={agent.key}
                    className="flex items-center gap-2 text-sm text-gray-300"
                  >
                    <input
                      type="checkbox"
                      checked={selectedAgents.includes(agent.key)}
                      onChange={() => toggleAgent(agent.key)}
                      className="rounded border-gray-600 bg-gray-800"
                    />
                    {agent.label}
                  </label>
                ))}
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full sm:w-auto px-5 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Meeting in progress... this can take a few minutes" : "Start Decision"}
            </button>
          </form>
        </div>

        {/* Decision history */}
        <div>
          <h2 className="text-xl font-bold mb-4">Decision History</h2>
          <div className="space-y-4">
            {history.length === 0 && (
              <p className="text-gray-500 text-sm">No decisions found yet.</p>
            )}
            {history.map((item) => {
              const isExpanded = expandedHistoryIds.has(item.id);
              const preview =
                item.decision_outcome.length > 150
                  ? item.decision_outcome.slice(0, 150) + "..."
                  : item.decision_outcome;

              return (
                <div
                  key={item.id}
                  className="bg-gray-900 border border-gray-800 rounded-lg p-5"
                >
                  <div className="flex justify-between items-start">
                    <h3 className="text-blue-400 font-bold text-lg">{item.topic}</h3>
                    <span className="text-xs text-gray-500">
                      {new Date(item.timestamp).toLocaleString("en-US")}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mt-2">
                    Participants:{" "}
                    {item.agents_involved.split(",").map((a) => (
                      <span
                        key={a}
                        className="inline-block bg-gray-800 border border-gray-700 text-blue-300 text-xs px-2 py-0.5 rounded ml-1"
                      >
                        {a.trim().toUpperCase()}
                      </span>
                    ))}
                  </p>
                  <p className="text-sm text-gray-300 mt-3 whitespace-pre-wrap">
                    {isExpanded ? item.decision_outcome : preview}
                  </p>
                  {item.decision_outcome.length > 150 && (
                    <button
                      onClick={() => toggleHistoryExpand(item.id)}
                      className="text-blue-400 text-sm mt-2 hover:underline"
                    >
                      {isExpanded ? "▲ Show less" : "▼ Show more"}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Action history — full audit trail across every status, unlike
            Pending Actions above, which only shows still-actionable items */}
        <div>
          <h2 className="text-xl font-bold mb-4">Action History</h2>
          <div className="space-y-4">
            {actionHistory.length === 0 && (
              <p className="text-gray-500 text-sm">No actions found yet.</p>
            )}
            {actionHistory.map((item) => {
              const isExpanded = expandedActionHistoryIds.has(item.id);
              const preview =
                item.action_detail.length > 150
                  ? item.action_detail.slice(0, 150) + "..."
                  : item.action_detail;

              return (
                <div
                  key={item.id}
                  className="bg-gray-900 border border-gray-800 rounded-lg p-5"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex items-center gap-2">
                      <span className="inline-block bg-blue-900/60 border border-blue-700 text-blue-300 text-xs font-semibold px-2.5 py-0.5 rounded uppercase tracking-wider">
                        {item.proposed_by}
                      </span>
                      {statusBadge(item.status)}
                    </div>
                    <span className="text-xs text-gray-500">
                      {new Date(item.timestamp).toLocaleString("en-US")}
                    </span>
                  </div>
                  <p className="text-sm text-gray-300 mt-3">{item.action_description}</p>
                  <div className="bg-gray-950 border border-gray-800 rounded p-3 mt-2 text-xs font-mono text-green-400 overflow-x-auto whitespace-pre-wrap">
                    {item.action_type === "file_operation" || item.action_type === "browser_action"
                      ? renderActionDetail(item.action_type, item.action_detail)
                      : isExpanded ? item.action_detail : preview}
                  </div>
                  {item.action_type !== "file_operation" && item.action_type !== "browser_action" && item.action_detail.length > 150 && (
                    <button
                      onClick={() => toggleActionHistoryExpand(item.id)}
                      className="text-blue-400 text-sm mt-2 hover:underline"
                    >
                      {isExpanded ? "▲ Show less" : "▼ Show more"}
                    </button>
                  )}
                  {item.result_detail && (() => {
                    try {
                      const parsedResult = JSON.parse(item.result_detail);
                      return (
                        <div className={`mt-3 p-3 bg-gray-950 border rounded text-xs space-y-1 ${parsedResult.error ? "border-red-900" : "border-blue-900"}`}>
                          <div className={`font-semibold ${parsedResult.error ? "text-red-400" : "text-blue-400"}`}>
                            {parsedResult.error ? "Failure Reason:" : "Result:"}
                          </div>
                          {parsedResult.error && (
                            <pre className="text-red-300 whitespace-pre-wrap overflow-x-auto">{parsedResult.error}</pre>
                          )}
                          {parsedResult.stdout && (
                            <pre className="text-green-300 whitespace-pre-wrap overflow-x-auto">{parsedResult.stdout}</pre>
                          )}
                          {parsedResult.stderr && (
                            <pre className="text-red-300 whitespace-pre-wrap overflow-x-auto">{parsedResult.stderr}</pre>
                          )}
                          {parsedResult.screenshot_path && (
                            <AuthenticatedScreenshot
                              filename={parsedResult.screenshot_path.split("/").pop()}
                              apiKey={apiKey || ""}
                            />
                          )}
                        </div>
                      );
                    } catch {
                      return null;
                    }
                  })()}
                  {item.reviewed_at && (
                    <p className="text-xs text-gray-600 mt-2">
                      Reviewed: {new Date(item.reviewed_at).toLocaleString("en-US")}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
