# Sprint 2 retrospective — draft for owner review

10 October 2026. BE-15/16/17 were accepted and merged. BE-18/19 implementation is in Review; subjective appearance/voice acceptance and merge are pending. This is not a claim that the sprint is already closed.

## What improved

- Local startup/key handling now have one checkout-aware launcher, reducing the command/branch confusion the owner reported.
- Results separate findings, unknowns and next action, with details available on demand.
- Private practice retains samples, failures, owner assessments and revisions instead of replacing earlier evidence.
- Explicit character presentation replaces name-based assumptions. Local voices can be compared without forcing all characters to sound artificially deep.
- Conceptual mapping now connects domain records, use cases and MVP boundaries before new scope is chosen.

## What needs improvement

- BE-17 required several owner test/revision cycles. Prevent that by defining a concrete useful sample and failure cases before implementation; basic format checks alone are weak quality evidence.
- Default browser speech quality varies by device. A working speech button is not proof of pleasant or character-appropriate audio.
- Documentation and board templates drifted behind accepted features. Update status, README, review instructions and traceability as part of each story.
- Large branches and intertwined changes made review harder. Keep coherent stories separate, declare dependent PRs, and obtain owner review before marking Done.
- Local test commands must preserve existing credentials and state and explain what is disposable. Report environment restrictions separately from product regressions.

## Next sprint working agreements (proposed)

1. Groom each story using actor, domain relationship, observable acceptance example and authority boundary.
2. Deliver one useful vertical slice, with failed/unknown examples and a short owner review guide.
3. Run appropriate tests on disposable data; distinguish automated functionality from subjective model/voice quality.
4. Record acceptance, update docs/board status and merge only with owner authorization.
5. Select the next scope from the conceptual audit; do not imply paid delivery follows from a practice pass.

No velocity, hours saved, revenue or user satisfaction scores are invented. Owner feedback on BE-18/19 should be added before sprint closure.

## Additional owner feedback — 10 October 2026

The owner rejected the first appearance/voice revision: women were not visually distinct enough, and the best exposed Kai voice still sounded poor. Automated tests verified controls but could not establish visual/audio satisfaction. The second revision now supplies a distinct feminine portrait design and locally generated neural auditions. The next working agreement is to show representative visible/audible samples earlier and keep subjective acceptance separate from passing code tests. BE-18/19 remain in Review.


## Owner acceptance — 10 October 2026

The owner confirmed the corrected neural auditions play, completed review and authorized merge. BE-18 and BE-19 are Done for the implemented character presentation, local voice comparison and neural audition/preference scope. Earlier pending/rejected review entries remain historical. Sprint 2 review is complete. Generated-conversation neural synthesis, 3D animation and paid/cloud voices remain future work.
