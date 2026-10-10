/** Read-only, source-explained company records with explicit context exclusions. */
"use client";
import { useCallback, useEffect, useRef, useState } from "react";
const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
const KINDS = [
  "goal",
  "decision",
  "action",
  "outcome",
  "lesson",
  "skill",
  "evidence",
  "brief",
  "sample",
  "review",
];
interface Node {
  kind: string;
  id: number;
  title: string;
  excerpt?: string;
  status?: string;
  recorded_at?: string | null;
  warnings?: string[];
  context?: { eligible: boolean; reasons: string[]; scope: string } | null;
  approval_status?: string;
  category?: string;
}
interface Link {
  target: Node;
  relation: string;
  origin: string;
  recorded_at: string | null;
  claim: string;
  verification: string;
  available: boolean;
}
interface Page {
  items: Node[];
  has_more: boolean;
  retrieved_at: string;
  scope: string;
}
interface Detail {
  node: Node;
  details: Record<string, unknown>;
  links: Link[];
  has_more_links: boolean;
  omitted_link_groups: string[];
  truncated_fields: string[];
  retrieved_at: string;
  scope: string;
}
export default function CompanyKnowledge({
  apiKey,
  onAuthFailure,
}: {
  apiKey: string;
  onAuthFailure: () => void;
}) {
  const [query, setQuery] = useState(""),
    [applied, setApplied] = useState(""),
    [kind, setKind] = useState("all"),
    [mode, setMode] = useState("history"),
    [offset, setOffset] = useState(0),
    [revision, setRevision] = useState(0);
  const [page, setPage] = useState<Page | null>(null),
    [selected, setSelected] = useState<{ kind: string; id: number } | null>(null),
    [detail, setDetail] = useState<Detail | null>(null),
    [linkOffset, setLinkOffset] = useState(0);
  const [error, setError] = useState(""),
    [loading, setLoading] = useState(false),
    [detailLoading, setDetailLoading] = useState(false),
    [trail, setTrail] = useState<{ kind: string; id: number }[]>([]);
  const detailRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (detail) detailRef.current?.focus();
  }, [detail]);
  const request = useCallback(
    async (path: string, signal: AbortSignal) => {
      const r = await fetch(API + path, {
        signal,
        cache: "no-store",
        headers: { "X-API-Key": apiKey },
      });
      if (r.status === 401) {
        onAuthFailure();
        throw new Error("Sign in again.");
      }
      const data = await r.json().catch(() => null);
      if (!r.ok)
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : "Knowledge records unavailable. Check the updated backend.",
        );
      return data;
    },
    [apiKey, onAuthFailure],
  );
  useEffect(() => {
    const c = new AbortController();
    let active = true;
    async function load() {
      setLoading(true);
      setError("");
      setPage(null);
      try {
        const data = await request(
          `/company/knowledge?query=${encodeURIComponent(applied)}&kind=${kind}&mode=${mode}&limit=30&offset=${offset}`,
          c.signal,
        );
        if (active) setPage(data);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Request failed");
      } finally {
        if (active) setLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
      c.abort();
    };
  }, [request, applied, kind, mode, offset, revision]);
  useEffect(() => {
    if (!selected) return;
    const c = new AbortController();
    let active = true;
    async function load() {
      setDetailLoading(true);
      setDetail(null);
      try {
        const data = await request(
          `/company/knowledge/${selected!.kind}/${selected!.id}?link_offset=${linkOffset}`,
          c.signal,
        );
        if (active) setDetail(data);
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : "Record unavailable");
      } finally {
        if (active) setDetailLoading(false);
      }
    }
    void load();
    return () => {
      active = false;
      c.abort();
    };
  }, [request, selected, linkOffset, revision]);
  function open(node: Node) {
    if (selected) setTrail((old) => [...old.slice(-19), selected]);
    setSelected({ kind: node.kind, id: node.id });
    setLinkOffset(0);
    setError("");
  }
  function badges(node: Node) {
    return (
      <>
        <p>
          {node.kind} #{node.id} · {node.status || "state unknown"}
          {node.approval_status && ` · owner direction: ${node.approval_status}`}
          {node.category && ` · source category: ${node.category}`}
        </p>
        <p className="text-sm text-gray-400">
          Record/source time: {node.recorded_at || "unknown — no timestamp stored"}
        </p>
        {node.context && (
          <p>
            Current agent memory context:{" "}
            {node.context.eligible ? "eligible as advisory context" : "withheld"}
            {node.context.reasons.length > 0 && ` (${node.context.reasons.join(", ")})`}
          </p>
        )}
        {node.warnings && node.warnings.length > 0 && (
          <p className="text-amber-300">Review notes: {node.warnings.join(" · ")}</p>
        )}
      </>
    );
  }
  return (
    <section aria-label="Company knowledge" className="command-card space-y-4">
      <h2>Company knowledge</h2>
      <p>
        Follow recorded goals, decisions, actions, results, lessons and skills. Links
        explain where a record came from; they do not prove its claims or grant
        approval.
      </p>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied(query.trim());
          setOffset(0);
          setRevision((v) => v + 1);
        }}
      >
        <label className="block">
          Search record titles and excerpts
          <input
            className="command-input"
            value={query}
            maxLength={200}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <label className="block">
          Record kind
          <select
            className="command-input"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value);
              setOffset(0);
            }}
          >
            <option value="all">All records</option>
            {KINDS.map((k) => (
              <option key={k}>{k}</option>
            ))}
          </select>
        </label>
        <label className="block">
          Memory visibility
          <select
            className="command-input"
            value={mode}
            onChange={(e) => {
              setMode(e.target.value);
              setOffset(0);
            }}
          >
            <option value="history">History, including withheld lessons</option>
            <option value="current">Exclude withheld lessons</option>
          </select>
        </label>
        <button className="office-filter" disabled={loading}>
          Search knowledge
        </button>
        <button
          type="button"
          className="office-filter"
          onClick={() => setRevision((v) => v + 1)}
          disabled={loading}
        >
          Refresh knowledge
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
      {loading && <p role="status">Loading records…</p>}
      {page && (
        <>
          <p className="text-sm text-gray-400">
            Retrieved: {page.retrieved_at}. {page.scope}
          </p>
          {page.items.length === 0 && <p>No matching records on this page.</p>}
          <div className="space-y-3">
            {page.items.map((n) => (
              <article
                key={`${n.kind}:${n.id}`}
                className="command-card space-y-2 break-words"
              >
                <h3>{n.title}</h3>
                {badges(n)}
                <p className="whitespace-pre-wrap">{n.excerpt}</p>
                <button className="office-filter" onClick={() => open(n)}>
                  Inspect {n.kind} #{n.id}
                </button>
              </article>
            ))}
          </div>
          <div className="flex gap-2">
            <button
              className="office-filter"
              disabled={offset === 0 || loading}
              onClick={() => setOffset(Math.max(0, offset - 30))}
            >
              Previous records
            </button>
            <button
              className="office-filter"
              disabled={!page.has_more || loading}
              onClick={() => setOffset(offset + 30)}
            >
              Next records
            </button>
          </div>
        </>
      )}
      {selected && (
        <section
          aria-label="Knowledge record detail"
          ref={detailRef}
          tabIndex={-1}
          className="command-card space-y-3 break-words"
        >
          <div className="flex gap-2">
            <button
              className="office-filter"
              disabled={trail.length === 0}
              onClick={() => {
                const old = trail[trail.length - 1];
                setTrail((t) => t.slice(0, -1));
                setSelected(old);
                setLinkOffset(0);
              }}
            >
              Back to previous record
            </button>
            <button
              className="office-filter"
              onClick={() => {
                setSelected(null);
                setDetail(null);
                setTrail([]);
                setLinkOffset(0);
              }}
            >
              Close record
            </button>
          </div>
          {detailLoading && <p role="status">Loading provenance…</p>}
          {detail && (
            <>
              <h3>{detail.node.title}</h3>
              {badges(detail.node)}
              <p className="text-sm text-gray-400">
                Retrieved: {detail.retrieved_at}. {detail.scope}
              </p>
              <details>
                <summary>Saved record fields and corrections</summary>
                {detail.truncated_fields.length > 0 && (
                  <p>
                    Field excerpts capped at 12,000 characters:{" "}
                    {detail.truncated_fields.join(", ")}. Open the original company
                    record to review the remaining content.
                  </p>
                )}
                {Object.entries(detail.details).map(([name, value]) => (
                  <div key={name} className="my-2">
                    <h4>{name.replaceAll("_", " ")}</h4>
                    <pre className="whitespace-pre-wrap break-words font-sans">
                      {value === null
                        ? "unknown"
                        : typeof value === "object"
                          ? JSON.stringify(value, null, 2)
                          : String(value)}
                    </pre>
                  </div>
                ))}
              </details>
              <h4>Recorded relationships</h4>
              {detail.links.length === 0 && (
                <p>No recorded links on this page. Missing links are not inferred.</p>
              )}
              {detail.links.map((l, i) => (
                <article key={i} className="space-y-1 border-t border-gray-700 py-3">
                  <p>
                    {l.relation} → {l.target.kind} #{l.target.id}: {l.target.title}
                  </p>
                  <p className="text-sm text-gray-400">
                    Source: {l.origin} · recorded {l.recorded_at || "time unknown"} ·{" "}
                    {l.verification}
                  </p>
                  {l.claim && (
                    <p className="whitespace-pre-wrap">Recorded claim: {l.claim}</p>
                  )}
                  {l.target.context && badges(l.target)}
                  {l.available ? (
                    <button className="office-filter" onClick={() => open(l.target)}>
                      Follow {l.target.kind} #{l.target.id}
                    </button>
                  ) : (
                    <p>Link unavailable; the original provenance is preserved.</p>
                  )}
                </article>
              ))}
              {detail.omitted_link_groups.length > 0 && (
                <p>
                  Some large relationship groups were capped at 200 entries:{" "}
                  {detail.omitted_link_groups.join(", ")}. Narrow your search to inspect
                  additional records.
                </p>
              )}
              <div className="flex gap-2">
                <button
                  className="office-filter"
                  disabled={linkOffset === 0 || detailLoading}
                  onClick={() => setLinkOffset(Math.max(0, linkOffset - 30))}
                >
                  Previous links
                </button>
                <button
                  className="office-filter"
                  disabled={!detail.has_more_links || detailLoading}
                  onClick={() => setLinkOffset(linkOffset + 30)}
                >
                  Next links
                </button>
              </div>
            </>
          )}
        </section>
      )}
    </section>
  );
}
