// Historical reports retain their text; placeholder links never become read controls.
export function businessProposals(report: string) {
  const prefix = "Proposed public source (not read): ";
  const proposed = report.split("\n").filter(line => line.startsWith(prefix)).slice(0, 5).map(line => ({ url: line.slice(prefix.length).split(" — ")[0], purpose: line.split(" — ").slice(1).join(" — ") }));
  const sources = proposed.filter(({ url }) => {
    try {
      const parsed = new URL(url), host = parsed.hostname.toLowerCase().replace(/\.$/, "");
      return ["http:", "https:"].includes(parsed.protocol) && !parsed.username && !parsed.password && !parsed.search && !parsed.hash && !["example.org", "example.com", "example.net", "example", "invalid", "test"].some(domain => host === domain || host.endsWith("." + domain));
    } catch { return false; }
  });
  return { sources, withheld: proposed.length - sources.length };
}
