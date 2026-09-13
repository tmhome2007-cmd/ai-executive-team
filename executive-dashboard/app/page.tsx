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

  const handleAuthFailure = () => {
    sessionStorage.removeItem("dashboard_api_key");
    setApiKey(null);
    setKeyInput("");
  };

  // --- Dashboard data state ---
  const [status, setStatus] = useState<DailyResearchStatus | null>(null);
  const [history, setHistory] = useState<DecisionHistoryItem[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [expandedHistoryIds, setExpandedHistoryIds] = useState<Set<number>>(new Set());

  const fetchDashboardData = useCallback(async () => {
    try {
      const [statusRes, historyRes] = await Promise.all([
        fetch(`${API_BASE}/workflows/daily-research/status`),
        fetch(`${API_BASE}/decisions/history?limit=20`),
      ]);
      if (!statusRes.ok || !historyRes.ok) {
        throw new Error("Kon geen verbinding maken met de backend.");
      }
      setStatus(await statusRes.json());
      setHistory(await historyRes.json());
      setLoadError(null);
    } catch (err: any) {
      setLoadError(err.message || "Kon geen verbinding maken met de backend.");
    }
  }, []);

  useEffect(() => {
    if (apiKey !== null) {
      fetchDashboardData();
    }
  }, [apiKey, fetchDashboardData]);

  const toggleHistoryExpand = (id: number) => {
    setExpandedHistoryIds((prev) => {
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
      setError("Vul zowel een onderwerp als een taakomschrijving in.");
      return;
    }
    if (selectedAgents.length === 0) {
      setError("Selecteer minimaal 1 agent.");
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
        setError("Ongeldige sleutel — probeer opnieuw.");
        return;
      }

      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(detail?.detail || `Fout: ${response.statusText}`);
      }

      const data: DecisionResponse = await response.json();
      setResult(data);
      fetchDashboardData(); // refresh history so the new entry shows up
    } catch (err: any) {
      setError(err.message || "Er is een onbekende fout opgetreden.");
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
          <h1 className="text-xl font-semibold text-white">Toegang vereist</h1>
          <input
            type="password"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            placeholder="API-sleutel"
            className="w-full rounded-md border border-gray-700 bg-gray-800 text-white p-2"
            autoFocus
          />
          <button
            type="submit"
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Bevestigen
          </button>
        </form>
      </div>
    );
  }

  // --- Main dashboard ---
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <div className="max-w-4xl mx-auto p-6 space-y-8">
        <div>
          <h1 className="text-3xl font-bold">AI Executive Team Dashboard</h1>
          <p className="text-gray-400 mt-1">
            Overzicht van autonome besluiten en dagelijkse onderzoeksstatus.
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
            <h2 className="text-lg font-semibold">Dagelijkse Research Status</h2>
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
                  ? "Succesvol"
                  : status.success === false
                  ? "Mislukt"
                  : "Nog niet uitgevoerd"}
              </span>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4 mt-4 text-sm">
            <div>
              <p className="text-gray-500">Laatste uitvoering:</p>
              <p className="text-gray-200">
                {status?.last_run_time
                  ? new Date(status.last_run_time).toLocaleString("nl-BE")
                  : "Nog niet uitgevoerd"}
              </p>
            </div>
            <div>
              <p className="text-gray-500">Bericht / Details:</p>
              <p className="text-gray-200">{status?.message || "No run yet."}</p>
            </div>
          </div>
        </div>

        {/* Ad-hoc decision trigger form */}
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-4">
          <h2 className="text-lg font-semibold">Nieuw Ad-Hoc Besluit Starten</h2>

          {result && (
            <div className="border border-green-800 bg-green-950/40 rounded-md p-5 space-y-4">
              <div className="flex justify-between items-start">
                <h3 className="text-lg font-bold text-green-300">{result.topic}</h3>
                <span className="text-xs bg-gray-800 text-gray-400 rounded-full px-2 py-1">
                  ID: #{result.database_id}
                </span>
              </div>
              <p className="text-sm text-green-400">
                Deelnemers: {result.participants.join(", ")}
              </p>

              <div>
                <h4 className="font-semibold text-gray-200 mb-1">Eindbesluit:</h4>
                <div className="bg-gray-950 rounded-md p-4 text-sm text-gray-200 whitespace-pre-wrap border border-gray-800">
                  {result.final_decision}
                </div>
              </div>

              {result.individual_outputs &&
                Object.keys(result.individual_outputs).length > 0 && (
                  <div className="pt-2 border-t border-gray-800 space-y-2">
                    <h4 className="font-semibold text-gray-200">
                      Individuele Inbreng per Agent:
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
                Onderwerp (Topic)
              </label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Bijv. Uitbreiding naar de Duitse markt"
                className="w-full rounded-md border border-gray-700 bg-gray-800 text-gray-100 p-2 placeholder-gray-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-1">
                Taakbeschrijving
              </label>
              <textarea
                value={taskDescription}
                onChange={(e) => setTaskDescription(e.target.value)}
                rows={3}
                placeholder="Geef een gedetailleerde toelichting over de situatie en vraagstelling..."
                className="w-full rounded-md border border-gray-700 bg-gray-800 text-gray-100 p-2 placeholder-gray-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">
                Deelnemende Agents
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
              {loading ? "Bezig met vergaderen... dit kan enkele minuten duren" : "Besluit Starten"}
            </button>
          </form>
        </div>

        {/* Decision history */}
        <div>
          <h2 className="text-xl font-bold mb-4">Besluithistorie</h2>
          <div className="space-y-4">
            {history.length === 0 && (
              <p className="text-gray-500 text-sm">Nog geen besluiten gevonden.</p>
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
                      {new Date(item.timestamp).toLocaleString("nl-BE")}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mt-2">
                    Betrokkenen:{" "}
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
                      {isExpanded ? "▲ Lees minder" : "▼ Lees meer"}
                    </button>
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
