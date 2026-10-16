/** Lead with application guidance; preserve unverified role text behind explicit details. */
import ApplicationAnswer from "./application-answer";
import { checklistSummary } from "../lib/checklist-summary";

export default function DecisionBrief({ text }: { text: string }) {
  const marker = "\n\nExecutive proposals — generated separately";
  const split = text.indexOf(marker);
  const checklist =
    text.startsWith("Application checklist — not an executive recommendation\n") &&
    split >= 0
      ? text.slice(0, split)
      : "";
  const executives = checklist ? text.slice(split + 2) : text;
  const headings = [
    "Findings",
    "Role positions and objections",
    "Evidence quotations",
    "Unknowns",
    "Next action",
  ];
  const lines = executives.split("\n");
  const complete = headings.every((heading) => lines.includes(heading));
  const nextIndex = lines.lastIndexOf("Next action");
  const next = nextIndex >= 0 ? lines[nextIndex + 1]?.trim() : "";
  const summary = checklistSummary(checklist);
  return (
    <section
      aria-label="Structured decision brief"
      className="space-y-3 text-sm break-words"
    >
      {summary ? (
        <ApplicationAnswer text={checklist} />
      ) : (
        <div className="rounded border border-amber-700 p-4 space-y-2">
          <h3 className="font-semibold">AI-proposed next step — unverified</h3>
          <p>
            {next ||
              "No clear next step was supplied. Review the original report below."}
          </p>
          <p className="text-xs text-amber-200">
            This is a saved AI proposal, not a verified team decision. Older results may
            contain unsupported assumptions.
          </p>
        </div>
      )}
      <p className="text-xs text-amber-200">
        Owner review pending. Exact quotations do not establish sound reasoning. Read
        the proposals before approving a direction.
      </p>
      {!complete && (
        <p role="alert">
          The brief is incomplete. Review the available text before making a decision.
        </p>
      )}
      {checklist && (
        <details>
          <summary className="cursor-pointer font-medium">
            Full application checklist and entered context
          </summary>
          <div className="whitespace-pre-wrap mt-3">{checklist}</div>
        </details>
      )}
      <details>
        <summary className="cursor-pointer font-medium">
          AI proposals, objections and evidence — unverified
        </summary>
        <div className="space-y-2 mt-3">
          {lines.filter(Boolean).map((line, index) =>
            headings.includes(line) ? (
              <h4 key={index} className="font-semibold text-teal-300 pt-2">
                {line}
              </h4>
            ) : (
              <p
                key={index}
                className={
                  line.includes(" objection:") ? "border-l-2 border-amber-600 pl-2" : ""
                }
              >
                {line}
              </p>
            ),
          )}
        </div>
      </details>
      {!text.trim() && <p>No decision brief was supplied.</p>}
    </section>
  );
}
