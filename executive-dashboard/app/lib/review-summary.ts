export type ReviewSummary = { findings: string[]; unknowns: string[]; next: string[]; warnings: string[] };
type Bucket = "findings" | "unknowns" | "next";
const groups: Record<string, Bucket> = {
  "findings": "findings", "supported findings": "findings", "known facts": "findings", "evidence and gaps": "findings", "expected vs actual": "findings", "what worked": "findings", "observations": "findings",
  "unknowns": "unknowns", "unresolved questions": "unknowns", "what remains unknown": "unknowns", "remaining unknowns": "unknowns", "what failed / unknown": "unknowns", "evidence still required": "unknowns", "missing prerequisites": "unknowns", "prerequisites": "unknowns",
  "practice candidate only": "next", "next research step": "next", "next action": "next", "next step": "next", "proposed next test": "next", "revised next test": "next", "recommended next test and observable result": "next", "recommendation": "next", "recommended next steps": "next", "what to repeat / stop / change": "next", "steps": "next",
};
export function reviewSummary(text: string): ReviewSummary {
  const result: ReviewSummary = { findings: [], unknowns: [], next: [], warnings: [] };
  let bucket: Bucket | null = null;
  // Extract literal report lines; never generate facts or reinterpret missing evidence.
  for (const raw of text.slice(0, 100000).split(/\r?\n/)) {
    const line = raw.trim();
    const heading = line.match(/^(?:#{1,6}\s+(.+)|\*\*(.+?)\*\*\s*:?)$/);
    const field = line.match(/^([A-Za-z][A-Za-z /-]{2,70}):\s*(.*)$/);
    if (heading || field) {
      const title = (heading ? heading[1] || heading[2] : field![1]).replace(/:$/, "").trim().toLowerCase();
      bucket = Object.hasOwn(groups, title) ? groups[title] : null;
      if (field?.[2] && bucket) result[bucket].push(field[2]);
      continue;
    }
    if (!line) continue;
    // Source proposals have their own validated controls; they are not next actions.
    if (line.startsWith("Proposed public source (not read): ")) continue;
    if (/\b(?:blocked until|do not (?:run|execute|create)|missing prerequisites|sources? conflict)\b/i.test(line)) result.warnings.push(line.slice(0, 400));
    if (/AI QUALITY REVIEW REQUIRED|AI cannot establish owner consent/i.test(line)) result.warnings.push(line.slice(0, 400));
    if (bucket) result[bucket].push(line.replace(/^[-*+]\s+/, ""));
  }
  // A separate, persistent warning is more visible than leaving consent claims in details.
  if (/\b(?:owner|human|user)\s+(?:has\s+)?(?:approved|agreed|authorized|consented)\b/i.test(text) && !/\b(?:not|never|cannot)\s+(?:record|establish|infer|claim)?\s*(?:owner|human|user)/i.test(text)) {
    result.warnings.push("An AI report cannot establish owner approval. Check the recorded approval status separately.");
  }
  for (const key of ["findings", "unknowns", "next"] as const) result[key] = [...new Set(result[key])].slice(0, 3).map(line => line.length > 280 ? line.slice(0, 280) + "… [excerpt]" : line);
  result.warnings = [...new Set(result.warnings)].slice(0, 4);
  return result;
}
