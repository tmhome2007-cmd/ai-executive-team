/** Read only the explicit application summary; never turn AI prose into verified advice. */
export function checklistSummary(text: string): Record<string, string> | null {
  const lines = text.split("\n");
  if (
    lines[0] !== "Application checklist — not an executive recommendation" ||
    lines[2] !== "Quick answer — application guidance"
  )
    return null;
  const end = lines.indexOf("End quick answer", 3);
  if (end < 0) return null;
  const result: Record<string, string> = {};
  for (const key of ["First step", "Why", "If blocked", "Effort", "Context"]) {
    const matches = lines.slice(3, end).filter((line) => line.startsWith(`${key}: `));
    if (matches.length !== 1 || !matches[0].slice(key.length + 2).trim()) return null;
    result[key] = matches[0].slice(key.length + 2);
  }
  return result;
}
