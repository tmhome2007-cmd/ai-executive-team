/** Grouped workspace navigation and consistent owner controls, without new authority. */
"use client";
import { useRef, useState, type ReactNode } from "react";
const GROUPS = [
  { title: "Workspace", keys: ["overview", "office", "records", "activity"] },
  {
    title: "Direction & delivery",
    keys: ["goals", "decisions", "actions", "resources", "treasury", "work", "boards"],
  },
  { title: "Research & learning", keys: ["business", "experiments", "knowledge"] },
  { title: "Administration", keys: ["system"] },
];
const DESCRIPTIONS: Record<string, string> = {
  overview: "A clear view of what matters, and what needs you next.",
  office: "Your executives, their workspace and recorded activity.",
  records: "Published conversations and the story behind each decision.",
  activity: "Follow-up observations, executive memory and recorded work.",
  goals: "Give the company direction and define what success looks like.",
  decisions: "Review the reasoning. Choose the direction.",
  actions: "Review proposals, follow execution and measure the result.",
  resources: "Resolve the access, data and resources the team needs.",
  treasury: "Capital, reservations and costs, with a clear paper trail.",
  work: "Evidence, plans, discussions and operating controls.",
  boards: "Your development work and the company’s work, in one place.",
  business: "Explore possibilities. Practice privately. Review the evidence.",
  experiments: "Turn a hypothesis into a measured observation.",
  knowledge: "Follow the connections. Know where the information came from.",
  system: "Runtime health and the controls behind your company.",
};
function Icon({ kind }: { kind: string }) {
  const paths: Record<string, string> = {
    overview: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
    office: "M4 21V7l8-4 8 4v14 M9 21v-5h6v5 M8 9h1 M15 9h1 M8 12h1 M15 12h1",
    records: "M4 4h16v12H9l-5 4z M8 8h8 M8 12h5",
    activity: "M3 12h4l3-7 4 14 3-7h4",
    goals: "M12 3v4 M12 17v4 M3 12h4 M17 12h4 M7 7l10 10 M7 17L17 7",
    decisions: "M6 3h12v18H6z M9 8h6 M9 12h6 M9 16h3",
    actions: "M8 4l12 8-12 8z",
    resources: "M3 7l9-4 9 4-9 5z M3 7v10l9 4 9-4V7 M12 12v9",
    treasury: "M3 6h18v14H3z M3 9h18 M16 13h5v4h-5z",
    work: "M3 8h18v13H3z M8 8V4h8v4 M3 13h18 M10 13v3h4v-3",
    boards: "M3 4h18v16H3z M9 4v16 M15 4v16 M5 8h2 M11 8h2 M17 8h2",
    business: "M4 20h16 M7 16l4-5 3 2 6-8 M16 5h4v4",
    experiments: "M9 3h6 M10 3v7l-6 9v2h16v-2l-6-9V3 M8 15h8",
    knowledge: "M4 4h7v16H4z M13 4h7v16h-7z M11 6h2 M11 18h2",
    system: "M4 4h16v12H4z M8 21h8 M12 16v5 M8 8h8 M8 12h4",
  };
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinejoin="round"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d={paths[kind] || paths.overview} />
    </svg>
  );
}
export default function DashboardShell({
  view,
  views,
  onNavigate,
  onRefresh,
  refreshing,
  health,
  sandboxMode,
  onToggleMode,
  togglingMode,
  modeError,
  children,
}: {
  view: string;
  views: readonly (readonly [string, string])[];
  onNavigate: (view: string) => void;
  onRefresh: () => void;
  refreshing: boolean;
  health: string;
  sandboxMode: boolean | null;
  onToggleMode: () => void;
  togglingMode: boolean;
  modeError: string | null;
  children: ReactNode;
}) {
  const [menuOpen, setMenuOpen] = useState(false),
    [filter, setFilter] = useState("");
  const menuButton = useRef<HTMLButtonElement>(null);
  const current = views.find(([key]) => key === view)?.[1] || "Overview";
  function navigate(key: string) {
    onNavigate(key);
    setMenuOpen(false);
    setFilter("");
    window.scrollTo({ top: 0, behavior: "instant" });
  }
  return (
    <div
      className="dashboard-shell"
      onKeyDown={(e) => {
        if (e.key === "Escape" && menuOpen) {
          setMenuOpen(false);
          menuButton.current?.focus();
        }
      }}
    >
      <a className="dashboard-skip" href="#company-content">
        Skip to workspace
      </a>
      <aside className={`dashboard-sidebar ${menuOpen ? "sidebar-open" : ""}`}>
        <div className="dashboard-brand">
          <span className="brand-monogram">
            AE<span>·</span>
          </span>
          <div>
            <strong>Executive Team</strong>
            <span>Company workspace</span>
          </div>
        </div>
        <label className="nav-search">
          <Icon kind="business" />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Find a view…"
            aria-label="Find a company view"
          />
        </label>
        <nav aria-label="Company views" id="company-navigation">
          {GROUPS.map((g) => (
            <div className="nav-group" key={g.title}>
              <p>{g.title}</p>
              {views
                .filter(
                  ([key, label]) =>
                    g.keys.includes(key) &&
                    label.toLowerCase().includes(filter.toLowerCase()),
                )
                .map(([key, label]) => (
                  <button
                    key={key}
                    onClick={() => navigate(key)}
                    aria-current={view === key ? "page" : undefined}
                  >
                    <Icon kind={key} />
                    <span>{label}</span>
                    {view === key && (
                      <span className="nav-current-dot" aria-hidden="true" />
                    )}
                  </button>
                ))}
            </div>
          ))}
          {filter &&
            !views.some(([, label]) =>
              label.toLowerCase().includes(filter.toLowerCase()),
            ) && <p className="nav-empty">No matching views.</p>}
        </nav>
        <div className="sidebar-owner">
          <span className="owner-avatar">O</span>
          <div>
            <strong>Owner workspace</strong>
            <span>You review. You decide.</span>
          </div>
        </div>
      </aside>
      <div className="dashboard-main">
        <header className="dashboard-topbar">
          <div className="topbar-location">
            <button
              ref={menuButton}
              className="mobile-menu"
              aria-label="Toggle company navigation"
              aria-expanded={menuOpen}
              aria-controls="company-navigation"
              onClick={() => setMenuOpen((v) => !v)}
            >
              ☰
            </button>
            <span className="topbar-company">Company</span>
            <span className="topbar-divider">/</span>
            <strong>{current}</strong>
          </div>
          <div className="topbar-controls">
            <span className="runtime-status">
              <span
                className={
                  health === "healthy" || health === "ok"
                    ? "status-dot"
                    : "status-dot status-dot-muted"
                }
              />
              {health}
            </span>
            <button
              className={`mode-pill ${sandboxMode === false ? "mode-live" : ""}`}
              onClick={onToggleMode}
              disabled={togglingMode}
              title="Change execution mode using the existing owner confirmation"
            >
              {togglingMode
                ? "Switching…"
                : sandboxMode === null
                  ? "Checking mode"
                  : sandboxMode
                    ? "Sandbox mode"
                    : "Live execution"}
            </button>
          </div>
        </header>
        <main id="company-content" tabIndex={-1} className="dashboard-content">
          {modeError && (
            <p role="alert" className="dashboard-alert">
              {modeError}
            </p>
          )}
          {sandboxMode === false && (
            <p className="dashboard-alert">
              Live execution: approved actions can run on this machine. Change execution
              mode above to return to sandbox.
            </p>
          )}
          <div className="workspace-heading">
            <div>
              <p className="workspace-eyebrow">YOUR COMPANY, CONNECTED</p>
              <h1>{current}</h1>
              <p>{DESCRIPTIONS[view]}</p>
            </div>
            <button
              className="workspace-refresh"
              onClick={onRefresh}
              disabled={refreshing}
            >
              <span aria-hidden="true">↻</span>
              {refreshing ? "Refreshing…" : "Refresh company data"}
            </button>
          </div>
          {children}
          <footer className="workspace-footer">
            <span>AI Executive Team</span>
            <span>Evidence before confidence. Owner approval before action.</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
