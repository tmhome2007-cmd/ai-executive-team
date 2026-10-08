"use client";

import { useState, useEffect, useCallback } from "react";
import VirtualOffice from "./components/virtual-office";
import AgileBoard from "./components/agile-board";
import CompanyRecords, { type ExecutiveProfile } from "./components/company-records";

const API_BASE = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");

const errorMessage = (error: unknown): string => error instanceof Error ? error.message : "";

const VIEWS = [
  ["overview", "Overview"], ["boards", "Agile boards"], ["office", "Virtual office"], ["records", "Conversations & activity"], ["goals", "Goals"], ["treasury", "Treasury"],
  ["decisions", "Decisions"], ["resources", "Resources"], ["actions", "Actions & results"],
  ["activity", "Executive activity"], ["system", "System health"],
] as const;
type DashboardView = typeof VIEWS[number][0];
interface SystemHealth {
  status: string;
  uptime_seconds: number;
  components: Record<string, { ok: boolean; message: string }>;
}

// Model text stays React text: headings and lists never execute HTML or links.
function Report({ text }: { text: string }) {
  const inline = (line: string) => line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**")
      ? <strong key={i}>{part.slice(2, -2)}</strong> : part);
  return <div className="report">{text.split(/\r?\n/).map((line, i) => {
    if (!line.trim()) return null;
    if (/^\s*#{1,6}\s/.test(line)) return <h4 key={i}>{inline(line.replace(/^\s*#{1,6}\s+/, ""))}</h4>;
    if (/^\s*[-*+]\s+/.test(line)) return <ul key={i}><li>{inline(line.replace(/^\s*[-*+]\s+/, ""))}</li></ul>;
    return <p key={i}>{inline(line)}</p>;
  })}</div>;
}

// --- Types ---

interface DecisionHistoryItem {
  id: number;
  meeting_type?: string;
  timestamp: string;
  topic: string;
  agents_involved: string;
  task_description: string;
  decision_outcome: string;
  sandbox_mode: number;
  approval_status?: "pending" | "approved" | "rejected";
  approval_reviewed_at?: string | null;
  preparation_status?: "not_started" | "in_progress" | "completed" | "failed";
  prepared_at?: string | null;
  preparation_outcome?: string | null;
  linked_action_count?: number;
  linked_resource_request_count?: number;
  goal_id?: number | null;
  goal_sync_uuid?: string | null;
  goal_title?: string | null;
  goal_status?: string | null;
}

interface MeetingTypeProfile {
  label: string;
  default_agents: string[];
  required_agents: string[];
  evidence_focus: string;
  output_contract: string;
  approval_posture: string;
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
  meeting_type: string;
  goal_id?: number | null;
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
  expected_outcome?: string | null;
  expected_impact?: string | null;
  expected_cost_amount?: number | null;
  currency?: string | null;
  outcome_status?: string | null;
  actual_outcome?: string | null;
  actual_impact?: string | null;
  actual_cost_amount?: number | null;
  measured_at?: string | null;
  next_recommendation?: string | null;
  outcome_notes?: string | null;
  source_decision_id?: number | null;
  source_decision_sync_uuid?: string | null;
  source_decision_topic?: string | null;
  source_phase?: string | null;
  source_goal_id?: number | null;
  source_goal_title?: string | null;
}

interface ResourceRequest {
  id: number;
  timestamp: string;
  requested_by: string;
  resource_type: string;
  resource_name: string;
  reason: string;
  required_for?: string | null;
  amount?: number | null;
  currency?: string | null;
  status: string;
  reviewed_at?: string | null;
  fulfilled_at?: string | null;
  fulfillment_note?: string | null;
  source_decision_id?: number | null;
  source_decision_sync_uuid?: string | null;
  source_decision_topic?: string | null;
  source_phase?: string | null;
  source_goal_id?: number | null;
  source_goal_title?: string | null;
}

interface CompanyGoal {
  id: number;
  created_at: string;
  updated_at: string;
  title: string;
  description: string;
  success_criteria: string;
  priority: "critical" | "high" | "medium" | "low";
  target_date?: string | null;
  status: "draft" | "active" | "paused" | "completed" | "abandoned";
  completed_at?: string | null;
  completion_note?: string | null;
  sync_uuid: string;
  linked_decision_count?: number;
  linked_action_count?: number;
  measured_outcome_count?: number;
}

interface GoalLineage {
  goal: CompanyGoal;
  decision_count: number;
  outcome_counts: Record<string, number>;
  spend_by_currency: Record<string, number>;
  decisions: DecisionLineage[];
}

interface TreasuryLineageEntry {
  id: number;
  timestamp: string;
  entry_type: string;
  amount: number;
  currency: string;
  note?: string | null;
  source_action_id?: number | null;
}

interface TreasuryLineageReservation {
  id: number;
  timestamp: string;
  amount: number;
  currency: string;
  status: string;
  source_action_id?: number | null;
}

interface DecisionLineage {
  decision: DecisionHistoryItem;
  actions: PendingAction[];
  resource_requests: ResourceRequest[];
  treasury?: {
    entries: TreasuryLineageEntry[];
    reservations: TreasuryLineageReservation[];
  };
}

interface TreasuryCurrencySummary {
  cash_balance: number;
  reserved: number;
  available: number;
}

interface TreasurySummary {
  currencies: Record<string, TreasuryCurrencySummary>;
}

interface FollowupEvent {
  id: number;
  created_at: string;
  updated_at: string;
  event_type: string;
  status: "open" | "resolved" | "dismissed";
  severity: "info" | "attention" | "critical";
  reason: string;
  fingerprint: string;
  goal_id?: number | null;
  goal_title?: string | null;
  source_action_id?: number | null;
  source_decision_id?: number | null;
  source_decision_topic?: string | null;
  generated_decision_id?: number | null;
  generated_decision_topic?: string | null;
}

interface FollowupStatus {
  last_run_time: string | null;
  success: boolean | null;
  scanned_goal_count: number;
  created_event_ids: number[];
  generated_decision_ids: number[];
  resolved_event_ids: number[];
  errors: string[];
  message: string;
}

interface ExecutiveMemory {
  id: number;
  created_at: string;
  updated_at: string;
  executive_key: string;
  memory_kind: string;
  lesson: string;
  supporting_evidence?: string | null;
  confidence: number;
  is_active: number;
  source_goal_id?: number | null;
  source_decision_id?: number | null;
  source_action_id?: number | null;
  fingerprint: string;
  sync_uuid: string;
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
  { key: "cco", label: "CCO" },
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

function OutcomeEditor({
  action,
  apiKey,
  onSaved,
}: {
  action: PendingAction;
  apiKey: string;
  onSaved: () => void;
}) {
  const [status, setStatus] = useState(
    ["succeeded", "failed", "partial", "inconclusive"].includes(action.outcome_status || "")
      ? action.outcome_status || ""
      : ""
  );
  const [actualOutcome, setActualOutcome] = useState(action.actual_outcome || "");
  const [actualImpact, setActualImpact] = useState(action.actual_impact || "");
  const [actualCost, setActualCost] = useState(
    action.actual_cost_amount !== null && action.actual_cost_amount !== undefined
      ? String(action.actual_cost_amount)
      : ""
  );
  const [currency, setCurrency] = useState(action.currency || "");
  const [nextRecommendation, setNextRecommendation] = useState(action.next_recommendation || "");
  const [notes, setNotes] = useState(action.outcome_notes || "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const canRecordActual = ["executed", "execution_failed", "blocked_dangerous"].includes(action.status);

  const save = async () => {
    if (!canRecordActual) return;
    if (!status || !actualOutcome.trim()) {
      setMessage("Choose an outcome status and describe the actual outcome.");
      return;
    }
    if (actualCost && !currency.trim()) {
      setMessage("Currency is required when actual cost is entered.");
      return;
    }

    setSaving(true);
    setMessage(null);
    try {
      const payload: Record<string, unknown> = {
        outcome_status: status,
        actual_outcome: actualOutcome.trim(),
      };
      if (actualImpact.trim()) payload.actual_impact = actualImpact.trim();
      if (actualCost.trim()) payload.actual_cost_amount = Number(actualCost);
      if (currency.trim()) payload.currency = currency.trim().toUpperCase();
      if (nextRecommendation.trim()) payload.next_recommendation = nextRecommendation.trim();
      if (notes.trim()) payload.notes = notes.trim();

      const response = await fetch(`${API_BASE}/actions/${action.id}/outcome`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || "Could not save outcome.");

      setMessage("Outcome saved.");
      onSaved();
    } catch (err: unknown) {
      setMessage(errorMessage(err) || "Could not save outcome.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mt-4 border border-cyan-900 bg-gray-950 rounded p-4 space-y-3">
      <div className="flex justify-between items-center gap-3">
        <h4 className="font-semibold text-cyan-300">Outcome Tracking</h4>
        <span className="text-xs border border-cyan-800 text-cyan-300 rounded px-2 py-0.5">
          {action.outcome_status || "not_started"}
        </span>
      </div>

      <div className="grid sm:grid-cols-2 gap-3 text-xs">
        <div>
          <div className="text-gray-500">Expected outcome</div>
          <div className="text-gray-300 whitespace-pre-wrap">
            {action.expected_outcome || "Not specified"}
          </div>
        </div>
        <div>
          <div className="text-gray-500">Expected impact</div>
          <div className="text-gray-300 whitespace-pre-wrap">
            {action.expected_impact || "Not specified"}
          </div>
        </div>
        <div>
          <div className="text-gray-500">Expected cost</div>
          <div className="text-gray-300">
            {action.expected_cost_amount !== null && action.expected_cost_amount !== undefined
              ? `${action.expected_cost_amount} ${action.currency || ""}`.trim()
              : "Unknown / not specified"}
          </div>
        </div>
        <div>
          <div className="text-gray-500">Measured at</div>
          <div className="text-gray-300">
            {action.measured_at ? new Date(action.measured_at).toLocaleString("en-US") : "Not measured yet"}
          </div>
        </div>
      </div>

      {action.actual_outcome && (
        <div className="text-xs space-y-1 border-t border-gray-800 pt-3">
          <div><span className="text-gray-500">Actual outcome:</span> <span className="text-gray-300">{action.actual_outcome}</span></div>
          {action.actual_impact && <div><span className="text-gray-500">Actual impact:</span> <span className="text-gray-300">{action.actual_impact}</span></div>}
          {action.actual_cost_amount !== null && action.actual_cost_amount !== undefined && (
            <div><span className="text-gray-500">Actual cost:</span> <span className="text-gray-300">{action.actual_cost_amount} {action.currency || ""}</span></div>
          )}
          {action.next_recommendation && <div><span className="text-gray-500">Next recommendation:</span> <span className="text-gray-300">{action.next_recommendation}</span></div>}
        </div>
      )}

      {canRecordActual && (
        <details>
          <summary className="cursor-pointer text-sm text-cyan-400">
            Record / update measured outcome
          </summary>
          <div className="mt-3 grid gap-2">
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="bg-gray-900 border border-gray-700 rounded p-2 text-sm"
            >
              <option value="">Choose outcome status</option>
              <option value="succeeded">Succeeded</option>
              <option value="failed">Failed</option>
              <option value="partial">Partial</option>
              <option value="inconclusive">Inconclusive</option>
            </select>
            <textarea
              value={actualOutcome}
              onChange={(e) => setActualOutcome(e.target.value)}
              placeholder="What actually happened?"
              rows={2}
              className="bg-gray-900 border border-gray-700 rounded p-2 text-sm"
            />
            <textarea
              value={actualImpact}
              onChange={(e) => setActualImpact(e.target.value)}
              placeholder="What impact did it actually have? (optional)"
              rows={2}
              className="bg-gray-900 border border-gray-700 rounded p-2 text-sm"
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                min="0"
                step="0.01"
                value={actualCost}
                onChange={(e) => setActualCost(e.target.value)}
                placeholder="Actual cost"
                className="bg-gray-900 border border-gray-700 rounded p-2 text-sm"
              />
              <input
                value={currency}
                onChange={(e) => setCurrency(e.target.value)}
                placeholder="Currency (EUR)"
                maxLength={3}
                className="bg-gray-900 border border-gray-700 rounded p-2 text-sm uppercase"
              />
            </div>
            <textarea
              value={nextRecommendation}
              onChange={(e) => setNextRecommendation(e.target.value)}
              placeholder="What should the team do next? (optional)"
              rows={2}
              className="bg-gray-900 border border-gray-700 rounded p-2 text-sm"
            />
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Measurement notes / evidence (optional)"
              rows={2}
              className="bg-gray-900 border border-gray-700 rounded p-2 text-sm"
            />
            {message && <p className="text-xs text-gray-300">{message}</p>}
            <button
              type="button"
              onClick={save}
              disabled={saving}
              className="w-fit px-3 py-1.5 bg-cyan-700 hover:bg-cyan-600 rounded text-xs text-white disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save Outcome"}
            </button>
          </div>
        </details>
      )}

      {action.status === "executed_dry_run" && (
        <p className="text-xs text-purple-300">
          Dry-run only: no real-world business outcome can be measured from this execution.
        </p>
      )}
    </div>
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
  const [view, setView] = useState<DashboardView>("overview");
  const [profiles, setProfiles] = useState<Record<string, ExecutiveProfile>>({});
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [sectionErrors, setSectionErrors] = useState<Record<string, string>>({});
  const [loadedSections, setLoadedSections] = useState<Record<string, boolean>>({});
  // --- Auth gate state ---
  const [apiKey, setApiKey] = useState<string | null>(null);
  const [keyInput, setKeyInput] = useState("");

  // Keep the privileged control-plane API key in memory only. Persisting it
  // in browser persistence would let any future XSS or compromised
  // browser-side dependency read a credential that can authorize real-world
  // actions. A refresh intentionally requires re-entry.
  const handleKeySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setApiKey(keyInput);
    setKeyInput("");
  };

  const handleAuthFailure = useCallback(() => {
    setApiKey(null);
    setKeyInput("");
    setLoadedSections({});
    setHealth(null);
    setProfiles({});
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
    } catch (err: unknown) {
      setSandboxToggleError(errorMessage(err) || "Failed to switch mode.");
    } finally {
      setTogglingSandbox(false);
    }
  };

  // --- Dashboard data state ---
  const [status, setStatus] = useState<DailyResearchStatus | null>(null);
  const [history, setHistory] = useState<DecisionHistoryItem[]>([]);
  const [pendingActions, setPendingActions] = useState<PendingAction[]>([]);
  const [actionHistory, setActionHistory] = useState<PendingAction[]>([]);
  const [resourceRequests, setResourceRequests] = useState<ResourceRequest[]>([]);
  const [resourceErrors, setResourceErrors] = useState<Record<number, string>>({});
  const [goals, setGoals] = useState<CompanyGoal[]>([]);
  const [followups, setFollowups] = useState<FollowupEvent[]>([]);
  const [followupStatus, setFollowupStatus] = useState<FollowupStatus | null>(null);
  const [followupError, setFollowupError] = useState<string | null>(null);
  const [runningFollowup, setRunningFollowup] = useState(false);
  const [memoryExecutive, setMemoryExecutive] = useState("ceo");
  const [executiveMemories, setExecutiveMemories] = useState<ExecutiveMemory[]>([]);
  const [memoryError, setMemoryError] = useState<string | null>(null);
  const [goalError, setGoalError] = useState<string | null>(null);
  const [goalLineage, setGoalLineage] = useState<Record<number, GoalLineage>>({});
  const [goalTitle, setGoalTitle] = useState("");
  const [goalDescription, setGoalDescription] = useState("");
  const [goalSuccessCriteria, setGoalSuccessCriteria] = useState("");
  const [goalPriority, setGoalPriority] = useState<CompanyGoal["priority"]>("medium");
  const [goalTargetDate, setGoalTargetDate] = useState("");
  const [goalStartActive, setGoalStartActive] = useState(true);
  const [creatingGoal, setCreatingGoal] = useState(false);
  const [treasury, setTreasury] = useState<TreasurySummary>({ currencies: {} });
  const [fundAmount, setFundAmount] = useState("");
  const [fundCurrency, setFundCurrency] = useState("");
  const [fundNote, setFundNote] = useState("");
  const [fundingTreasury, setFundingTreasury] = useState(false);
  const [treasuryMessage, setTreasuryMessage] = useState<string | null>(null);
  const [actionErrors, setActionErrors] = useState<Record<number, string>>({});
  const [executionResults, setExecutionResults] = useState<Record<number, ExecutionResult>>({});
  const [executingIds, setExecutingIds] = useState<Set<number>>(new Set());
  const [loadError, setLoadError] = useState<string | null>(null);
  const [expandedHistoryIds, setExpandedHistoryIds] = useState<Set<number>>(new Set());
  const [expandedActionHistoryIds, setExpandedActionHistoryIds] = useState<Set<number>>(new Set());
  const [decisionErrors, setDecisionErrors] = useState<Record<number, string>>({});
  const [preparingDecisionIds, setPreparingDecisionIds] = useState<Set<number>>(new Set());
  const [preparationResults, setPreparationResults] = useState<Record<number, string>>({});
  const [lineageResults, setLineageResults] = useState<Record<number, DecisionLineage>>({});
  const [loadingLineageIds, setLoadingLineageIds] = useState<Set<number>>(new Set());

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

      // Backend returns all active states: pending, approved, executing.
      // Terminal actions belong only in Action History.
      setPendingActions(data);
      setLoadedSections((prev) => ({ ...prev, pendingActions: true }));
      setSectionErrors((prev) => ({ ...prev, pendingActions: "" }));
    } catch (err: unknown) {
      setSectionErrors((prev) => ({ ...prev, pendingActions: errorMessage(err) || "Could not load pending actions." }));
    }
  }, [handleAuthFailure]);

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
      setLoadedSections((prev) => ({ ...prev, actionHistory: true }));
      setSectionErrors((prev) => ({ ...prev, actionHistory: "" }));
    } catch (err: unknown) {
      setSectionErrors((prev) => ({ ...prev, actionHistory: errorMessage(err) || "Could not load action history." }));
    }
  }, [handleAuthFailure]);

  const fetchResourceRequests = useCallback(async (currentKey: string) => {
    try {
      const res = await fetch(`${API_BASE}/resources/pending`, {
        headers: { "X-API-Key": currentKey },
      });
      if (res.status === 401) {
        handleAuthFailure();
        return;
      }
      if (!res.ok) throw new Error("Could not fetch resource requests.");
      setResourceRequests(await res.json());
      setLoadedSections((prev) => ({ ...prev, resources: true }));
      setSectionErrors((prev) => ({ ...prev, resources: "" }));
    } catch (err) {
      setSectionErrors((prev) => ({ ...prev, resources: errorMessage(err) || "Could not load resource requests." }));
    }
  }, [handleAuthFailure]);

  const fetchTreasury = useCallback(async (currentKey: string) => {
    try {
      const res = await fetch(`${API_BASE}/treasury/summary`, {
        headers: { "X-API-Key": currentKey },
      });
      if (res.status === 401) {
        handleAuthFailure();
        return;
      }
      if (!res.ok) throw new Error("Could not fetch treasury.");
      setTreasury(await res.json());
      setLoadedSections((prev) => ({ ...prev, treasury: true }));
      setSectionErrors((prev) => ({ ...prev, treasury: "" }));
    } catch (err) {
      setSectionErrors((prev) => ({ ...prev, treasury: errorMessage(err) || "Could not load treasury." }));
    }
  }, [handleAuthFailure]);

  const handleFundTreasury = async () => {
    if (!apiKey) return;
    const amount = Number(fundAmount);
    if (!Number.isFinite(amount) || amount <= 0) {
      setTreasuryMessage("Enter an amount greater than zero.");
      return;
    }
    if (!/^[A-Za-z]{3}$/.test(fundCurrency.trim())) {
      setTreasuryMessage("Enter a 3-letter currency code such as EUR or USD.");
      return;
    }

    setFundingTreasury(true);
    setTreasuryMessage(null);
    try {
      const res = await fetch(`${API_BASE}/treasury/fund`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify({
          amount,
          currency: fundCurrency.trim().toUpperCase(),
          note: fundNote.trim() || null,
        }),
      });
      if (res.status === 401) {
        handleAuthFailure();
        return;
      }
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "Could not add treasury funding.");

      setFundAmount("");
      setFundNote("");
      setTreasuryMessage("Funding recorded.");
      await fetchTreasury(apiKey);
    } catch (err: unknown) {
      setTreasuryMessage(errorMessage(err) || "Could not add treasury funding.");
    } finally {
      setFundingTreasury(false);
    }
  };

  const fetchFollowups = useCallback(async (currentKey: string) => {
    try {
      const [itemsRes, statusRes] = await Promise.all([
        fetch(`${API_BASE}/followups/open?limit=100`, {
          headers: { "X-API-Key": currentKey },
        }),
        fetch(`${API_BASE}/workflows/autonomous-followup/status`, {
          headers: { "X-API-Key": currentKey },
        }),
      ]);
      if (itemsRes.status === 401 || statusRes.status === 401) {
        handleAuthFailure();
        return;
      }
      if (!itemsRes.ok || !statusRes.ok) {
        throw new Error("Could not fetch autonomous follow-up state.");
      }
      setFollowups(await itemsRes.json());
      setLoadedSections((prev) => ({ ...prev, followups: true }));
      setFollowupStatus(await statusRes.json());
      setFollowupError(null);
    } catch (err: unknown) {
      setFollowupError(errorMessage(err) || "Could not fetch autonomous follow-up state.");
    }
  }, [handleAuthFailure]);

  const handleRunFollowup = async () => {
    if (!apiKey) return;
    setRunningFollowup(true);
    setFollowupError(null);
    try {
      const res = await fetch(`${API_BASE}/workflows/autonomous-followup/trigger`, {
        method: "POST",
        headers: { "X-API-Key": apiKey },
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "Autonomous follow-up scan failed.");
      await Promise.all([
        fetchFollowups(apiKey),
        fetchDashboardData(),
        fetchGoals(apiKey),
      ]);
    } catch (err: unknown) {
      setFollowupError(errorMessage(err) || "Autonomous follow-up scan failed.");
    } finally {
      setRunningFollowup(false);
    }
  };

  const handleFollowupDecision = async (id: number, action: "resolve" | "dismiss") => {
    if (!apiKey) return;
    try {
      const res = await fetch(`${API_BASE}/followups/${id}/${action}`, {
        method: "POST",
        headers: { "X-API-Key": apiKey },
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || `Could not ${action} follow-up.`);
      await fetchFollowups(apiKey);
    } catch (err: unknown) {
      setFollowupError(errorMessage(err) || `Could not ${action} follow-up.`);
    }
  };

  const fetchExecutiveMemories = useCallback(async (
    currentKey: string,
    executiveKey: string = memoryExecutive
  ) => {
    try {
      const res = await fetch(`${API_BASE}/memory/${executiveKey}?active_only=true&limit=20`, {
        headers: { "X-API-Key": currentKey },
      });
      if (res.status === 401) {
        handleAuthFailure();
        return;
      }
      if (!res.ok) throw new Error("Could not fetch executive memory.");
      setExecutiveMemories(await res.json());
      setMemoryError(null);
    } catch (err: unknown) {
      setMemoryError(errorMessage(err) || "Could not fetch executive memory.");
    }
  }, [handleAuthFailure, memoryExecutive]);

  const handleMemoryStatus = async (memoryId: number, active: boolean) => {
    if (!apiKey) return;
    try {
      const res = await fetch(`${API_BASE}/memory/${memoryId}/status`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify({ active }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "Could not update executive memory.");
      await fetchExecutiveMemories(apiKey, memoryExecutive);
    } catch (err: unknown) {
      setMemoryError(errorMessage(err) || "Could not update executive memory.");
    }
  };

  const fetchGoals = useCallback(async (currentKey: string) => {
    try {
      const res = await fetch(`${API_BASE}/goals?limit=100`, {
        headers: { "X-API-Key": currentKey },
      });
      if (res.status === 401) {
        handleAuthFailure();
        return;
      }
      if (!res.ok) throw new Error("Could not fetch company goals.");
      setGoals(await res.json());
      setLoadedSections((prev) => ({ ...prev, goals: true }));
    } catch (err: unknown) {
      setGoalError(errorMessage(err) || "Could not fetch company goals.");
    }
  }, [handleAuthFailure]);

  const handleCreateGoal = async () => {
    if (!apiKey) return;
    if (!goalTitle.trim() || !goalDescription.trim() || !goalSuccessCriteria.trim()) {
      setGoalError("Title, mission description, and success criteria are required.");
      return;
    }
    setCreatingGoal(true);
    setGoalError(null);
    try {
      const res = await fetch(`${API_BASE}/goals`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify({
          title: goalTitle.trim(),
          description: goalDescription.trim(),
          success_criteria: goalSuccessCriteria.trim(),
          priority: goalPriority,
          target_date: goalTargetDate || null,
          status: goalStartActive ? "active" : "draft",
        }),
      });
      const data = await res.json().catch(() => null);
      if (res.status === 401) {
        handleAuthFailure();
        return;
      }
      if (!res.ok) throw new Error(data?.detail || "Could not create company goal.");
      setGoalTitle("");
      setGoalDescription("");
      setGoalSuccessCriteria("");
      setGoalTargetDate("");
      await fetchGoals(apiKey);
    } catch (err: unknown) {
      setGoalError(errorMessage(err) || "Could not create company goal.");
    } finally {
      setCreatingGoal(false);
    }
  };

  const handleGoalStatus = async (
    goal: CompanyGoal,
    status: "active" | "paused" | "completed" | "abandoned"
  ) => {
    if (!apiKey) return;
    let completionNote: string | null = null;
    if (status === "completed" || status === "abandoned") {
      completionNote = window.prompt(
        status === "completed"
          ? "Record the evidence/reason this goal is complete."
          : "Record why this goal is being abandoned."
      );
      if (!completionNote?.trim()) return;
    }
    setGoalError(null);
    try {
      const res = await fetch(`${API_BASE}/goals/${goal.id}/status`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify({ status, completion_note: completionNote }),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "Could not update goal status.");
      await fetchGoals(apiKey);
      await fetchDashboardData();
    } catch (err: unknown) {
      setGoalError(errorMessage(err) || "Could not update goal status.");
    }
  };

  const handleGoalLineage = async (goalId: number) => {
    if (!apiKey) return;
    if (goalLineage[goalId]) {
      setGoalLineage((prev) => {
        const next = { ...prev };
        delete next[goalId];
        return next;
      });
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/goals/${goalId}/lineage`, {
        headers: { "X-API-Key": apiKey },
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) throw new Error(data?.detail || "Could not load goal lineage.");
      setGoalLineage((prev) => ({ ...prev, [goalId]: data }));
    } catch (err: unknown) {
      setGoalError(errorMessage(err) || "Could not load goal lineage.");
    }
  };

  const fetchMeetingTypes = useCallback(async (currentKey: string) => {
    try {
      const res = await fetch(`${API_BASE}/meeting-types`, {
        headers: { "X-API-Key": currentKey },
      });
      if (res.status === 401) {
        handleAuthFailure();
        return;
      }
      if (!res.ok) throw new Error("Could not fetch meeting types.");
      setMeetingTypes(await res.json());
    } catch (err: unknown) {
      setLoadError(errorMessage(err) || "Could not fetch meeting types.");
    }
  }, [handleAuthFailure]);

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
      setLoadedSections((prev) => ({ ...prev, decisions: true }));
      setLoadError(null);
    } catch (err: unknown) {
      setLoadError(errorMessage(err) || "Could not connect to the backend.");
    }
  }, [apiKey, handleAuthFailure]);

  useEffect(() => {
    if (apiKey !== null) {
      fetchDashboardData();
      fetchPendingActions(apiKey);
      fetchActionHistory(apiKey);
      fetchResourceRequests(apiKey);
      fetchTreasury(apiKey);
      fetchGoals(apiKey);
      fetchFollowups(apiKey);
      fetchExecutiveMemories(apiKey, memoryExecutive);
      fetchMeetingTypes(apiKey);
    }
  }, [apiKey, fetchDashboardData, fetchPendingActions, fetchActionHistory, fetchResourceRequests, fetchTreasury, fetchGoals, fetchFollowups, fetchExecutiveMemories, fetchMeetingTypes, memoryExecutive]);

  const refreshHealth = useCallback(async (currentKey: string) => {
    try {
      const response = await fetch(`${API_BASE}/system/health`, { headers: { "X-API-Key": currentKey } });
      if (response.status === 401) { handleAuthFailure(); return; }
      if (!response.ok) throw new Error("System health is unavailable.");
      setHealth(await response.json());
      setHealthError(null);
    } catch (err) { setHealthError(errorMessage(err) || "System health is unavailable."); }
  }, [handleAuthFailure]);
  useEffect(() => { if (apiKey) refreshHealth(apiKey); }, [apiKey, refreshHealth]);
  const fetchProfiles = useCallback(async (currentKey: string, signal?: AbortSignal) => {
    try {
      const response = await fetch(`${API_BASE}/executives/profiles`, { headers: { "X-API-Key": currentKey }, signal });
      if (response.status === 401) { handleAuthFailure(); return; }
      if (!response.ok) throw new Error("Executive profiles unavailable. Restart the updated backend.");
      const data = await response.json();
      if (signal?.aborted) return;
      setProfiles(data);
      setSectionErrors(previous => ({ ...previous, profiles: "" }));
    } catch (error) { if (!signal?.aborted) setSectionErrors(previous => ({ ...previous, profiles: errorMessage(error) })); }
  }, [handleAuthFailure]);
  useEffect(() => {
    if (!apiKey) return;
    const controller = new AbortController();
    fetchProfiles(apiKey, controller.signal);
    return () => controller.abort();
  }, [apiKey, fetchProfiles]);
  const refreshAll = async () => {
    if (!apiKey) return;
    setRefreshing(true);
    try { await Promise.all([fetchDashboardData(), fetchPendingActions(apiKey), fetchActionHistory(apiKey),
      fetchResourceRequests(apiKey), fetchTreasury(apiKey), fetchGoals(apiKey), fetchFollowups(apiKey),
      fetchExecutiveMemories(apiKey, memoryExecutive), refreshHealth(apiKey), fetchProfiles(apiKey)]); }
    finally { setRefreshing(false); }
  };

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
        fetchResourceRequests(apiKey);
        fetchTreasury(apiKey);
      }
    } catch (err: unknown) {
      if (apiKey) fetchPendingActions(apiKey);
      setActionErrors((prev) => ({
        ...prev,
        [id]: errorMessage(err) || "An error occurred while processing this action.",
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

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || data.error || "Execution failed.");
      }

      const executionData = data as ExecutionResult;
      setExecutionResults((prev) => ({ ...prev, [action.id]: executionData }));

      // Terminal actions leave the active queue; their result remains in history.
      setPendingActions((prev) => prev.filter((act) => act.id !== action.id));

      if (apiKey) {
        fetchPendingActions(apiKey);
        fetchActionHistory(apiKey);
        fetchResourceRequests(apiKey);
        fetchTreasury(apiKey);
      }
    } catch (err: unknown) {
      setActionErrors((prev) => ({
        ...prev,
        [action.id]: errorMessage(err) || "Error while executing action.",
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

  const handleResourceDecision = async (
    id: number,
    type: "approve" | "reject" | "fulfill"
  ) => {
    setResourceErrors((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });

    let fulfillmentNote: string | null = null;
    if (type === "fulfill") {
      fulfillmentNote = window.prompt(
        "Describe how the resource was provided. Do NOT paste passwords, API keys, tokens, or other secrets."
      );
      if (!fulfillmentNote?.trim()) return;
    }

    try {
      const response = await fetch(`${API_BASE}/resources/${id}/${type}`, {
        method: "POST",
        headers: {
          "X-API-Key": apiKey || "",
          ...(type === "fulfill" ? { "Content-Type": "application/json" } : {}),
        },
        body:
          type === "fulfill"
            ? JSON.stringify({ fulfillment_note: fulfillmentNote })
            : undefined,
      });

      if (response.status === 401) {
        handleAuthFailure();
        return;
      }
      const data = await response.json().catch(() => null);
      if (!response.ok) throw new Error(data?.detail || `Could not ${type} resource request.`);

      if (apiKey) fetchResourceRequests(apiKey);
      await fetchDashboardData();
    } catch (err: unknown) {
      setResourceErrors((prev) => ({
        ...prev,
        [id]: errorMessage(err) || "Could not update resource request.",
      }));
    }
  };

  const handleDecisionReview = async (id: number, type: "approve" | "reject") => {
    setDecisionErrors((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });

    try {
      const response = await fetch(`${API_BASE}/decisions/${id}/${type}`, {
        method: "POST",
        headers: { "X-API-Key": apiKey || "" },
      });
      if (response.status === 401) {
        handleAuthFailure();
        return;
      }
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || `Could not ${type} decision.`);
      }
      await fetchDashboardData();
    } catch (err: unknown) {
      setDecisionErrors((prev) => ({
        ...prev,
        [id]: errorMessage(err) || "Could not update decision approval.",
      }));
    }
  };

  const handlePrepareDecision = async (id: number) => {
    const confirmed = window.confirm(
      "Start Phase 2 preparation? Tool-capable executives may create action proposals and structured resource requests. Nothing executes or grants access without separate owner review."
    );
    if (!confirmed) return;

    setPreparingDecisionIds((prev) => new Set(prev).add(id));
    setDecisionErrors((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });

    try {
      const response = await fetch(`${API_BASE}/decisions/${id}/prepare`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey || "",
        },
        body: JSON.stringify({ agent_keys: ["coo", "cto", "ceo"] }),
      });

      if (response.status === 401) {
        handleAuthFailure();
        return;
      }

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Preparation failed.");
      }

      setPreparationResults((prev) => ({ ...prev, [id]: data.final_plan }));
      await fetchDashboardData();
      if (apiKey) {
        fetchPendingActions(apiKey);
        fetchActionHistory(apiKey);
      }
    } catch (err: unknown) {
      setDecisionErrors((prev) => ({
        ...prev,
        [id]: errorMessage(err) || "Preparation failed.",
      }));
      await fetchDashboardData();
    } finally {
      setPreparingDecisionIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handleLoadLineage = async (id: number) => {
    if (lineageResults[id]) {
      setLineageResults((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      return;
    }

    setLoadingLineageIds((prev) => new Set(prev).add(id));
    setDecisionErrors((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });

    try {
      const response = await fetch(`${API_BASE}/decisions/${id}/lineage`, {
        headers: { "X-API-Key": apiKey || "" },
      });
      if (response.status === 401) {
        handleAuthFailure();
        return;
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not load decision lineage.");
      setLineageResults((prev) => ({ ...prev, [id]: data }));
    } catch (err: unknown) {
      setDecisionErrors((prev) => ({
        ...prev,
        [id]: errorMessage(err) || "Could not load decision lineage.",
      }));
    } finally {
      setLoadingLineageIds((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
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
  const [selectedAgents, setSelectedAgents] = useState<string[]>(["cso", "cfo", "ceo"]);
  const [selectedGoalId, setSelectedGoalId] = useState<string>("");
  const [selectedMeetingType, setSelectedMeetingType] = useState("strategy");
  const [meetingTypes, setMeetingTypes] = useState<Record<string, MeetingTypeProfile>>({});
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
          meeting_type: selectedMeetingType,
          agent_keys: selectedAgents,
          goal_id: selectedGoalId ? Number(selectedGoalId) : null,
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
    } catch (err: unknown) {
      setError(errorMessage(err) || "An unknown error occurred.");
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

      <div className="max-w-7xl mx-auto p-4 sm:p-8 space-y-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div><p className="text-xs tracking-widest uppercase text-teal-300 mb-2">AI Executive Team · Company dashboard v2</p>
            <h1 className="text-3xl sm:text-4xl font-semibold tracking-tight">Company command center</h1>
            <p className="text-gray-400 mt-2">Set direction. Review proposals. Measure what happened.</p></div>
          <button onClick={refreshAll} disabled={refreshing} className="border border-gray-700 rounded-lg px-4 py-2 text-sm hover:bg-gray-800 disabled:opacity-50">{refreshing ? "Refreshing…" : "Refresh company data"}</button>
        </header>
        <nav aria-label="Company views" className="flex flex-wrap gap-2 border-b border-gray-800 pb-4">
          {VIEWS.map(([key, label]) => <button key={key} aria-current={view === key ? "page" : undefined}
            onClick={() => setView(key)} className={`rounded-lg px-3 py-2 text-sm transition-colors ${view === key ? "bg-teal-300 text-gray-950 font-semibold" : "text-gray-400 hover:bg-gray-800 hover:text-white"}`}>{label}</button>)}
        </nav>
        {Object.entries(sectionErrors).filter(([, error]) => error).map(([key, error]) => <p role="alert" key={key} className="text-amber-200 border border-amber-800 rounded-lg p-3">{error} Previously loaded data may be stale. Use Refresh company data to retry.</p>)}
        <section hidden={view !== "overview"} aria-label="Company overview" className="space-y-6">
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {([
              ["Active goals", !loadedSections.goals || goalError ? "Unavailable" : goals.filter(g => g.status === "active").length, "goals", "Current loaded goals"],
              ["Actions to review", !loadedSections.pendingActions || sectionErrors.pendingActions ? "Unavailable" : pendingActions.filter(a => a.status === "pending").length, "actions", "Approval and execution are separate"],
              ["Resources needed", !loadedSections.resources || sectionErrors.resources ? "Unavailable" : resourceRequests.length, "resources", "Access, data and capital requests"],
              ["Open follow-ups", !loadedSections.followups || followupError ? "Unavailable" : followups.filter(f => f.status === "open").length, "activity", "Observations and owner review"],
            ] as const).map(([label, value, target, note]) => <button key={label} onClick={() => setView(target)} className="text-left bg-gray-900 border border-gray-800 rounded-xl p-5 hover:border-teal-600">
              <span className="text-sm text-gray-400">{label}</span><strong className="block text-3xl my-3">{value}</strong><span className="text-xs text-gray-500">{note}</span></button>)}
          </div>
          <div className="grid lg:grid-cols-2 gap-6">
            <article className="command-card"><h2>Treasury available</h2><p className="text-sm text-gray-400 mb-4">Available capital after reservations, kept separate by currency.</p>
              {!loadedSections.treasury || sectionErrors.treasury ? <p>Treasury unavailable.</p> : Object.keys(treasury.currencies).length === 0 ? <p className="text-gray-400">No funding recorded. Add capital in Treasury.</p> : Object.entries(treasury.currencies).map(([currency, balance]) => <div className="flex justify-between border-t border-gray-800 py-3" key={currency}><strong>{currency}</strong><span>{balance.available.toLocaleString(undefined, { maximumFractionDigits: 2 })} available · {balance.reserved} reserved</span></div>)}
              <button className="command-link" onClick={() => setView("treasury")}>Manage treasury →</button>
            </article>
            <article className="command-card"><h2>Needs your attention</h2><p className="text-sm text-gray-400 mb-4">Recent decisions awaiting direction approval and actions ready to execute.</p>
              {!loadedSections.decisions || loadError ? <p>Decisions unavailable.</p> : history.filter(d => d.approval_status === "pending").slice(0, 3).map(d => <button key={d.id} className="block text-left py-2 command-link" onClick={() => setView("decisions")}>Decision #{d.id} · {d.topic}</button>)}
              {pendingActions.filter(a => a.status === "approved").slice(0, 3).map(a => <button key={a.id} className="block text-left py-2 command-link" onClick={() => setView("actions")}>Ready for execution · #{a.id} {a.action_description}</button>)}
              <p className="text-xs text-gray-500 mt-3">Decision summaries cover the latest 20 records. Review each view for details.</p>
            </article>
            <article className="command-card"><h2>Recent experiment results</h2><p className="text-sm text-gray-400 mb-4">Execution is distinct from a measured business outcome.</p>
              {!loadedSections.actionHistory || sectionErrors.actionHistory ? <p>Results unavailable.</p> : actionHistory.filter(a => a.actual_outcome).length === 0 ? <p className="text-gray-400">No measured results in the latest 20 actions. Record observations in Actions & results.</p> : actionHistory.filter(a => a.actual_outcome).slice(0, 3).map(a => <div key={a.id} className="border-t border-gray-800 py-3"><p className="font-medium">#{a.id} · {a.action_description}</p><p className="text-teal-300 text-xs my-1">{a.outcome_status?.replaceAll("_", " ")}</p><p className="text-sm text-gray-400">{a.actual_outcome}</p></div>)}
              <button className="command-link" onClick={() => setView("actions")}>Review actions and outcomes →</button>
            </article>
            <article className="command-card"><h2>Executive activity</h2><p className="text-sm text-gray-400">Research: {status?.success === true ? "Last run succeeded" : status?.success === false ? "Last run failed" : "No completed run"}</p><p className="text-sm text-gray-400 mt-2">Follow-up: {followupStatus?.message || "No run recorded"}</p><p className="text-sm mt-4">System: {healthError ? "Unavailable" : health?.status || "Checking…"}</p><button className="command-link" onClick={() => setView("activity")}>Review activity and memory →</button></article>
          </div>
        </section>
        <div hidden={view !== "office"}>
          <VirtualOffice profiles={profiles} onRecords={() => setView("records")} decisions={history} actions={[...pendingActions, ...actionHistory.filter(a => !pendingActions.some(p => p.id === a.id))]}
            resources={resourceRequests} followups={followups}
            available={{ decisions: !!loadedSections.decisions && !loadError,
              actions: !!loadedSections.pendingActions && !!loadedSections.actionHistory && !sectionErrors.pendingActions && !sectionErrors.actionHistory,
              resources: !!loadedSections.resources && !sectionErrors.resources,
              followups: !!loadedSections.followups && !followupError }}
            errors={!!loadError || !!followupError || Object.values(sectionErrors).some(Boolean)}
            onNavigate={setView} onMemory={(executive) => { setMemoryExecutive(executive); setView("activity"); }} />
        </div>
        {view === "boards" && apiKey && <AgileBoard apiKey={apiKey} profiles={profiles} onAuthFailure={handleAuthFailure} onNavigate={setView} />}
        {view === "records" && apiKey && <CompanyRecords apiKey={apiKey} decisions={history} profiles={profiles} onAuthFailure={handleAuthFailure} onNavigate={setView} />}
        <section hidden={view !== "system"} className="command-card" aria-label="System health">
          <h2>System health</h2>{healthError && <p role="alert" className="text-amber-300">{healthError}</p>}
          {health ? <><p className="text-gray-400 mb-4">Overall: {health.status} · uptime {Math.floor(health.uptime_seconds / 60)} minutes. Telegram and browser are optional components.</p><div className="grid sm:grid-cols-2 gap-4">{Object.entries(health.components).map(([name, component]) => <div key={name} className="border border-gray-800 rounded-lg p-4"><h3 className="capitalize font-medium">{name.replaceAll("_", " ")}</h3><p className={component.ok ? "text-teal-300" : "text-amber-300"}>{component.ok ? "Ready" : "Not ready"}</p><p className="text-sm text-gray-400 mt-2">{component.message}</p></div>)}</div></> : <p>Waiting for a health response.</p>}
        </section>

        {loadError && (
          <div className="p-4 bg-red-950 border-l-4 border-red-500 text-red-300 rounded">
            {loadError}
          </div>
        )}

        {/* Executive Memory */}
        <section hidden={view !== "activity"} className="space-y-6">
        <div className="bg-gray-900 border border-sky-900/70 rounded-lg p-6 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-sky-200">Executive Memory</h2>
            <p className="text-xs text-gray-500 mt-1">
              Structured historical lessons only. Memories are advisory and never override current evidence or owner-approved state.
            </p>
          </div>

          <div className="flex flex-wrap gap-2 items-center">
            <select
              value={memoryExecutive}
              onChange={(e) => setMemoryExecutive(e.target.value)}
              className="bg-gray-950 border border-gray-700 rounded p-2 text-sm"
            >
              {AGENT_OPTIONS.map((agent) => (
                <option key={agent.key} value={agent.key}>{agent.label}</option>
              ))}
            </select>
            {apiKey && (
              <button
                type="button"
                onClick={() => fetchExecutiveMemories(apiKey, memoryExecutive)}
                className="px-3 py-1.5 bg-sky-800 hover:bg-sky-700 text-white text-xs rounded"
              >
                Refresh Memory
              </button>
            )}
          </div>

          {memoryError && (
            <div className="text-xs text-red-300 border border-red-900 bg-red-950/40 rounded p-2">
              {memoryError}
            </div>
          )}

          {executiveMemories.length === 0 ? (
            <p className="text-gray-500 text-sm">No active structured memories for this executive yet.</p>
          ) : (
            <div className="space-y-3">
              {executiveMemories.map((memory) => (
                <div key={memory.id} className="bg-gray-950 border border-sky-900/50 rounded p-4 space-y-2">
                  <div className="flex justify-between gap-3">
                    <div className="text-sm font-semibold text-gray-200">
                      #{memory.id} · {memory.memory_kind.replaceAll("_", " ")}
                    </div>
                    <div className="text-xs text-sky-300">
                      confidence {(memory.confidence * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div className="text-sm text-gray-300">{memory.lesson}</div>
                  {memory.supporting_evidence && (
                    <details className="text-xs text-gray-500">
                      <summary className="cursor-pointer text-gray-400">Historical support</summary>
                      <div className="mt-2 whitespace-pre-wrap">{memory.supporting_evidence}</div>
                    </details>
                  )}
                  <div className="text-xs text-gray-500">
                    {memory.source_goal_id ? `Goal #${memory.source_goal_id}` : ""}
                    {memory.source_decision_id ? `${memory.source_goal_id ? " · " : ""}Decision #${memory.source_decision_id}` : ""}
                    {memory.source_action_id ? ` · Action #${memory.source_action_id}` : ""}
                  </div>
                  <button
                    type="button"
                    onClick={() => handleMemoryStatus(memory.id, false)}
                    className="px-2.5 py-1 bg-gray-800 text-gray-300 text-xs rounded"
                  >
                    Deactivate Memory
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        </section>
        {/* Autonomous Follow-Up */}
        <section hidden={view !== "activity"} className="space-y-6">
        <div className="bg-gray-900 border border-violet-900/70 rounded-lg p-6 space-y-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-violet-200">Autonomous Follow-Up</h2>
              <p className="text-xs text-gray-500 mt-1">
                Hourly deterministic scan. It may create tool-free pending decisions, but never approves, prepares, fulfills, reserves, executes, or measures anything.
              </p>
            </div>
            <button
              type="button"
              onClick={handleRunFollowup}
              disabled={runningFollowup}
              className="px-3 py-1.5 bg-violet-700 hover:bg-violet-600 text-white text-xs rounded disabled:opacity-50"
            >
              {runningFollowup ? "Scanning..." : "Run Scan Now"}
            </button>
          </div>

          {followupStatus && (
            <div className="text-xs text-gray-400 border border-gray-800 rounded p-3">
              <div>{followupStatus.message}</div>
              <div className="mt-1">
                Last run: {followupStatus.last_run_time || "never"} · goals scanned: {followupStatus.scanned_goal_count}
              </div>
              {followupStatus.generated_decision_ids.length > 0 && (
                <div className="mt-1 text-violet-300">
                  Generated pending decisions: {followupStatus.generated_decision_ids.map((id) => `#${id}`).join(", ")}
                </div>
              )}
            </div>
          )}

          {followupError && (
            <div className="text-xs text-red-300 border border-red-900 bg-red-950/40 rounded p-2">
              {followupError}
            </div>
          )}

          {followups.length === 0 ? (
            <p className="text-gray-500 text-sm">No open follow-up items.</p>
          ) : (
            <div className="space-y-3">
              {followups.map((item) => (
                <div
                  key={item.id}
                  className={`bg-gray-950 rounded p-4 border ${
                    item.severity === "critical"
                      ? "border-red-800"
                      : item.severity === "attention"
                      ? "border-yellow-800"
                      : "border-gray-800"
                  }`}
                >
                  <div className="flex justify-between gap-3">
                    <div className="text-sm font-semibold text-gray-200">
                      #{item.id} · {item.event_type.replaceAll("_", " ")}
                    </div>
                    <div className="text-xs uppercase text-gray-400">{item.severity}</div>
                  </div>
                  <div className="text-sm text-gray-400 mt-2">{item.reason}</div>
                  <div className="text-xs text-gray-500 mt-2">
                    {item.goal_id ? `Goal #${item.goal_id}${item.goal_title ? ` — ${item.goal_title}` : ""}` : "No goal"}
                    {item.source_action_id ? ` · Action #${item.source_action_id}` : ""}
                    {item.source_decision_id ? ` · Source Decision #${item.source_decision_id}` : ""}
                  </div>
                  {item.generated_decision_id && (
                    <div className="text-xs text-violet-300 mt-1">
                      Tool-free follow-up created Decision #{item.generated_decision_id} — pending owner review.
                    </div>
                  )}
                  <div className="flex gap-2 mt-3">
                    <button
                      onClick={() => handleFollowupDecision(item.id, "resolve")}
                      className="px-2.5 py-1 bg-green-800 text-white text-xs rounded"
                    >
                      Resolve
                    </button>
                    <button
                      onClick={() => handleFollowupDecision(item.id, "dismiss")}
                      className="px-2.5 py-1 bg-gray-800 text-gray-300 text-xs rounded"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        </section>
        {/* Company Goals / Missions */}
        <section hidden={view !== "goals"} className="space-y-6">
        <div className="bg-gray-900 border border-amber-900/70 rounded-lg p-6 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-amber-200">Company Goals / Missions</h2>
            <p className="text-xs text-gray-500 mt-1">
              Goals are owner-controlled. Agents can work toward active goals, but cannot declare them complete.
            </p>
          </div>

          {goalError && (
            <div className="text-xs text-red-300 border border-red-900 bg-red-950/40 rounded p-2">
              {goalError}
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-2">
            <input
              value={goalTitle}
              onChange={(e) => setGoalTitle(e.target.value)}
              placeholder="Goal title"
              className="bg-gray-950 border border-gray-700 rounded p-2 text-sm"
            />
            <select
              value={goalPriority}
              onChange={(e) => setGoalPriority(e.target.value as CompanyGoal["priority"])}
              className="bg-gray-950 border border-gray-700 rounded p-2 text-sm"
            >
              <option value="critical">Critical priority</option>
              <option value="high">High priority</option>
              <option value="medium">Medium priority</option>
              <option value="low">Low priority</option>
            </select>
            <textarea
              value={goalDescription}
              onChange={(e) => setGoalDescription(e.target.value)}
              placeholder="Mission / what the company is trying to achieve"
              rows={2}
              className="bg-gray-950 border border-gray-700 rounded p-2 text-sm"
            />
            <textarea
              value={goalSuccessCriteria}
              onChange={(e) => setGoalSuccessCriteria(e.target.value)}
              placeholder="Measurable success criteria"
              rows={2}
              className="bg-gray-950 border border-gray-700 rounded p-2 text-sm"
            />
            <input
              type="date"
              value={goalTargetDate}
              onChange={(e) => setGoalTargetDate(e.target.value)}
              className="bg-gray-950 border border-gray-700 rounded p-2 text-sm"
            />
            <label className="flex items-center gap-2 text-sm text-gray-300">
              <input
                type="checkbox"
                checked={goalStartActive}
                onChange={(e) => setGoalStartActive(e.target.checked)}
              />
              Start active
            </label>
          </div>
          <button
            type="button"
            onClick={handleCreateGoal}
            disabled={creatingGoal}
            className="px-3 py-1.5 bg-amber-700 hover:bg-amber-600 text-white text-xs rounded disabled:opacity-50"
          >
            {creatingGoal ? "Creating..." : "Create Goal"}
          </button>

          <div className="space-y-3">
            {goals.length === 0 && <p className="text-gray-500 text-sm">No company goals yet.</p>}
            {goals.map((goal) => (
              <div key={goal.id} className="bg-gray-950 border border-amber-900/50 rounded p-4 space-y-2">
                <div className="flex justify-between gap-3">
                  <div>
                    <div className="font-semibold text-gray-200">
                      #{goal.id} · {goal.title}
                    </div>
                    <div className="text-xs text-amber-300 uppercase">
                      {goal.priority} · {goal.status}
                      {goal.target_date ? ` · target ${goal.target_date}` : ""}
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 text-right">
                    <div>{goal.linked_decision_count || 0} decisions</div>
                    <div>{goal.linked_action_count || 0} actions</div>
                    <div>{goal.measured_outcome_count || 0} measured outcomes</div>
                  </div>
                </div>
                <div className="text-sm text-gray-400">{goal.description}</div>
                <div className="text-xs">
                  <span className="text-gray-500">Success:</span>{" "}
                  <span className="text-gray-300">{goal.success_criteria}</span>
                </div>
                {goal.completion_note && (
                  <div className="text-xs text-gray-400">
                    <span className="text-gray-500">Closure evidence:</span> {goal.completion_note}
                  </div>
                )}
                <div className="flex flex-wrap gap-2">
                  {goal.status === "draft" && (
                    <button onClick={() => handleGoalStatus(goal, "active")} className="px-2.5 py-1 bg-green-700 text-white text-xs rounded">
                      Activate
                    </button>
                  )}
                  {goal.status === "active" && (
                    <button onClick={() => handleGoalStatus(goal, "paused")} className="px-2.5 py-1 bg-yellow-700 text-white text-xs rounded">
                      Pause
                    </button>
                  )}
                  {goal.status === "paused" && (
                    <button onClick={() => handleGoalStatus(goal, "active")} className="px-2.5 py-1 bg-green-700 text-white text-xs rounded">
                      Resume
                    </button>
                  )}
                  {["active", "paused"].includes(goal.status) && (
                    <button onClick={() => handleGoalStatus(goal, "completed")} className="px-2.5 py-1 bg-blue-700 text-white text-xs rounded">
                      Complete
                    </button>
                  )}
                  {!["completed", "abandoned"].includes(goal.status) && (
                    <button onClick={() => handleGoalStatus(goal, "abandoned")} className="px-2.5 py-1 bg-red-800 text-white text-xs rounded">
                      Abandon
                    </button>
                  )}
                  <button onClick={() => handleGoalLineage(goal.id)} className="px-2.5 py-1 bg-gray-800 text-gray-200 text-xs rounded">
                    {goalLineage[goal.id] ? "Hide Lineage" : "View Lineage"}
                  </button>
                </div>
                {goalLineage[goal.id] && (
                  <div className="border-t border-gray-800 pt-2 text-xs space-y-1">
                    <div className="text-gray-300">
                      Decisions: {goalLineage[goal.id].decision_count}
                    </div>
                    <div className="text-gray-300">
                      Outcomes: {Object.entries(goalLineage[goal.id].outcome_counts)
                        .map(([key, value]) => `${key} ${value}`)
                        .join(" · ")}
                    </div>
                    <div className="text-gray-300">
                      Spend: {Object.entries(goalLineage[goal.id].spend_by_currency).length
                        ? Object.entries(goalLineage[goal.id].spend_by_currency)
                            .map(([currency, amount]) => `${amount} ${currency}`)
                            .join(" · ")
                        : "none"}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        </section>
        {/* Company Treasury */}
        <section hidden={view !== "treasury"} className="space-y-6">
        <div className="bg-gray-900 border border-emerald-900/70 rounded-lg p-6 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-emerald-200">Company Treasury</h2>
            <p className="text-xs text-gray-500 mt-1">
              Cash is real recorded capital. Reserved funds are earmarked for approved paid actions but are not spent yet.
            </p>
          </div>

          {Object.keys(treasury.currencies).length === 0 ? (
            <p className="text-gray-500 text-sm">No company capital recorded yet.</p>
          ) : (
            <div className="grid sm:grid-cols-3 gap-3">
              {Object.entries(treasury.currencies).map(([currency, values]) => (
                <div key={currency} className="bg-gray-950 border border-gray-800 rounded p-3">
                  <div className="font-semibold text-gray-200">{currency}</div>
                  <div className="mt-2 text-xs space-y-1">
                    <div><span className="text-gray-500">Cash:</span> {values.cash_balance.toFixed(2)}</div>
                    <div><span className="text-gray-500">Reserved:</span> {values.reserved.toFixed(2)}</div>
                    <div><span className="text-gray-500">Available:</span> {values.available.toFixed(2)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="border-t border-gray-800 pt-4">
            <div className="text-sm font-medium text-gray-300 mb-2">Record owner funding</div>
            <div className="grid sm:grid-cols-3 gap-2">
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={fundAmount}
                onChange={(e) => setFundAmount(e.target.value)}
                placeholder="Amount"
                className="bg-gray-950 border border-gray-700 rounded p-2 text-sm"
              />
              <input
                value={fundCurrency}
                onChange={(e) => setFundCurrency(e.target.value.toUpperCase())}
                placeholder="Currency (EUR)"
                maxLength={3}
                className="bg-gray-950 border border-gray-700 rounded p-2 text-sm uppercase"
              />
              <input
                value={fundNote}
                onChange={(e) => setFundNote(e.target.value)}
                placeholder="Note (optional)"
                maxLength={500}
                className="bg-gray-950 border border-gray-700 rounded p-2 text-sm"
              />
            </div>
            <div className="mt-2 flex items-center gap-3">
              <button
                type="button"
                onClick={handleFundTreasury}
                disabled={fundingTreasury}
                className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white text-xs rounded disabled:opacity-50"
              >
                {fundingTreasury ? "Recording..." : "Add Funding"}
              </button>
              {treasuryMessage && <span className="text-xs text-gray-300">{treasuryMessage}</span>}
            </div>
            <p className="text-xs text-gray-600 mt-2">
              This records capital in the internal ledger only; it does not transfer money or connect a bank account.
            </p>
          </div>
        </div>

        </section>
        {/* Daily research status card */}
        <section hidden={view !== "activity"} className="space-y-6">
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

        </section>
        {/* Structured Resource / Capability Requests */}
        <section hidden={view !== "resources"} className="space-y-6">
        <div className="bg-gray-900 border border-indigo-900/70 rounded-lg p-6 space-y-4">
          <div>
            <h2 className="text-lg font-semibold text-indigo-200">
              Resource & Capability Requests ({resourceRequests.length})
            </h2>
            <p className="text-xs text-gray-500 mt-1">
              Approval does not grant access or execute anything. Mark fulfilled only after you provide the resource separately.
            </p>
          </div>

          {resourceRequests.length === 0 ? (
            <p className="text-gray-500 text-sm">No resource requests awaiting owner action.</p>
          ) : (
            <div className="space-y-4">
              {resourceRequests.map((resource) => (
                <div
                  key={resource.id}
                  className="bg-gray-950 border border-indigo-900/70 rounded-md p-4 space-y-3"
                >
                  <div className="flex justify-between gap-3">
                    <div className="flex flex-wrap gap-2 items-center">
                      <span className="text-xs bg-indigo-950 border border-indigo-800 text-indigo-300 rounded px-2 py-0.5 uppercase">
                        {resource.resource_type}
                      </span>
                      {statusBadge(resource.status)}
                      <span className="text-xs text-gray-500">
                        requested by {resource.requested_by}
                      </span>
                    </div>
                    <span className="text-xs text-gray-500">
                      {new Date(resource.timestamp).toLocaleString("en-US")}
                    </span>
                  </div>

                  <div>
                    <div className="font-semibold text-gray-200">{resource.resource_name}</div>
                    <div className="text-sm text-gray-400 mt-1 whitespace-pre-wrap">
                      {resource.reason}
                    </div>
                  </div>

                  {resource.required_for && (
                    <div className="text-xs">
                      <span className="text-gray-500">Required for:</span>{" "}
                      <span className="text-gray-300">{resource.required_for}</span>
                    </div>
                  )}

                  {resource.amount !== null && resource.amount !== undefined && (
                    <div className="text-xs">
                      <span className="text-gray-500">Requested budget:</span>{" "}
                      <span className="text-gray-300">
                        {resource.amount} {resource.currency || ""}
                      </span>
                    </div>
                  )}

                  {resource.source_decision_id && (
                    <div className="text-xs text-cyan-300">
                      Source: Decision #{resource.source_decision_id}
                      {resource.source_decision_topic
                        ? ` — ${resource.source_decision_topic}`
                        : ""}
                    </div>
                  )}
                  {resource.source_goal_id && (
                    <div className="text-xs text-amber-300">
                      Goal #{resource.source_goal_id}
                      {resource.source_goal_title ? ` — ${resource.source_goal_title}` : ""}
                    </div>
                  )}

                  {resourceErrors[resource.id] && (
                    <div className="text-xs text-red-300 border border-red-900 bg-red-950/40 rounded p-2">
                      {resourceErrors[resource.id]}
                    </div>
                  )}

                  <div className="flex flex-wrap gap-2">
                    <button
                      onClick={() => handleResourceDecision(resource.id, "approve")}
                      disabled={resource.status !== "pending"}
                      className="px-3 py-1.5 bg-green-700 hover:bg-green-600 text-white text-xs rounded disabled:opacity-40"
                    >
                      Approve Resource
                    </button>
                    <button
                      onClick={() => handleResourceDecision(resource.id, "reject")}
                      disabled={!["pending", "approved"].includes(resource.status)}
                      className="px-3 py-1.5 bg-red-700 hover:bg-red-600 text-white text-xs rounded disabled:opacity-40"
                    >
                      Reject
                    </button>
                    <button
                      onClick={() => handleResourceDecision(resource.id, "fulfill")}
                      disabled={resource.status !== "approved"}
                      className="px-3 py-1.5 bg-indigo-700 hover:bg-indigo-600 text-white text-xs rounded disabled:opacity-40"
                    >
                      Mark Fulfilled
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        </section>
        {/* Pending Actions section */}
        <section hidden={view !== "actions"} className="space-y-6">
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
                const isPending = action.status === "pending";
                const isApproved = action.status === "approved";
                const isExecuting = action.status === "executing" || executingIds.has(action.id);
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

                    {action.source_decision_id && (
                      <div className="text-xs text-cyan-300 border border-cyan-900 bg-cyan-950/30 rounded px-2 py-1">
                        Source: Decision #{action.source_decision_id}
                        {action.source_decision_topic ? ` — ${action.source_decision_topic}` : ""}
                        {action.source_phase ? ` · ${action.source_phase}` : ""}
                      </div>
                    )}
                    {action.source_goal_id && (
                      <div className="text-xs text-amber-300 border border-amber-900/60 bg-amber-950/20 rounded px-2 py-1">
                        Goal #{action.source_goal_id}
                        {action.source_goal_title ? ` — ${action.source_goal_title}` : ""}
                      </div>
                    )}

                    <div className="bg-gray-900 border border-gray-800 rounded p-3 text-xs font-mono text-green-400 overflow-x-auto whitespace-pre-wrap">
                      {renderActionDetail(action.action_type, action.action_detail)}
                    </div>

                    {action.expected_cost_amount !== null && action.expected_cost_amount !== undefined && (
                      <div className="text-xs border border-emerald-900/60 bg-emerald-950/20 rounded px-2 py-1">
                        <span className="text-gray-500">Expected cost:</span>{" "}
                        <span className="text-emerald-300">
                          {action.expected_cost_amount} {action.currency || ""}
                        </span>
                        {action.status === "approved" && (
                          <span className="text-gray-500"> · treasury reserved</span>
                        )}
                      </div>
                    )}

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
                        disabled={!isPending || isExecuting}
                        className="px-3 py-1.5 bg-green-600 hover:bg-green-700 text-white text-xs font-medium rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => handleActionDecision(action.id, "reject")}
                        disabled={(!isPending && !isApproved) || isExecuting}
                        className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-medium rounded transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
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

        </section>
        {/* Ad-hoc decision trigger form */}
        <section hidden={view !== "decisions"} className="space-y-6">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold">Start New Ad-Hoc Decision</h2>

          {result && (
            <div className="border border-green-800 bg-green-950/40 rounded-md p-5 space-y-4">
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="text-lg font-bold text-green-300">{result.topic}</h3>
                  <div className="text-xs text-purple-300 uppercase mt-1">
                    {result.meeting_type.replaceAll("_", " ")}
                  </div>
                </div>
                <span className="text-xs bg-gray-800 text-gray-400 rounded-full px-2 py-1">
                  ID: #{result.database_id}
                </span>
              </div>
              <p className="text-sm text-green-400">
                Participants: {result.participants.join(", ")}
              </p>

              {result.quality_warnings &&
                ((result.quality_warnings.unsupported_quantitative_claims?.length || 0) > 0 ||
                  Object.keys(result.quality_warnings.repeated_analysis || {}).length > 0) && (
                  <div className="border border-yellow-800 bg-yellow-950/40 rounded p-3 text-sm text-yellow-200 space-y-2">
                    <div className="font-semibold">Decision Quality Warnings</div>
                    {(result.quality_warnings.unsupported_quantitative_claims?.length || 0) > 0 && (
                      <p>
                        Unsupported quantitative claims:{" "}
                        {result.quality_warnings.unsupported_quantitative_claims!.join(", ")}
                      </p>
                    )}
                    {Object.keys(result.quality_warnings.repeated_analysis || {}).length > 0 && (
                      <p>
                        Repeated analysis detected from:{" "}
                        {Object.keys(result.quality_warnings.repeated_analysis || {}).join(", ")}
                      </p>
                    )}
                  </div>
                )}

              <div>
                <h4 className="font-semibold text-gray-200 mb-1">Final Decision:</h4>
                <div className="bg-gray-950 rounded-md p-4 text-sm text-gray-200 whitespace-pre-wrap border border-gray-800">
                  <Report text={result.final_decision} />
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
                Meeting Type
              </label>
              <select
                value={selectedMeetingType}
                onChange={(e) => {
                  const next = e.target.value;
                  setSelectedMeetingType(next);
                  const profile = meetingTypes[next];
                  if (profile) setSelectedAgents(profile.default_agents);
                }}
                className="w-full rounded-md border border-gray-700 bg-gray-800 text-gray-100 p-2"
              >
                {Object.entries(meetingTypes).map(([key, profile]) => (
                  <option key={key} value={key}>
                    {profile.label}
                  </option>
                ))}
              </select>
              {meetingTypes[selectedMeetingType] && (
                <div className="mt-1 text-xs text-gray-500 space-y-1">
                  <div>{meetingTypes[selectedMeetingType].evidence_focus}</div>
                  <div>
                    Default roles: {meetingTypes[selectedMeetingType].default_agents.join(", ")}
                  </div>
                  <div>
                    Required roles: {meetingTypes[selectedMeetingType].required_agents.join(", ") || "none"}
                  </div>
                </div>
              )}
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
              <label className="block text-sm font-medium text-gray-400 mb-1">
                Company Goal (optional)
              </label>
              <select
                value={selectedGoalId}
                onChange={(e) => setSelectedGoalId(e.target.value)}
                className="w-full rounded-md border border-gray-700 bg-gray-800 text-gray-100 p-2"
              >
                <option value="">No linked goal</option>
                {goals.filter((goal) => goal.status === "active").map((goal) => (
                  <option key={goal.id} value={goal.id}>
                    #{goal.id} · {goal.priority.toUpperCase()} · {goal.title}
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Only active goals can receive new decisions.
              </p>
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

        </section>
        {/* Decision history */}
        <section hidden={view !== "decisions"} className="space-y-6">
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

              const approval = item.approval_status || "pending";
              const preparation = item.preparation_status || "not_started";
              const isPreparing = preparingDecisionIds.has(item.id);
              const shownPreparation =
                preparationResults[item.id] || item.preparation_outcome || null;

              return (
                <div
                  key={item.id}
                  className="bg-gray-900 border border-gray-800 rounded-lg p-5"
                >
                  <div className="flex justify-between items-start gap-3">
                    <div>
                      <h3 className="text-blue-400 font-bold text-lg">{item.topic}</h3>{item.meeting_type && <span className="text-xs text-purple-300 uppercase">{item.meeting_type.replaceAll("_", " ")}</span>}
                      <div className="flex gap-2 mt-2 text-xs">
                        <span className="bg-gray-800 border border-gray-700 rounded px-2 py-0.5">
                          Decision: {approval}
                        </span>
                        <span className="bg-gray-800 border border-gray-700 rounded px-2 py-0.5">
                          Preparation: {preparation}
                        </span>
                        <span className="bg-cyan-950/40 border border-cyan-900 text-cyan-300 rounded px-2 py-0.5">
                          Linked actions: {item.linked_action_count || 0}
                        </span>
                        <span className="bg-indigo-950/40 border border-indigo-900 text-indigo-300 rounded px-2 py-0.5">
                          Resource requests: {item.linked_resource_request_count || 0}
                        </span>
                      </div>
                    </div>
                    <span className="text-xs text-gray-500">
                      {new Date(item.timestamp).toLocaleString("en-US")}
                    </span>
                  </div>
                  {item.goal_id && (
                    <div className="mt-2 text-xs text-amber-300 border border-amber-900/60 bg-amber-950/20 rounded px-2 py-1 w-fit">
                      Goal #{item.goal_id}{item.goal_title ? ` — ${item.goal_title}` : ""}
                      {item.goal_status ? ` · ${item.goal_status}` : ""}
                    </div>
                  )}
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
                  <div className="text-sm text-gray-300 mt-3"><Report text={isExpanded ? item.decision_outcome : preview} /></div>
                  {item.decision_outcome.length > 150 && (
                    <button
                      onClick={() => toggleHistoryExpand(item.id)}
                      className="text-blue-400 text-sm mt-2 hover:underline"
                    >
                      {isExpanded ? "▲ Show less" : "▼ Show more"}
                    </button>
                  )}

                  {decisionErrors[item.id] && (
                    <div className="mt-3 p-2 bg-red-950 border border-red-800 text-red-300 text-xs rounded">
                      {decisionErrors[item.id]}
                    </div>
                  )}

                  <div className="flex flex-wrap gap-2 mt-4">
                    <button
                      onClick={() => handleDecisionReview(item.id, "approve")}
                      disabled={approval !== "pending" || isPreparing}
                      className="px-3 py-1.5 bg-green-700 hover:bg-green-600 text-white text-xs rounded disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Approve Direction
                    </button>
                    <button
                      onClick={() => handleDecisionReview(item.id, "reject")}
                      disabled={
                        !["pending", "approved"].includes(approval) ||
                        ["in_progress", "completed"].includes(preparation) ||
                        isPreparing
                      }
                      className="px-3 py-1.5 bg-red-700 hover:bg-red-600 text-white text-xs rounded disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Reject Direction
                    </button>
                    <button
                      onClick={() => handlePrepareDecision(item.id)}
                      disabled={
                        approval !== "approved" ||
                        !["not_started", "failed"].includes(preparation) ||
                        isPreparing
                      }
                      className="px-3 py-1.5 bg-purple-700 hover:bg-purple-600 text-white text-xs rounded disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      {isPreparing ? "Preparing..." : "Start Phase 2 Preparation"}
                    </button>
                    <button
                      onClick={() => handleLoadLineage(item.id)}
                      disabled={loadingLineageIds.has(item.id)}
                      className="px-3 py-1.5 bg-cyan-800 hover:bg-cyan-700 text-white text-xs rounded disabled:opacity-40"
                    >
                      {loadingLineageIds.has(item.id)
                        ? "Loading Lineage..."
                        : lineageResults[item.id]
                        ? "Hide Lineage"
                        : "View Lineage"}
                    </button>
                  </div>

                  {lineageResults[item.id] && (
                    <div className="mt-4 border border-cyan-900 rounded bg-gray-950 p-3 space-y-3">
                      <div className="font-semibold text-cyan-300 text-sm">
                        Decision → Action → Outcome Lineage
                      </div>
                      {lineageResults[item.id].actions.length === 0 ? (
                        <p className="text-xs text-gray-500">No actions linked to this decision yet.</p>
                      ) : (
                        <div className="space-y-2">
                          {lineageResults[item.id].actions.map((action) => (
                            <div
                              key={action.id}
                              className="border border-gray-800 rounded p-3 text-xs space-y-1"
                            >
                              <div className="flex flex-wrap gap-2 items-center">
                                <span className="text-cyan-300">Action #{action.id}</span>
                                {statusBadge(action.status)}
                                <span className="text-gray-500">
                                  Outcome: {action.outcome_status || "not_started"}
                                </span>
                              </div>
                              <div className="text-gray-300">{action.action_description}</div>
                              {action.expected_outcome && (
                                <div>
                                  <span className="text-gray-500">Expected:</span>{" "}
                                  <span className="text-gray-300">{action.expected_outcome}</span>
                                </div>
                              )}
                              {action.actual_outcome && (
                                <div>
                                  <span className="text-gray-500">Actual:</span>{" "}
                                  <span className="text-gray-300">{action.actual_outcome}</span>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                      {lineageResults[item.id].resource_requests?.length > 0 && (
                        <div className="space-y-2 border-t border-gray-800 pt-3">
                          <div className="text-xs font-semibold text-indigo-300">Resource Requests</div>
                          {lineageResults[item.id].resource_requests.map((resource) => (
                            <div key={resource.id} className="border border-indigo-900/70 rounded p-3 text-xs">
                              <div className="text-indigo-300">
                                #{resource.id} · {resource.resource_type} · {resource.status}
                              </div>
                              <div className="text-gray-300 mt-1">{resource.resource_name}</div>
                              <div className="text-gray-500 mt-1">{resource.reason}</div>
                            </div>
                          ))}
                        </div>
                      )}
                      {((lineageResults[item.id].treasury?.entries?.length || 0) > 0 ||
                        (lineageResults[item.id].treasury?.reservations?.length || 0) > 0) && (
                        <div className="space-y-2 border-t border-gray-800 pt-3">
                          <div className="text-xs font-semibold text-emerald-300">Treasury</div>
                          {lineageResults[item.id].treasury?.reservations?.map((reservation) => (
                            <div key={`reservation-${reservation.id}`} className="border border-emerald-900/70 rounded p-3 text-xs">
                              <div className="text-emerald-300">
                                Reservation #{reservation.id} · {reservation.status}
                              </div>
                              <div className="text-gray-300 mt-1">
                                {reservation.amount} {reservation.currency}
                                {reservation.source_action_id ? ` · Action #${reservation.source_action_id}` : ""}
                              </div>
                            </div>
                          ))}
                          {lineageResults[item.id].treasury?.entries?.map((entry) => (
                            <div key={`entry-${entry.id}`} className="border border-emerald-900/70 rounded p-3 text-xs">
                              <div className="text-emerald-300">
                                Ledger #{entry.id} · {entry.entry_type}
                              </div>
                              <div className="text-gray-300 mt-1">
                                {entry.amount} {entry.currency}
                                {entry.source_action_id ? ` · Action #${entry.source_action_id}` : ""}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {shownPreparation && (
                    <details className="mt-4 border border-purple-900 rounded bg-gray-950">
                      <summary className="cursor-pointer p-3 text-sm font-semibold text-purple-300">
                        Preparation Plan
                      </summary>
                      <pre className="p-3 border-t border-purple-900 whitespace-pre-wrap text-xs text-gray-300 font-sans">
                        {shownPreparation}
                      </pre>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        </section>
        <section hidden={view !== "actions"} className="space-y-6">
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
                  {item.source_decision_id && (
                    <div className="mt-3 text-xs text-cyan-300 border border-cyan-900 bg-cyan-950/30 rounded px-3 py-2">
                      Provenance: Decision #{item.source_decision_id}
                      {item.source_decision_topic ? ` — ${item.source_decision_topic}` : ""}
                      {item.source_phase ? ` · phase: ${item.source_phase}` : ""}
                    </div>
                  )}
                  {item.source_goal_id && (
                    <div className="mt-2 text-xs text-amber-300 border border-amber-900/60 bg-amber-950/20 rounded px-3 py-2">
                      Goal #{item.source_goal_id}
                      {item.source_goal_title ? ` — ${item.source_goal_title}` : ""}
                    </div>
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
                          {parsedResult.detail && (
                            <pre className="text-gray-300 whitespace-pre-wrap overflow-x-auto">{parsedResult.detail}</pre>
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
                  <OutcomeEditor
                    action={item}
                    apiKey={apiKey || ""}
                    onSaved={() => {
                      if (apiKey) {
                        fetchActionHistory(apiKey);
                        fetchTreasury(apiKey);
                      }
                    }}
                  />
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
        </section>
      </div>
    </div>
  );
}
