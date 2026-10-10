/** Owner-reviewed versioned procedures; acceptance never grants execution authority. */
"use client";

import { useCallback, useEffect, useState } from "react";
const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
interface Evidence {
  review_id: number;
  sample_id: number;
  brief_id: number;
  rubric_digest: string;
  title: string;
}
interface Skill {
  uses: { brief_id: number; state: string; owner_assessment: string }[];
  id: number;
  skill_key: string;
  version: number;
  name: string;
  procedure: string;
  prerequisites: string;
  limitations: string;
  checks: string[];
  service_key: string;
  deliverable_kind: string;
  state: string;
  state_version: number;
  usable: boolean;
  unavailable_reason: string;
  evidence: Evidence[];
  scope: string;
}

export default function ExecutiveSkills({
  apiKey,
  onAuthFailure,
}: {
  apiKey: string;
  onAuthFailure: () => void;
}) {
  const [items, setItems] = useState<Skill[]>([]);
  const [offset, setOffset] = useState(0);
  const [sources, setSources] = useState<Evidence[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [key, setKey] = useState("");
  const [name, setName] = useState("");
  const [procedure, setProcedure] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useCallback(
    async (path: string, body?: unknown, signal?: AbortSignal) => {
      const response = await fetch(API + path, {
        method: body ? "POST" : "GET",
        signal,
        cache: "no-store",
        headers: {
          "X-API-Key": apiKey,
          ...(body ? { "Content-Type": "application/json" } : {}),
        },
        ...(body ? { body: JSON.stringify(body) } : {}),
      });
      if (response.status === 401) {
        onAuthFailure();
        throw new Error("Sign in again.");
      }
      const data = await response.json().catch(() => null);
      if (!response.ok)
        throw new Error(
          typeof data?.detail === "string"
            ? data.detail
            : "Skill request failed. Refresh the updated backend.",
        );
      return data;
    },
    [apiKey, onAuthFailure],
  );
  const load = useCallback(
    async (signal?: AbortSignal) => {
      const [skills, evidence] = await Promise.all([
        request(`/skills?limit=100&offset=${offset}`, undefined, signal),
        request("/skills/evidence", undefined, signal),
      ]);
      setItems(skills);
      setSources(evidence);
    },
    [request, offset],
  );
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      request(`/skills?limit=100&offset=${offset}`, undefined, controller.signal),
      request("/skills/evidence", undefined, controller.signal),
    ])
      .then(([skills, evidence]) => {
        if (!controller.signal.aborted) {
          setItems(skills);
          setSources(evidence);
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [request, offset]);
  async function act(operation: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await operation();
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Skill request failed");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="rounded-xl border border-gray-700 p-4 space-y-4"
      aria-label="Executive skill library"
    >
      <h2 className="text-2xl font-semibold">Executive skill library</h2>
      <p>
        Review two examples → draft a procedure → accept this version → reuse on a new
        exercise.
      </p>
      <p className="text-sm">
        Private text only · €0 · no tools or launch permission. Practice does not train
        the model or establish general competence.
      </p>
      {error && (
        <p role="alert" className="text-red-300">
          {error}
        </p>
      )}
      <button type="button" disabled={busy} onClick={() => act(async () => undefined)}>
        Refresh skills and evidence
      </button>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          act(async () => {
            await request("/skills", {
              skill_key: key,
              name,
              procedure,
              prerequisites:
                "A matching owner-approved private exercise with different supplied facts.",
              limitations:
                "Private text only. Owner review required for each sample; no tools, money, publication or general competence.",
              review_ids: selected,
            });
            setProcedure("");
          });
        }}
      >
        <fieldset disabled={busy} className="space-y-3">
          <legend>Propose a procedure version</legend>
          <label className="block">
            Skill key
            <input
              className="agile-input w-full"
              required
              pattern="[a-z][a-z0-9-]{0,79}"
              maxLength={80}
              placeholder="private-evidence-summary"
              value={key}
              onChange={(e) => setKey(e.target.value)}
            />
          </label>
          <label className="block">
            Procedure name
            <input
              className="agile-input w-full"
              required
              maxLength={200}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <p>
            Select two passing reviews from different exercises with the same rubric and
            different facts. Open their saved samples in Business research before
            accepting a procedure.
          </p>
          {sources.map((source) => (
            <label className="block" key={source.review_id}>
              <input
                type="checkbox"
                checked={selected.includes(source.review_id)}
                disabled={!selected.includes(source.review_id) && selected.length >= 2}
                onChange={(e) =>
                  setSelected(
                    e.target.checked
                      ? [...selected, source.review_id]
                      : selected.filter((id) => id !== source.review_id),
                  )
                }
              />{" "}
              Review #{source.review_id} · sample #{source.sample_id} · brief #
              {source.brief_id} · {source.title} · rubric{" "}
              {source.rubric_digest.slice(0, 12)}
            </label>
          ))}
          {sources.length === 0 && (
            <p>
              No eligible passing reviews yet. Review two structured exercises with
              different supplied facts first.
            </p>
          )}
          <button
            type="button"
            disabled={selected.length !== 2 || !key || !name}
            onClick={() =>
              act(() =>
                request("/skills/draft", {
                  skill_key: key,
                  name,
                  review_ids: selected,
                }),
              )
            }
          >
            Ask CSO to draft a proposed procedure
          </button>
          <label className="block">
            Or write the procedure
            <textarea
              className="agile-input w-full"
              rows={5}
              maxLength={8000}
              value={procedure}
              onChange={(e) => setProcedure(e.target.value)}
            />
          </label>
          <button type="submit" disabled={selected.length !== 2 || !procedure.trim()}>
            Save proposed version
          </button>
        </fieldset>
      </form>
      <div className="flex gap-3">
        <button
          disabled={busy || offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 100))}
        >
          Newer skill versions
        </button>
        <button
          disabled={busy || items.length < 100}
          onClick={() => setOffset(offset + 100)}
        >
          Older skill versions
        </button>
      </div>
      {items.map((skill) => (
        <article
          className="border border-gray-700 rounded p-3 space-y-2"
          key={skill.id}
        >
          <h3 className="text-xl font-semibold">
            {skill.name} · version {skill.version} · #{skill.id}
          </h3>
          <p>
            {skill.state}
            {skill.usable
              ? " · available for compatible private exercises"
              : " · " + skill.unavailable_reason}
          </p>
          <p className="text-sm">
            {skill.service_key} · {skill.deliverable_kind} · evidence{" "}
            {skill.evidence
              .map(
                (x) =>
                  `review #${x.review_id} / sample #${x.sample_id} / brief #${x.brief_id}`,
              )
              .join(", ")}
          </p>
          <details>
            <summary>Procedure, prerequisites and exact rubric</summary>
            <pre className="whitespace-pre-wrap">{skill.procedure}</pre>
            <p>Prerequisites: {skill.prerequisites}</p>
            <p>Limits: {skill.limitations}</p>
            <ul>
              {skill.checks.map((check) => (
                <li key={check}>{check}</li>
              ))}
            </ul>
          </details>
          {skill.state === "proposed" && (
            <button
              disabled={busy}
              onClick={() =>
                act(() =>
                  request(`/skills/${skill.id}/decision`, {
                    expected_version: skill.state_version,
                    state: "accepted",
                    note: "Owner accepted this private procedure version; source reviews remain separately recorded. Private practice only.",
                  }),
                )
              }
            >
              Accept this private procedure version
            </button>
          )}
          {skill.state !== "revoked" && (
            <button
              disabled={busy}
              onClick={() =>
                act(() =>
                  request(`/skills/${skill.id}/decision`, {
                    expected_version: skill.state_version,
                    state: "revoked",
                    note: "Owner revoked this version; earlier samples remain preserved.",
                  }),
                )
              }
            >
              Revoke version
            </button>
          )}
          {skill.uses?.map((use) => (
            <p key={use.brief_id} className="text-sm">
              Reused in brief #{use.brief_id} · {use.state} · owner assessment:{" "}
              {use.owner_assessment}
            </p>
          ))}
          {skill.usable && (
            <p className="text-sm">
              Select version #{skill.id} in a new research-ready practice plan. Match
              this service, format and every check; use different supplied facts.
            </p>
          )}
        </article>
      ))}
    </section>
  );
}
