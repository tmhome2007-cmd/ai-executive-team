/** Owner-controlled research, frozen private exercises and separately recorded assessments. */
"use client";
import { useCallback, useEffect, useState } from "react";
import { businessProposals } from "../lib/business-proposals";
import AiReport from "./ai-report";
import PracticeArtifacts from "./practice-artifacts";
import BusinessSourceContext from "./business-source-context";
const API = (process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
interface Attempt {
  id: number;
  attempt: number;
  sample: string;
  created_at: string;
  parent_sample_id: number | null;
  feedback_review_id: number | null;
  reviews: {
    id: number;
    supersedes_review_id: number | null;
    review: { results: boolean[]; evidence: string; assessment: string };
  }[];
}
interface Template {
  key: string;
  service_key: string;
  audience: string;
  supplied_facts: string;
  deliverable_kind: string;
  exercise: string;
  checks: string[];
}
interface Comparison {
  sample_id: number;
  parent_sample_id: number;
  before_review_id: number;
  after_review_id: number;
  comparable: boolean;
  improved_checks: string[];
  regressed_checks: string[];
  remaining_failures: string[];
  feedback_superseded: boolean;
}
interface PracticeEvidence {
  groups: {
    rubric_digest: string;
    service_key: string;
    assessed_examples: number;
    passing_examples: number;
    repeated_practice_evidence: boolean;
    brief_ids: number[];
  }[];
  scope: string;
}
interface Brief {
  skill_version?: {
    id: number;
    name: string;
    version: number;
    usable: boolean;
    unavailable_reason: string;
  } | null;
  practice_specification?: {
    structured: boolean;
    rubric_digest: string;
    specification: Template;
  };
  feedback_summary?: { comparisons: Comparison[]; scope: string };
  id: number;
  ignored_check_indices: number[];
  review_assessment: string | null;
  attempts: Attempt[];
  title: string;
  constraints: string;
  version: number;
  state: string;
  research_contract_version: number;
  source_ids: number[];
  research: string | null;
  sample: string | null;
  sample_display: string | null;
  selected_option: string | null;
  exercise: string | null;
  checks: string[] | null;
  observation_due_at: string | null;
  review: { results: boolean[]; evidence: string; assessment: string } | null;
}
interface Source {
  id: number;
  title: string;
  reference: string;
  summary: string;
  freshness: string;
  verification: string;
}
export default function BusinessDiscovery({
  apiKey,
  onAuthFailure,
}: {
  apiKey: string;
  onAuthFailure: () => void;
}) {
  const [items, setItems] = useState<Brief[]>([]),
    [selected, setSelected] = useState<Brief | null>(null);
  const [sources, setSources] = useState<Source[]>([]),
    [chosen, setChosen] = useState<number[]>([]);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [title, setTitle] = useState("AI-operated business research"),
    [constraints, setConstraints] = useState(
      "The agents should do the work; I review and approve. No assumed owner professional skills. Research and private practice only. No spending, paid services, publishing or customer contact.",
    );
  const [url, setUrl] = useState("");
  const [skillId, setSkillId] = useState("");
  const [skillOffset, setSkillOffset] = useState(0);
  const [moreSkills, setMoreSkills] = useState(false);
  const [acceptedSkills, setAcceptedSkills] = useState<
    {
      id: number;
      name: string;
      version: number;
      service_key: string;
      deliverable_kind: string;
      checks: string[];
      usable: boolean;
    }[]
  >([]);
  const [option, setOption] = useState(""),
    [exercise, setExercise] = useState(""),
    [checks, setChecks] = useState(""),
    [due, setDue] = useState("");
  const [results, setResults] = useState<(boolean | null)[]>([]),
    [evidence, setEvidence] = useState("");
  const [correcting, setCorrecting] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]),
    [practiceEvidence, setPracticeEvidence] = useState<PracticeEvidence | null>(null);
  const [service, setService] = useState("documentation"),
    [audience, setAudience] = useState(""),
    [facts, setFacts] = useState(""),
    [kind, setKind] = useState("guide");
  const request = useCallback(
    async (path: string, method = "GET", body?: unknown, signal?: AbortSignal) => {
      const response = await fetch(API + path, {
        method,
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
            : "Business research unavailable. Check the updated backend.",
        );
      return data;
    },
    [apiKey, onAuthFailure],
  );
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      request("/business-discovery", "GET", undefined, controller.signal),
      request("/evidence?limit=100", "GET", undefined, controller.signal),
      request(
        "/business-discovery/practice-templates",
        "GET",
        undefined,
        controller.signal,
      ),
      request(
        "/business-discovery/practice-evidence",
        "GET",
        undefined,
        controller.signal,
      ),
    ])
      .then(([briefs, records, presets, assessed]) => {
        setItems(briefs);
        setSources(records);
        setTemplates(presets);
        setPracticeEvidence(assessed);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [request]);
  const act = async (callback: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await callback();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setBusy(false);
    }
  };
  const update = (brief: Brief) => {
    setSelected(brief);
    setItems((previous) => [brief, ...previous.filter((b) => b.id !== brief.id)]);
    setResults(
      (brief.checks || []).map((_, i) =>
        brief.ignored_check_indices?.includes(i) ? false : null,
      ),
    );
    setEvidence("");
    setCorrecting(false);
  };
  const { sources: proposals, withheld } = businessProposals(selected?.research || "");
  const stage = (name: string) =>
    act(async () => {
      if (selected)
        update(
          await request(`/business-discovery/${selected.id}/${name}`, "POST", {
            expected_version: selected.version,
          }),
        );
    });
  return (
    <section className="space-y-5">
      <h2 className="text-2xl font-semibold">Business research & practice</h2>
      <p className="text-gray-300">
        Research → choose a practice task → generate a private sample → review the
        checks. The agents do the drafting; you choose and review.
      </p>
      <p className="text-teal-300">
        Budget €0 · permitted loss €0 · no launch authority
      </p>
      <p className="text-sm text-gray-400">
        Learning here means practicing with the existing model. It does not train a new
        model or prove customer demand. Samples are text only; generated code is never
        executed.
      </p>
      {error && (
        <p role="alert" className="text-amber-300">
          {error}
        </p>
      )}
      {busy && (
        <p role="status">
          Working… local AI reasoning can take several minutes. If interrupted, refresh
          the record; do not start duplicate work.
        </p>
      )}
      <fieldset disabled={busy} className="command-card space-y-3">
        <legend>1. Research sources and brief</legend>
        <p className="text-sm text-gray-400">
          Select at least three dated records, or read public pages below. Platform fees
          and documentation alone do not establish customer demand. Public reads send
          the page URL only; records remain unverified.
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            act(async () => {
              const source = await request(
                "/business-discovery/public-source",
                "POST",
                { url },
              );
              setSources((old) => [source, ...old]);
              setChosen((old) => [...old, source.id]);
              setUrl("");
            });
          }}
          className="flex flex-wrap gap-2"
        >
          <input
            aria-label="Public research URL"
            className="agile-input flex-1 min-w-0"
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://… public source"
            required
          />
          <button className="office-filter">Read public source</button>
        </form>
        <button
          className="office-filter"
          onClick={() =>
            act(async () => {
              for (const publicUrl of [
                "https://help.fiverr.com/hc/en-us/articles/9234443621137-Your-earnings-page",
                "https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits",
                "https://developers.cloudflare.com/pages/platform/limits/",
              ]) {
                const source = await request(
                  "/business-discovery/public-source",
                  "POST",
                  { url: publicUrl },
                );
                setSources((old) => [source, ...old]);
                setChosen((old) => [...old, source.id]);
              }
            })
          }
        >
          Read three starting sources
        </button>
        <p className="text-xs text-gray-400">
          Starting sources cover platform fees and hosting constraints. Add demand or
          buyer evidence before expecting a business choice. Failed reads stay missing;
          they never count as evidence.
        </p>
        <details>
          <summary>Available evidence records ({sources.length})</summary>
          <p className="text-xs text-gray-400">
            Saved evidence, including previous workflow inputs. Text here is not a
            current error message.
          </p>
          {sources.map((s) => (
            <label key={s.id} className="block text-sm my-2 break-words">
              <input
                type="checkbox"
                checked={chosen.includes(s.id)}
                onChange={(e) =>
                  setChosen((old) =>
                    e.target.checked ? [...old, s.id] : old.filter((i) => i !== s.id),
                  )
                }
              />{" "}
              #{s.id} {s.title} · {s.freshness} · {s.verification}
              <span className="block text-gray-500">{s.reference}</span>
              <span className="block whitespace-pre-wrap">
                {s.summary.slice(0, 250)}
              </span>
            </label>
          ))}
        </details>
        <p role="status">
          {chosen.length} sources selected
          {chosen.length >= 3
            ? " — ready. Next: Save research brief below."
            : " — select at least three."}
        </p>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            act(async () =>
              update(
                await request("/business-discovery", "POST", {
                  title,
                  constraints,
                  source_ids: chosen,
                }),
              ),
            );
          }}
          className="space-y-3"
        >
          <label className="block">
            Research title
            <input
              className="agile-input w-full"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
              required
            />
          </label>
          <label className="block">
            Your constraints
            <textarea
              className="agile-input w-full"
              rows={3}
              value={constraints}
              onChange={(e) => setConstraints(e.target.value)}
              maxLength={4000}
              required
            />
          </label>
          <button className="office-filter" disabled={chosen.length < 3}>
            Save research brief
          </button>
        </form>
      </fieldset>
      <div>
        {chosen.map((id) => (
          <BusinessSourceContext
            key={id}
            sourceId={id}
            request={request}
            disabled={busy}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((b) => (
          <button
            disabled={busy}
            className="office-filter"
            key={b.id}
            onClick={() =>
              act(async () => update(await request(`/business-discovery/${b.id}`)))
            }
          >
            #{b.id} {b.title} · {b.state.replaceAll("_", " ")}
          </button>
        ))}
      </div>
      {selected && (
        <article className="command-card space-y-4">
          <h3 className="text-xl font-semibold break-words">{selected.title}</h3>
          <p>State: {selected.state.replaceAll("_", " ")}</p>
          <p className="whitespace-pre-wrap break-words text-sm">
            {selected.constraints}
          </p>
          <p className="text-sm">
            Source records: {selected.source_ids.map((id) => `#${id}`).join(", ")}
          </p>
          <button
            disabled={busy}
            className="office-filter"
            onClick={() =>
              act(async () =>
                update(await request(`/business-discovery/${selected.id}`)),
              )
            }
          >
            Refresh record
          </button>
          {selected.state === "draft" && (
            <button
              disabled={busy}
              className="office-filter"
              onClick={() => stage("research")}
            >
              Compare options with local AI
            </button>
          )}
          {selected.research &&
            ![2, 3].includes(selected.research_contract_version) && (
              <p role="alert" className="text-amber-300">
                This older comparison has not passed the service/source checks. Create a
                new attempt below before choosing practice.
              </p>
            )}
          {selected.research && (
            <>
              <h4 className="font-semibold">
                2. Research recommendation — unverified AI output
              </h4>
              <p className="text-sm text-amber-300">
                {selected.research.includes("Selection blocked")
                  ? "Business choice blocked: more buyer evidence or resolved contradictions are needed. Private practice remains available."
                  : selected.research
                      .split("\n")
                      .find((line) =>
                        line.startsWith("Research candidate with greatest"),
                      ) ||
                    "Private practice recommendation only; review the evidence details."}
              </p>
              {selected.research.includes("Withheld unsupported quotation") && (
                <p role="alert" className="text-sm text-amber-300">
                  Unsupported AI source quotations were withheld and receive no evidence
                  credit. See Evidence coverage in the full report.
                </p>
              )}
              <AiReport text={selected.research} />
              {withheld > 0 && (
                <p role="alert" className="text-sm text-amber-300">
                  A placeholder or invalid source suggestion was withheld. It provides
                  no buyer evidence. Private practice remains available below.
                </p>
              )}
              {proposals.map((proposal, index) => (
                <div key={index} className="text-sm break-words">
                  <p>
                    Suggested source, contents unknown: {proposal.url} ·{" "}
                    {proposal.purpose}
                  </p>
                  <button
                    type="button"
                    disabled={busy}
                    className="office-filter"
                    onClick={() =>
                      act(async () => {
                        const source = await request(
                          "/business-discovery/public-source",
                          "POST",
                          { url: proposal.url },
                        );
                        setSources((old) => [source, ...old]);
                        setChosen((old) => Array.from(new Set([...old, source.id])));
                      })
                    }
                  >
                    Read proposed source {index + 1}
                  </button>
                  <p>
                    Create a new brief with the new record to use it. This report stays
                    unchanged.
                  </p>
                </div>
              ))}
            </>
          )}
          {selected.state === "research_ready" &&
            [2, 3].includes(selected.research_contract_version) && (
              <form
                className="space-y-3"
                onSubmit={(e) => {
                  e.preventDefault();
                  act(async () =>
                    update(
                      await request(
                        `/business-discovery/${selected.id}/practice-plan`,
                        "POST",
                        {
                          expected_version: selected.version,
                          skill_version_id: skillId ? Number(skillId) : null,
                          selected_option: option,
                          service_key: service,
                          audience,
                          supplied_facts: facts,
                          deliverable_kind: kind,
                          exercise,
                          checks: checks
                            .split("\n")
                            .map((s) => s.trim())
                            .filter(Boolean),
                          observation_due_at: new Date(due).toISOString(),
                        },
                      ),
                    ),
                  );
                }}
              >
                <fieldset disabled={busy} className="space-y-3">
                  <legend>3. Choose a private practice exercise</legend>
                  <label className="block">
                    Reusable private procedure (optional)
                    <select
                      aria-label="Reusable private procedure (optional)"
                      className="agile-input w-full"
                      value={skillId}
                      onChange={(e) => {
                        setSkillId(e.target.value);
                        const skill = acceptedSkills.find(
                          (item) => String(item.id) === e.target.value,
                        );
                        if (skill) {
                          setService(skill.service_key);
                          setKind(skill.deliverable_kind);
                          setChecks(skill.checks.join("\n"));
                        }
                      }}
                    >
                      <option value="">No reusable procedure</option>
                      {acceptedSkills
                        .filter((skill) => skill.usable)
                        .map((skill) => (
                          <option key={skill.id} value={skill.id}>
                            {skill.name} · v{skill.version} · #{skill.id}
                          </option>
                        ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    onClick={() =>
                      act(async () => {
                        setAcceptedSkills(await request("/skills?limit=100"));
                      })
                    }
                  >
                    Refresh accepted procedures
                  </button>
                  {moreSkills && (
                    <button
                      type="button"
                      onClick={() =>
                        act(async () => {
                          const page = await request(
                            `/skills?limit=100&offset=${skillOffset}`,
                          );
                          setAcceptedSkills((old) => [
                            ...old,
                            ...page.filter(
                              (skill: { id: number }) =>
                                !old.some((item) => item.id === skill.id),
                            ),
                          ]);
                          setSkillOffset(skillOffset + 100);
                          setMoreSkills(page.length === 100);
                        })
                      }
                    >
                      Load older procedure versions
                    </button>
                  )}
                  <p className="text-sm">
                    Selecting a procedure fills its service, format and checks. Keep
                    these unchanged and use with different supplied facts. See Executive
                    skill library below.
                  </p>
                  <p className="text-sm">
                    Choose a prepared exercise or supply a brief. Approval freezes its
                    facts and checks; later revisions use the same rubric.
                  </p>
                  <label className="block">
                    Prepared exercise
                    <select
                      aria-label="Prepared exercise"
                      className="agile-input w-full"
                      defaultValue=""
                      onChange={(e) => {
                        const preset = templates.find((t) => t.key === e.target.value);
                        if (preset) {
                          setService(preset.service_key);
                          setOption(preset.service_key.replaceAll("_", " "));
                          setAudience(preset.audience);
                          setFacts(preset.supplied_facts);
                          setKind(preset.deliverable_kind);
                          setExercise(preset.exercise);
                          setChecks(preset.checks.join("\n"));
                        }
                      }}
                    >
                      <option value="">Choose an exercise…</option>
                      {templates.map((t) => (
                        <option key={t.key} value={t.key}>
                          {t.key.replaceAll("_", " ")}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    Practice service
                    <select
                      aria-label="Practice service"
                      className="agile-input w-full"
                      value={service}
                      onChange={(e) => setService(e.target.value)}
                    >
                      {["documentation", "editing", "support_drafts"].map((key) => (
                        <option key={key} value={key}>
                          {key.replaceAll("_", " ")}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    Audience
                    <input
                      aria-label="Audience"
                      required
                      maxLength={1000}
                      className="agile-input w-full"
                      value={audience}
                      onChange={(e) => setAudience(e.target.value)}
                    />
                  </label>
                  <label className="block">
                    Supplied facts and explicit unknowns
                    <textarea
                      aria-label="Supplied facts and explicit unknowns"
                      required
                      maxLength={6000}
                      className="agile-input w-full"
                      value={facts}
                      onChange={(e) => setFacts(e.target.value)}
                    />
                  </label>
                  <label className="block">
                    Deliverable format
                    <select
                      aria-label="Deliverable format"
                      value={kind}
                      onChange={(e) => setKind(e.target.value)}
                      className="agile-input w-full"
                    >
                      {[
                        "guide",
                        "evidence_summary",
                        "reply",
                        "edited_text",
                        "other_text",
                      ].map((k) => (
                        <option key={k} value={k}>
                          {k.replaceAll("_", " ")}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block">
                    Chosen option
                    <input
                      required
                      maxLength={1000}
                      className="agile-input w-full"
                      value={option}
                      onChange={(e) => setOption(e.target.value)}
                    />
                  </label>
                  <label className="block">
                    Practice deliverable
                    <textarea
                      aria-label="Practice deliverable"
                      required
                      maxLength={4000}
                      className="agile-input w-full"
                      value={exercise}
                      onChange={(e) => setExercise(e.target.value)}
                    />
                  </label>
                  <label className="block">
                    Observable checks (2–10, one per line)
                    <textarea
                      aria-label="Observable checks (2–10, one per line)"
                      required
                      className="agile-input w-full"
                      value={checks}
                      onChange={(e) => setChecks(e.target.value)}
                    />
                  </label>
                  <label className="block">
                    Review due (your local time)
                    <input
                      required
                      type="datetime-local"
                      className="agile-input w-full"
                      value={due}
                      onChange={(e) => setDue(e.target.value)}
                    />
                  </label>
                  <button className="office-filter">
                    Approve this practice plan only
                  </button>
                </fieldset>
              </form>
            )}
          {selected.skill_version && (
            <p>
              Procedure: {selected.skill_version.name} · version{" "}
              {selected.skill_version.version} · #{selected.skill_version.id}
              {!selected.skill_version.usable &&
                " · " + selected.skill_version.unavailable_reason}
            </p>
          )}
          {selected.practice_specification?.structured && (
            <details>
              <summary>Approved facts and rubric</summary>
              <p className="whitespace-pre-wrap">
                Audience: {selected.practice_specification.specification.audience}
                {"\n"}Facts:{" "}
                {selected.practice_specification.specification.supplied_facts}
              </p>
              <p className="text-xs">
                Rubric: {selected.practice_specification.rubric_digest.slice(0, 12)} ·
                owner assessments only
              </p>
            </details>
          )}
          {selected.feedback_summary && (
            <details open>
              <summary>Feedback improvement</summary>
              <p className="text-xs">{selected.feedback_summary.scope}</p>
              {selected.feedback_summary.comparisons.length === 0 && (
                <p className="text-sm">
                  Review an original and a revised sample to compare their results.
                </p>
              )}
              {selected.feedback_summary.comparisons.map((pair) => (
                <div key={pair.sample_id} className="contribution text-sm">
                  <p>
                    Sample #{pair.parent_sample_id} → #{pair.sample_id} · reviews #
                    {pair.before_review_id} → #{pair.after_review_id}
                  </p>
                  {!pair.comparable ? (
                    <p>Legacy or changed rubric: no improvement comparison.</p>
                  ) : (
                    <>
                      <p>
                        {pair.improved_checks.length} improved ·{" "}
                        {pair.regressed_checks.length} regressed ·{" "}
                        {pair.remaining_failures.length} still failed
                      </p>
                      <ul>
                        {pair.improved_checks.map((c) => (
                          <li key={c}>Improved: {c}</li>
                        ))}
                        {pair.regressed_checks.map((c) => (
                          <li key={c}>Regressed: {c}</li>
                        ))}
                        {pair.remaining_failures.map((c) => (
                          <li key={c}>Still failed: {c}</li>
                        ))}
                      </ul>
                    </>
                  )}
                  {pair.feedback_superseded && (
                    <p>
                      The feedback used was later corrected; the exact original
                      comparison remains visible.
                    </p>
                  )}
                </div>
              ))}
            </details>
          )}
          {selected.exercise && (
            <p className="whitespace-pre-wrap break-words">
              Practice: {selected.exercise} · Review due:{" "}
              {selected.observation_due_at &&
                new Date(selected.observation_due_at).toLocaleString()}
            </p>
          )}
          {selected.state === "practice_ready" && (
            <button
              disabled={busy}
              className="office-filter"
              onClick={() => stage("practice")}
            >
              Generate private practice sample
            </button>
          )}
          {selected.sample && (
            <>
              <h4 className="font-semibold">
                Practice sample — AI self-checks are unverified
              </h4>
              <details open>
                <summary>Full sample</summary>
                <p className="whitespace-pre-wrap break-words text-sm">
                  {selected.sample_display || selected.sample}
                </p>
              </details>
            </>
          )}
          {selected.attempts?.length > 0 && (
            <PracticeArtifacts
              key={selected.id}
              briefId={selected.id}
              samples={selected.attempts}
              apiKey={apiKey}
              onAuthFailure={onAuthFailure}
            />
          )}
          {(selected.state === "sample_ready" ||
            (selected.state === "reviewed" && correcting)) && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                act(async () =>
                  update(
                    await request(
                      `/business-discovery/${selected.id}/${correcting ? "review-correction" : "review"}`,
                      "POST",
                      {
                        expected_version: selected.version,
                        results,
                        evidence,
                        observed_at: new Date().toISOString(),
                      },
                    ),
                  ),
                );
              }}
            >
              <fieldset disabled={busy} className="space-y-3">
                <legend>
                  {correcting
                    ? "Correct the recorded assessment"
                    : "4. Review the actual sample"}
                </legend>
                <p className="text-sm">
                  Choose Passed or Failed for every check based on the actual sample.
                  Your assessment does not permit launching. Corrections preserve the
                  earlier record.
                </p>
                {selected.checks?.map((check, i) =>
                  selected.ignored_check_indices?.includes(i) ? (
                    <p key={i} className="text-sm text-gray-400">
                      Excluded checklist instruction: {check}. Original records are
                      preserved.
                    </p>
                  ) : (
                    <label key={i} className="block break-words">
                      {check}
                      <select
                        aria-label={check}
                        className="agile-input block w-full"
                        value={
                          results[i] === null || results[i] === undefined
                            ? ""
                            : results[i]
                              ? "pass"
                              : "fail"
                        }
                        required
                        onChange={(e) =>
                          setResults((old) =>
                            old.map((r, n) =>
                              n === i
                                ? e.target.value === ""
                                  ? null
                                  : e.target.value === "pass"
                                : r,
                            ),
                          )
                        }
                      >
                        <option value="">Not assessed — choose a result</option>
                        <option value="pass">Passed</option>
                        <option value="fail">Failed</option>
                      </select>
                    </label>
                  ),
                )}
                <label className="block">
                  What you checked and observed
                  <textarea
                    aria-label="What you checked and observed"
                    required
                    maxLength={12000}
                    className="agile-input w-full"
                    value={evidence}
                    onChange={(e) => setEvidence(e.target.value)}
                  />
                </label>
                <button
                  className="office-filter"
                  disabled={results.some((result) => result === null)}
                >
                  {correcting ? "Record review correction" : "Record practice review"}
                </button>
                {correcting && (
                  <button
                    type="button"
                    className="office-filter ml-2"
                    onClick={() => setCorrecting(false)}
                  >
                    Cancel correction
                  </button>
                )}
              </fieldset>
            </form>
          )}
          {selected.state === "reviewed" && selected.review && !correcting && (
            <div className="flex flex-wrap gap-2">
              <button
                className="office-filter"
                disabled={busy}
                type="button"
                onClick={(event) => {
                  event.preventDefault();
                  setCorrecting(true);
                  setResults([...selected.review!.results]);
                  setEvidence(selected.review!.evidence);
                }}
              >
                Correct review results
              </button>
              <button
                className="office-filter"
                disabled={busy}
                onClick={() => stage("revise")}
              >
                Revise sample using this review
              </button>
            </div>
          )}
          {selected.review && (
            <ul className="text-sm space-y-1">
              {selected.checks?.map((check, i) => (
                <li key={i} className="break-words">
                  {selected.ignored_check_indices?.includes(i)
                    ? "Excluded instruction"
                    : selected.review?.results[i]
                      ? "Passed"
                      : "Failed"}
                  : {check}
                </li>
              ))}
            </ul>
          )}
          {selected.review && (
            <p className="whitespace-pre-wrap break-words">
              {(selected.review_assessment || selected.review.assessment).replaceAll(
                "_",
                " ",
              )}{" "}
              · {selected.review.evidence}
              <br />
              Owner assessment of this sample only. Checklist instructions are excluded
              from the current summary; history keeps the original results. Next:
              correct an inaccurate assessment or revise using this feedback, then
              review the new sample. Customer demand and profit remain unknown.
            </p>
          )}
          {selected.state === "needs_review" && (
            <p className="text-amber-300">
              Generation failed or was interrupted. Nothing is approved. Previous
              samples and reviews are preserved. Use a revision retry if reviewed
              practice exists, or create a new research attempt.
            </p>
          )}
          {selected.state === "needs_review" && selected.sample && selected.review && (
            <button
              className="office-filter"
              disabled={busy}
              onClick={() => stage("revise")}
            >
              Retry revision using this review
            </button>
          )}
          {(selected.state === "needs_review" ||
            selected.state === "research_ready") && (
            <button
              className="office-filter"
              disabled={busy}
              onClick={() =>
                act(async () =>
                  update(
                    await request("/business-discovery", "POST", {
                      title: selected.title,
                      constraints: selected.constraints,
                      source_ids: selected.source_ids,
                    }),
                  ),
                )
              }
            >
              Create new attempt from this brief
            </button>
          )}
          {selected.attempts?.length > 0 && (
            <details>
              <summary className="command-link">
                Sample & review history ({selected.attempts.length} samples)
              </summary>
              {selected.attempts.map((attempt) => (
                <article className="contribution space-y-2" key={attempt.id}>
                  <h4 className="font-semibold">
                    Sample {attempt.attempt} ·{" "}
                    {new Date(attempt.created_at).toLocaleString()}
                  </h4>
                  {attempt.parent_sample_id && (
                    <p className="text-xs text-gray-400">
                      Revises sample record #{attempt.parent_sample_id}, using review #
                      {attempt.feedback_review_id}
                    </p>
                  )}
                  <details>
                    <summary>Full saved sample</summary>
                    <p className="whitespace-pre-wrap break-words text-sm">
                      {attempt.sample}
                    </p>
                  </details>
                  {attempt.reviews.map((review) => (
                    <div key={review.id} className="text-sm">
                      <p>
                        Review #{review.id} ·{" "}
                        {review.review.assessment.replaceAll("_", " ")}
                        {review.supersedes_review_id &&
                          ` · corrects review #${review.supersedes_review_id}`}
                      </p>
                      <ul>
                        {review.review.results.map((passed, i) => (
                          <li key={i}>
                            {passed ? "Passed" : "Failed"}:{" "}
                            {selected.practice_specification?.specification.checks[i] ||
                              selected.checks?.[i]}
                          </li>
                        ))}
                      </ul>
                      <p className="whitespace-pre-wrap break-words">
                        {review.review.evidence}
                      </p>
                    </div>
                  ))}
                </article>
              ))}
            </details>
          )}
        </article>
      )}
      <details>
        <summary>Repeated practice evidence</summary>
        <button
          disabled={busy}
          type="button"
          className="office-filter"
          onClick={() =>
            act(async () =>
              setPracticeEvidence(
                await request("/business-discovery/practice-evidence"),
              ),
            )
          }
        >
          Refresh practice evidence
        </button>
        <p className="text-sm">{practiceEvidence?.scope}</p>
        {practiceEvidence?.groups.map((group) => (
          <p key={group.rubric_digest} className="text-sm">
            {group.service_key.replaceAll("_", " ")} · {group.assessed_examples}{" "}
            distinct assessed examples · {group.passing_examples} owner-passed ·{" "}
            {group.repeated_practice_evidence
              ? "Repeated practice recorded"
              : "Need two distinct assessed examples"}{" "}
            · briefs {group.brief_ids.map((id) => `#${id}`).join(", ")}
          </p>
        ))}
        {practiceEvidence?.groups.length === 0 && (
          <p>No structured examples have been assessed yet.</p>
        )}
      </details>
    </section>
  );
}
