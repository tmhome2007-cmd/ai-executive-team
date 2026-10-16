# Bandit B608 review — 2026-10-08

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

**Finding classification: 21 individually reviewed B608 false positives.**

The current Bandit scan detects 21 medium-severity occurrences in `memory/database.py`. Each constructs SQL with Python string interpolation. These are **not automatically vulnerabilities**, but dynamic identifiers must never originate from arbitrary external input.

## Reviewed query families

1. **Dynamic `IN (...)` placeholder counts:** goal, follow-up, decision-approval, resource-request and action transition/recovery queries. SQL structure is built from a number of literal `?` placeholders, and values are passed separately to sqlite3 `execute`. Status filters are checked against `VALID_*_STATUSES` where appropriate.
2. **Literal WHERE/AND clauses:** executive-memory filters and treasury summaries build clauses from program-authored constant SQL fragments. User-provided values remain parameters.
3. **Dynamic UPDATE assignments:** company-goal and action-outcome updates derive keys from named function parameters or fixed local dictionaries. They must remain restricted to statically known column names; a future refactor must not accept arbitrary caller-supplied column names.
4. **Signed-sync SQL:** import accepts only table names in `_SYNC_TABLE_COLUMNS` and only row keys in the corresponding allowed set; input values remain bound parameters. Foreign key resolution table names are in literal tuples.
5. **Dynamic INSERT:** table/column identifiers are derived from the same fixed import whitelist; values use positional parameters.

## Required ongoing protection

- Keep import-table and column sets immutable and explicit.
- Continue to reject unknown row keys before generating UPDATE/INSERT.
- Add dedicated malicious-column tests (e.g. column names containing `); DROP TABLE`) for signed imports.
- Do not broadly disable Bandit B608. If individual suppressions are introduced, require code-review justification beside each location.
- Re-run B608 after any SQL schema/import/refactor change.
- Treat changes to assignment-key sources (particularly `updates` or imported rows) as security-sensitive.

**Audit outcome:** No directly interpolated untrusted SQL *values* identified in these 21 inspected query sites; malicious status values, signed table/column injection attempts, and SQL-like literal UPDATE values pass real-SQLite regressions. Each reviewed expression now has an individual `nosec B608` justification beside it. Bandit remains enabled globally and the medium/high gate passes; this is a static false-positive disposition, not proof of every future query.

## Activity ledger review — 9 October 2026

Two additional B608 expressions in memory/activity.py generate migration snapshots and
triggers from the fixed SPECS tuple. Table names, keys, columns, links and conditions
are program literals; no API or sync value can supply SQL structure. Each site has an
individual justification. The gate now reviews 23 construction sites and reports zero
medium/high findings. Real SQLite tests cover migration replay, atomic rollback and
concurrent transitions in addition to the existing adversarial input regressions.

## BE-04–07 schema additions — 9 October 2026

Two further construction expressions install immutable evidence-link and discussion
triggers. Each iterates only the literal tuple (`UPDATE`, `DELETE`) with a fixed table,
trigger prefix and error string; no user identifiers/values enter those expressions.
Both have individual B608 dispositions. Other new source/plan/discussion/capability
queries bind all runtime values. The evidence-target query selector chooses among
three fixed statements, and provider checks use fixed hosts rather than SQL-derived
URLs. Real SQLite tests exercise immutable records and normal/stale/concurrent owner
transitions. Bandit remains enabled globally and includes foundation_api.py.
