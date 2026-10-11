/** Show attributed structured proposals without truncating objections or implying votes. */
export default function DecisionBrief({ text }: { text: string }) {
  const headings = [
    "Findings",
    "Role positions and objections",
    "Evidence quotations",
    "Unknowns",
    "Next action",
  ];
  const lines = text.split("\n");
  const complete = headings.every((heading) => lines.includes(heading));
  return (
    <section
      aria-label="Structured decision brief"
      className="space-y-3 text-sm break-words"
    >
      <p className="text-xs text-amber-200">
        Private proposals · owner review pending. Quotations were checked against
        supplied records; interpretation still needs review.
      </p>
      {!complete && (
        <p role="alert">
          The brief is incomplete. Review the available text before making a decision.
        </p>
      )}
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
      {!text.trim() && <p>No decision brief was supplied.</p>}
    </section>
  );
}
