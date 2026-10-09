# Sprint 2 — BE-18 / BE-19 local review

10 October 2026. Implementation is in Review; visual/audio acceptance remains with the owner. No final voice quality score or owner acceptance is invented.

## BE-18: identity-aware character presentation

The owner explicitly selected these defaults:

| Character | Presentation |
|---|---|
| Kai Akira | Man; Black, clean-shaven, black dreadlocks, dark eyes with red tint, tall and well-built |
| Maya Chen | Woman |
| Alex Sterling | Man |
| Jordan Blake | Androgynous |
| Sarah Okonkwo | Woman |
| Marcus Rivera | Man |
| Zoe Nakamura | Woman |
| Dev Patel | Man |
| Elena Volkov | Woman |
| Brandon Fire | Man |
| Priya Raman | Woman |

The renderer supports explicit masculine/feminine/androgynous portrait presentation, not name-based gender guessing. Description, hair, skin/eyes, body and voice remain editable. Both face and body views are available. Reasoning personality and authority are unchanged.

New databases receive the revised defaults. On startup, exactly untouched original default profiles receive an appended version; original versions remain intact. Profiles edited by the owner are not overwritten, including edits made before this change. Those may be adjusted manually with the new portrait selector.

## BE-19: local voice comparison and provider research

The previous preview chose the first matching voice and artificially lowered some pitches. The new control requires a specific installed local voice, uses a common short comparison passage, offers natural vs saved pitch/pace, stops playback, and saves the selected voice/language in a retained version. Default pitch is now natural; choosing an appropriate naturally deep voice is preferable to forcing every voice downward. Device quality is still determined by its synthesis engine.

Only browser voices reporting `localService=true` are selectable; this is the browser's locality signal, not an independent audit of the operating system. A missing saved voice is shown explicitly, with no silent provider replacement. [MDN localService documentation](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisVoice/localService).

### Candidate comparison (researched 10 October 2026)

| Candidate | Privacy / installation | Cost and licensing | Review status |
|---|---|---|---|
| Installed browser/system voices | Runs through system/browser synthesis; install system voices and reload if needed. Exposure varies by browser. Downloads contact the vendor. | No additional application service subscription; system terms apply. | Common sample can be compared in this dashboard now; owner listening pending. |
| Kokoro-82M local neural synthesis | Separate runtime/model/voice installation; upstream example uses Python, soundfile and phonemizer dependencies. Model downloads need network; isolated local serving must be designed and tested. | Upstream code/weights Apache-licensed; no hosted-service fee for local execution. Hardware/storage still have costs. | Candidate only, not installed, benchmarked or connected. Listen to upstream samples before choosing. |
| ElevenLabs cloud synthesis | Account and API integration; submitted text leaves the computer. Retention/settings require plan-specific review; do not assume zero retention. | Published Free plan is $0/10k credits; Starter standard monthly price $6/30k credits at research time, with temporary promotions. Commercial licensing comes with paid plans; free usage has noncommercial/attribution constraints. | Candidate only; no account created, credentials added, text submitted or purchase made. |

Sources: [Apple voice management](https://support.apple.com/en-kw/guide/mac-help/mchlp2290/mac), [Kokoro upstream installation and sample links](https://github.com/hexgrad/kokoro), [Kokoro model card and samples](https://huggingface.co/hexgrad/Kokoro-82M), [ElevenLabs pricing](https://elevenlabs.io/pricing), [ElevenLabs billing/commercial rights](https://elevenlabs.io/docs/overview/administration/billing), [ElevenLabs synthesis overview and free-use terms](https://elevenlabs.io/text-to-speech).

Recommendation: first compare installed voices at natural pitch. If they remain unsatisfactory, evaluate Kokoro in a separate disposable local environment before adopting a new dependency. ElevenLabs is a future option only after an explicit cloud/privacy/budget choice. These are design recommendations, not measured sound-quality rankings. No neural provider integration or 3D work is included in this sprint change.

## Owner review: simple restart and checks

Stop your existing `./company start` with Ctrl+C in its terminal, then from this checkout:

```bash
./company doctor
./company start
```

In another terminal in this checkout:

```bash
./company key
```

Open the dashboard, paste the existing key, choose **Organizational work → People & simulation → Characters**.

1. Inspect each of the eleven characters in face and full-body views. Check the selected identities and Kai's specifics; customized old profiles may need a manual presentation edit.
2. Choose an installed voice. Listen to **Preview natural voice**, compare another voice using the same passage, and compare saved pitch/pace. Check **Stop voice**.
3. Save your preferred voice at natural pitch, refresh the character, and verify the name/language and new version. Check history retains the old version.
4. Record whether clarity, naturalness and character fit are acceptable. If not, identify the character/voice and what sounded wrong; do not mark voice quality Done solely because the button works.

For regression checks use `./company audit`. This does not reset the live database or key. The existing upstream dependency advisories remain separately tracked.

## Technical verification

Backend suite: 157 tests passed with the real-Docker test skipped in that run; the real-Docker isolation test passed separately. Foundation regression: 150/150 passed. Character/profile tests: 16 passed, including legacy upgrade, owner-edit preservation and portrait validation. Frontend lint passed with the existing image-optimization warning; webpack production build passed. Changed backend files passed Bandit. Disposable Chromium checks passed for local voice comparison/persistence, remote exclusion, profile history, workforce, fictional-event isolation, mobile layout and API-key storage privacy. Speech in the automated browser test is synthetic/stubbed: it verifies selection, settings, persistence and remote exclusion, not subjective sound quality.
