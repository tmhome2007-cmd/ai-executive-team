# BE-24 — repeatable local answer measurements

Run from this checkout with Ollama open:

```bash
./company quality
./company quality summary
```

The first command generates 10 fictional cases three times each (30 attempts). It may take several minutes. Ctrl+C preserves completed attempts and a report with the remaining attempts counted as incomplete. No company database, dashboard key, private company source, tool, paid service or cloud model is used.

A zero exit status means all 30 narrow automatic checks passed; exit 1 means failed checks, inference errors or incomplete attempts; exit 2 means startup/report configuration could not be used. A failure is a useful measurement, not permission to change the owner’s approval decisions.

## What is measured

Fixtures cover task results, task instructions, return-policy drafting, evidence gaps, zero budgets, pending approval, conflicting sources, supplied reminder details, single-sample competence and private drafts. Raw output must satisfy a bounded three-key JSON contract, contain specified literal fact tokens in findings, and preserve named uncertainty. Existing output-quality checks detect several unsupported approval/causal claims.

These are deliberately narrow checks: paraphrases can fail literal coverage, and misleading statements containing the expected words can still pass. They do not verify truth, assess every deliverable, replace owner review or establish business competence. No AI judge is used. This benchmark profile is not the complete production business-generation workflow.

Ollama’s optional [JSON output mode](https://docs.ollama.com/api/generate) can be measured with `./company quality run --json-output`. This changes generation configuration, not the rubric, and still checks the raw response.

## Versions and comparison

Each private report records the fixture hash, checker-code hash, rubric version, exact saved prompt hash, installed model name/digest and generation configuration. Changing fixtures or checkers invalidates direct comparison. Prompt/model/configuration changes are visible comparison dimensions.

```bash
./company quality versions
./company quality run --prompt-version FULL_SAVED_HASH
./company quality compare quality-results/FIRST_RUN/report.json quality-results/SECOND_RUN/report.json
```

Prompt replay provides rollback for this benchmark profile. It does not silently change production prompts. Editing the checked-in policy/profile creates a new snapshot on the next run; old prompt files and results remain immutable.

## Storage and recovery

Owner-only files live under ignored `quality-results/`; reports contain only fictional fixture generations. They are retained as development measurement evidence rather than transient company artifacts. Files are exclusive-created with mode 0600 in 0700 directories; symlink storage is rejected. Completed attempts survive interruption. A manifest without a final report indicates an abrupt process kill; its saved attempt files remain inspectable and no passing score is inferred.

Ollama must use a loopback HTTP URL, without credentials, redirects or environment proxies. Each response has a byte cap and timeout; generated code is never executed. No new runtime dependency or copied upstream code is introduced.

When checker code changes, `./company quality recheck quality-results/RUN/report.json` creates a derived report from the saved raw answers under the current checker. It requires the same fixture inputs, preserves the original report, records its hash and makes no model requests. Compare two derived reports to reassess an earlier pair fairly.

## First measured baseline — 10 October 2026

Local `llama3.1:latest`: unconstrained generation passed 0/30 (all failed the JSON-only contract). With the same prompt and fixture inputs, Ollama JSON mode passed 24/30, with six fact-coverage failures and no transport errors. Both raw runs are preserved privately. After tightening checker identity to exclude prompt/transport text, both were rechecked from unchanged raw answers under the same checker; the outcomes stayed unchanged. See [the saved measurement summary](planning/be24-baseline-summary.json).

This demonstrates a generation-format improvement in this fictional profile. It does not measure production workflows or prove semantic correctness. The six remaining failures include strict literal fact coverage; inspect actual answers before concluding that every flagged paraphrase is wrong. Production prompts were not changed.

Verification: backend suite ran 193 tests successfully with one existing real-Docker test skipped, before the final checker/recheck changes; the final targeted suite covers those changes separately. Formatting/catalog checks and focused Bandit medium/high checks pass.
