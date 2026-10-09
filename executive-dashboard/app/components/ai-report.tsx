"use client";
import { reviewSummary } from "../lib/review-summary";
export default function AiReport({ text }: { text: string }) {
  const report = reviewSummary(text);
  const sections = [
    ["Reported findings", report.findings, "No structured findings were supplied. Open the full report."],
    ["Unknowns / evidence needed", report.unknowns, "No explicit unknowns were listed; this does not establish complete evidence."],
    ["Proposed next action", report.next, "No explicit next action was supplied. Review the full report before choosing one."],
  ] as const;
  return <section aria-label="AI report short review" className="space-y-3 break-words">
    <p className="text-xs text-gray-400">Up to three excerpts per section; additional details may be omitted. Review sources and the full report before approval. Owner approval is recorded separately.</p>
    {report.warnings.length > 0 && <div role="alert" className="border border-amber-700 p-3 text-amber-200"><ul>{report.warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul></div>}
    {sections.map(([title, lines, empty]) => <div key={title}><h4 className="font-semibold text-teal-300">{title}</h4>{lines.length ? <ul className="list-disc pl-5 text-sm space-y-1">{lines.map((line, i) => <li key={i}>{line}</li>)}</ul> : <p className="text-sm text-gray-400">{empty}</p>}</div>)}
    <details><summary className="command-link cursor-pointer">Full report and evidence details</summary><div className="whitespace-pre-wrap text-sm mt-3">{text || "No report was supplied."}</div></details>
  </section>;
}
