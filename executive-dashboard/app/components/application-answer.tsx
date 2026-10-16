import { checklistSummary } from "../lib/checklist-summary";

export default function ApplicationAnswer({ text }: { text: string }) {
  const summary = checklistSummary(text);
  if (!summary) return null;
  return (
    <section
      aria-label="Your next step"
      className="rounded-lg border border-teal-700 bg-gray-950 p-4 space-y-3 text-sm"
    >
      <div>
        <h3 className="font-semibold text-lg text-teal-200">Your next step</h3>
        <p className="text-xs text-gray-400">
          Application guidance from your answers · proposed owner work only
        </p>
      </div>
      <p className="font-medium text-base">{summary["First step"]}</p>
      <p>
        <strong>Why: </strong>
        {summary.Why}
      </p>
      <p>
        <strong>If blocked: </strong>
        {summary["If blocked"]}
      </p>
      <p>
        <strong>Estimated effort: </strong>
        {summary.Effort}
      </p>
      <p className="text-xs text-amber-200">{summary.Context}</p>
      <p className="text-xs text-gray-400">
        No message has been sent. AI proposals below need separate review.
      </p>
    </section>
  );
}
