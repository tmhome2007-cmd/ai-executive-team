/** Office navigation and presentation of recorded organizational state. */
"use client";
import AiReport from "./ai-report";

import { useState } from "react";
import OfficeWorkforce from "./office-workforce";
import CharacterAvatar from "./character-avatar";
import type { ExecutiveProfile } from "./company-records";

type Destination = "decisions" | "actions" | "resources" | "activity";
interface Decision {
  id: number;
  topic: string;
  timestamp: string;
  agents_involved: string;
  decision_outcome: string;
  approval_status?: string;
  meeting_type?: string;
}
interface Action {
  id: number;
  proposed_by: string;
  action_description: string;
  status: string;
  source_decision_id?: number | null;
  actual_outcome?: string | null;
}
interface Resource {
  id: number;
  requested_by: string;
  resource_name: string;
  status: string;
}
interface Followup {
  id: number;
  reason: string;
  severity: string;
  source_decision_id?: number | null;
}

const EXECUTIVES = [
  {
    key: "ceo",
    title: "CEO",
    name: "Chief Executive",
    department: "Leadership",
    initials: "CE",
    color: "#5eead4",
    remit: "Company direction and coordination",
  },
  {
    key: "board_director",
    title: "Board Director",
    name: "Board Director",
    department: "Leadership",
    initials: "BD",
    color: "#94a3b8",
    remit: "Oversight and strategic challenge",
  },
  {
    key: "cfo",
    title: "CFO",
    name: "Chief Financial Officer",
    department: "Finance & risk",
    initials: "CF",
    color: "#fbbf24",
    remit: "Capital, costs and financial evidence",
  },
  {
    key: "general_counsel",
    title: "General Counsel",
    name: "General Counsel",
    department: "Finance & risk",
    initials: "GC",
    color: "#c4b5fd",
    remit: "Legal review and constraints",
  },
  {
    key: "coo",
    title: "COO",
    name: "Chief Operating Officer",
    department: "Operations",
    initials: "CO",
    color: "#93c5fd",
    remit: "Preparation, delivery and dependencies",
  },
  {
    key: "chro",
    title: "CHRO",
    name: "Chief Human Resources Officer",
    department: "Operations",
    initials: "HR",
    color: "#f9a8d4",
    remit: "People and organizational capacity",
  },
  {
    key: "cso",
    title: "CSO",
    name: "Chief Strategy Officer",
    department: "Growth",
    initials: "CS",
    color: "#a5b4fc",
    remit: "Research and strategy proposals",
  },
  {
    key: "cmo",
    title: "CMO",
    name: "Chief Marketing Officer",
    department: "Growth",
    initials: "CM",
    color: "#fdba74",
    remit: "Marketing and experiment design",
  },
  {
    key: "cco",
    title: "CCO",
    name: "Chief Compliance & Operations Officer",
    department: "Finance & risk",
    initials: "CC",
    color: "#bef264",
    remit: "Security compliance and risk-managed operations",
  },
  {
    key: "cto",
    title: "CTO",
    name: "Chief Technology Officer",
    department: "Product & technology",
    initials: "CT",
    color: "#67e8f9",
    remit: "Technical feasibility and implementation",
  },
  {
    key: "cpo",
    title: "CPO",
    name: "Chief Product Officer",
    department: "Product & technology",
    initials: "CP",
    color: "#d8b4fe",
    remit: "Product direction and customer value",
  },
];
const FLOORS = [
  { label: "03", name: "Executive floor", rooms: ["Leadership", "Finance & risk"] },
  { label: "02", name: "Company floor", rooms: ["Operations", "Growth"] },
  { label: "01", name: "Build floor", rooms: ["Product & technology"] },
];
const belongsTo = (participants: string, key: string) =>
  participants
    .split(",")
    .map((p) => p.trim().toLowerCase())
    .includes(key);

export default function VirtualOffice({
  decisions,
  actions,
  resources,
  followups,
  available,
  errors,
  onNavigate,
  onMemory,
  profiles,
  onRecords,
  apiKey,
  onAuthFailure,
}: {
  apiKey: string | null;
  onAuthFailure: () => void;
  profiles: Record<string, ExecutiveProfile>;
  onRecords: () => void;
  decisions: Decision[];
  actions: Action[];
  resources: Resource[];
  followups: Followup[];
  available: {
    decisions: boolean;
    actions: boolean;
    resources: boolean;
    followups: boolean;
  };
  errors: boolean;
  onNavigate: (view: Destination) => void;
  onMemory: (executive: string) => void;
}) {
  const [selected, setSelected] = useState("ceo");
  const [floor, setFloor] = useState("all");
  const executive = EXECUTIVES.find((e) => e.key === selected)!;
  const executiveDecisions = decisions.filter((d) =>
    belongsTo(d.agents_involved, selected),
  );
  const executiveActions = actions.filter(
    (a) => a.proposed_by.toLowerCase() === selected,
  );
  const executiveResources = resources.filter(
    (r) => r.requested_by.toLowerCase() === selected,
  );
  const executing = actions.filter((a) => a.status === "executing");

  return (
    <section aria-label="Virtual office" className="space-y-6">
      <div className="office-intro">
        <div>
          <p className="text-teal-300 text-xs uppercase tracking-widest">
            The company, in view
          </p>
          <h2 className="text-2xl font-semibold mt-2">Virtual office</h2>
          <p className="text-sm text-gray-400 mt-2 max-w-2xl">
            Explore departments and select an executive to inspect recorded work. Floors
            organize existing roles; avatars represent AI executives.
          </p>
        </div>
        <div className="office-presence">
          <span className="office-dot" />
          {available.actions
            ? `${executing.length} recorded executions in progress`
            : "Execution state unavailable"}
        </div>
      </div>
      <p className="text-xs text-gray-500">
        This view uses the latest loaded records, not live presence or a conversation
        stream. Decision history covers 20 records. Use Refresh company data to update.
      </p>
      {errors && (
        <p role="alert" className="text-amber-300">
          Some office data is unavailable or stale. Refresh before relying on these
          records.
        </p>
      )}
      <div className="office-layout">
        <div className="space-y-5">
          <div className="flex flex-wrap gap-2" aria-label="Office floor filters">
            {[{ label: "all", name: "All floors" }, ...FLOORS].map((f) => (
              <button
                key={f.label}
                onClick={() => setFloor(f.label)}
                aria-pressed={floor === f.label}
                className={`office-filter ${floor === f.label ? "office-filter-active" : ""}`}
              >
                {f.name}
              </button>
            ))}
          </div>
          {FLOORS.filter((f) => floor === "all" || floor === f.label).map((f) => (
            <section key={f.label} className="office-floor" aria-label={f.name}>
              <header className="flex items-center gap-3 mb-5">
                <span className="office-floor-number">{f.label}</span>
                <div>
                  <h3 className="font-semibold">{f.name}</h3>
                  <p className="text-xs text-gray-500">{f.rooms.join(" · ")}</p>
                </div>
              </header>
              <div className="office-rooms">
                {f.rooms.map((room) => (
                  <div className="office-room" key={room}>
                    <h4 className="text-xs uppercase tracking-wider text-gray-400 mb-4">
                      {room}
                    </h4>
                    <div className="flex flex-wrap gap-3">
                      {EXECUTIVES.filter((e) => e.department === room).map((e) => {
                        const active = actions.some(
                          (a) =>
                            a.proposed_by.toLowerCase() === e.key &&
                            a.status === "executing",
                        );
                        const proposals = actions.filter(
                          (a) =>
                            a.proposed_by.toLowerCase() === e.key &&
                            a.status === "pending",
                        ).length;
                        return (
                          <button
                            key={e.key}
                            aria-label={`Inspect ${e.title}`}
                            aria-pressed={selected === e.key}
                            onClick={() => setSelected(e.key)}
                            className={`office-desk ${selected === e.key ? "office-desk-selected" : ""}`}
                          >
                            <CharacterAvatar
                              compact
                              presentation={profiles[e.key]?.presentation}
                              name={profiles[e.key]?.name || e.title}
                            />
                            <strong className="block text-sm mt-2">
                              {profiles[e.key]?.name || e.title}
                            </strong>
                            <span className="block text-xs text-gray-400">
                              {e.title}
                            </span>
                            <span className="block text-xs text-gray-400 mt-1">
                              {!available.actions
                                ? "State unavailable"
                                : active
                                  ? "Executing"
                                  : proposals
                                    ? `${proposals} pending proposals`
                                    : "No active execution"}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          ))}
          <article className="command-card">
            <div className="flex justify-between gap-3 items-center">
              <h3 className="font-semibold">Boardroom · recorded meetings</h3>
              <button className="command-link" onClick={() => onNavigate("decisions")}>
                Open decisions →
              </button>
            </div>
            {!available.decisions ? (
              <p className="text-gray-400 mt-4">Meeting history unavailable.</p>
            ) : decisions.length === 0 ? (
              <p className="text-gray-400 mt-4">
                No recorded meetings yet. Start one in Decisions.
              </p>
            ) : (
              decisions.slice(0, 4).map((d) => (
                <button
                  key={d.id}
                  className="office-record"
                  onClick={() => onNavigate("decisions")}
                >
                  <span className="text-teal-300">
                    #{d.id} · {d.topic}
                  </span>
                  <span className="text-xs text-gray-500 block mt-1">
                    {d.meeting_type?.replaceAll("_", " ") || "Meeting"} ·{" "}
                    {d.agents_involved.toUpperCase()} ·{" "}
                    {d.approval_status || "Unknown approval state"}
                  </span>
                </button>
              ))
            )}
          </article>
        </div>
        <aside
          className="command-card office-inspector"
          aria-label="Executive inspector"
        >
          <div className="flex items-center gap-4">
            <CharacterAvatar
              compact
              presentation={profiles[selected]?.presentation}
              name={profiles[selected]?.name || executive.title}
            />
            <div>
              <p className="text-teal-300 text-xs">{executive.department}</p>
              <h3 className="text-xl font-semibold">{executive.title}</h3>
            </div>
          </div>
          <p className="font-medium mt-4">
            {profiles[selected]?.name || "Name unavailable until profiles load"}
          </p>
          <p className="text-sm text-gray-400 mt-1">
            {profiles[selected]?.goal || executive.remit}
          </p>
          <button className="command-link" onClick={() => onMemory(selected)}>
            Review {executive.title} memory →
          </button>
          {profiles[selected] && (
            <details className="mt-4">
              <summary className="text-sm text-teal-300 cursor-pointer">
                Background & role personality
              </summary>
              <p className="text-sm text-gray-400 whitespace-pre-wrap mt-3">
                {profiles[selected].backstory}
              </p>
            </details>
          )}
          <button className="command-link block" onClick={onRecords}>
            Recorded contributions & timeline →
          </button>
          <h4 className="office-subheading">Action records</h4>
          {!available.actions ? (
            <p className="text-sm text-gray-400">Actions unavailable.</p>
          ) : executiveActions.length === 0 ? (
            <p className="text-sm text-gray-400">
              No actions for this executive in the loaded records.
            </p>
          ) : (
            executiveActions.slice(0, 5).map((a) => (
              <button
                key={a.id}
                className="office-record"
                onClick={() => onNavigate("actions")}
              >
                <span>
                  #{a.id} · {a.action_description}
                </span>
                <span className="text-xs text-teal-300 block mt-1">
                  {a.status.replaceAll("_", " ")}
                  {a.source_decision_id ? ` · Decision #${a.source_decision_id}` : ""}
                </span>
                {a.actual_outcome && (
                  <span className="block text-xs text-gray-400 mt-1">
                    Observed: {a.actual_outcome}
                  </span>
                )}
              </button>
            ))
          )}
          <h4 className="office-subheading">Resource requests</h4>
          {!available.resources ? (
            <p className="text-sm text-gray-400">Resources unavailable.</p>
          ) : executiveResources.length === 0 ? (
            <p className="text-sm text-gray-400">
              No outstanding resource requests in the loaded records.
            </p>
          ) : (
            executiveResources.map((r) => (
              <button
                className="office-record"
                key={r.id}
                onClick={() => onNavigate("resources")}
              >
                {r.resource_name}
                <span className="text-xs text-gray-500 block">{r.status}</span>
              </button>
            ))
          )}
          <h4 className="office-subheading">Recorded meeting contribution</h4>
          {!available.decisions ? (
            <p className="text-sm text-gray-400">Meetings unavailable.</p>
          ) : executiveDecisions.length === 0 ? (
            <p className="text-sm text-gray-400">
              No participation recorded in the recent meetings.
            </p>
          ) : (
            <>
              <p className="text-sm text-teal-300">
                #{executiveDecisions[0].id} · {executiveDecisions[0].topic}
              </p>
              <details className="mt-3">
                <summary className="text-sm cursor-pointer">
                  Read the meeting’s final report
                </summary>
                <AiReport text={executiveDecisions[0].decision_outcome} />
              </details>
              <p className="text-xs text-gray-500 mt-2">
                Collective meeting result; not an individual message or live chat.
              </p>
            </>
          )}
        </aside>
      </div>
      <OfficeWorkforce
        key={floor}
        apiKey={apiKey}
        floor={floor}
        onAuthFailure={onAuthFailure}
      />
      <article className="command-card">
        <h3 className="font-semibold">Observation desk · open follow-ups</h3>
        {!available.followups ? (
          <p className="text-gray-400 mt-3">Follow-ups unavailable.</p>
        ) : followups.length === 0 ? (
          <p className="text-gray-400 mt-3">
            No open observations in the loaded records.
          </p>
        ) : (
          followups.slice(0, 5).map((f) => (
            <button
              className="office-record"
              key={f.id}
              onClick={() => onNavigate("activity")}
            >
              <span className="text-xs uppercase text-amber-300">{f.severity}</span>
              <span className="block text-sm mt-1">{f.reason}</span>
            </button>
          ))
        )}
        <button className="command-link" onClick={() => onNavigate("activity")}>
          Review follow-ups →
        </button>
      </article>
    </section>
  );
}
