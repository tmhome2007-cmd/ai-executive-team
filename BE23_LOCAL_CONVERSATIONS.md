# BE-23: local voiced executive contributions

Status: implemented for owner review on `codex/local-executive-conversations`. BE-20–22 were accepted and merged through PR #36 (`7d0acdb`). BE-23 is a separate change and is not merged.

## Use

1. Stop the old `./company start` terminal with Ctrl+C, then run `./company start` in this checkout.
2. In People & simulation, select an executive, audition a local Kokoro voice and save the neural voice preference. Run `./company voices` only if assets are missing; it downloads public model assets, never company text.
3. In Conversations & activity, select a recorded meeting and click **Load spoken contribution**. Published discussion rounds in Organizational work have the same control.
4. Press Play in the audio control; verify duration, voice fit and intelligibility. Stop cancels ongoing generation/download and stops playback. **Delete saved audio** removes audio bytes while retaining published text and history.

The server uses the current saved character voice and records its version, the published contribution/discussion ID, original-text digest, spoken-text digest and engine/model version in the cache key. It never substitutes a voice or generates new reasoning. Markdown markers and link targets are omitted from speech; the original report remains visible. Character changes produce a different cache entry. Existing cached audio keeps its original expiry rather than extending on every read.

## Limits and privacy

- No cloud speech, company-text downloads or automatic synthesis. All endpoints require the existing owner key; audio is loaded as a private blob with no key in the URL and no-store responses.
- One generator per server and private cache writer lock; no queue of expensive duplicate requests. Isolated worker receives only text and an allowlisted voice on stdin, not command arguments or company credentials. Socket connections are disabled inside the worker; ONNX telemetry is disabled. These application controls are not an OS network sandbox.
- Installed model hashes are verified before use. No automatic download. Kokoro runs on CPU with two intra-op threads and one inter-op thread; generation times out after 240 seconds and kills the worker.
- Contributions must fit 12,000 spoken characters, with audio at most 1,200 seconds/64 MiB. Oversized input fails explicitly without truncation. Cache capacity: 40 WAV files and 256 MiB; a full cache blocks new synthesis instead of silently deleting unexpired audio.
- Audio is owner-only under the configured database directory's `conversation-audio/`; descriptor-relative opens reject links/hardlinks and media hashes detect corruption. Generated media is ignored by Git. Cache provenance is in SQLite and included in whole-database backups; WAV files are regenerable and not included in those backups.
- Default generated-audio retention is 30 days (the owner-confirmed policy matching other generated artifacts). `CONVERSATION_AUDIO_RETENTION_DAYS=7` shortens new entries; `0` disables new synthesis. Existing expiry snapshots are retained. Reads reject expired media immediately; startup/daily cleanup and each new generation remove registered expired files while the server runs. Deletion is not forensic erasure.
- Stop uses the owner-authenticated request token to terminate pending synthesis. If publication already completed, Stop stops playback/download; Delete removes the saved bytes. Closing/unmounting a card aborts downloads and requests cancellation. Expiry/deletion and writes share the cache lock.

Original meeting/approval history is not deleted. A crash between file replacement and metadata commit can leave a private orphan file; capacity still counts its bytes and no successful response is recorded. No claim of exactly-once external effects or verified AI truth is added.

## Review and validation

Automated tests use temporary SQLite and synthetic WAV files for source/profile bindings, cache replay/regeneration, voice versions, expiry, links/corruption, busy/cancel handling, request bounds, owner authentication, private headers and worker timeout/credential stripping. A production-browser smoke checks duration, playback/stop, cache reuse, deletion/regeneration, keys outside URLs/storage and mobile width. A real installed-Kokoro test generated a 6.32-second fictional contribution and replayed it without synthesis; an additional run verified the CPU-bounded session path.

Audio quality and suitability still need the owner's listening review. No acceptance is recorded from automated playback. Known Chroma dependency findings remain separately tracked.

Full local audit on code commit `44fbdde` (`audit-results/20261010-192151`): 187 backend tests, 150 foundation checks and all nine browser flows passed, alongside Bandit, Docker isolation, frontend lint/build/dependency checks, voice dependencies and local Ollama inference. The Python scan still reports four known Chroma advisories separately; it is not clean.

Long-contribution correction: the initial 1,200-character limit rejected normal saved reports. The local engine already batches phonemes at punctuation/word boundaries; the full normalized contribution now reaches that engine within the expanded limits. No excerpts or silent truncation are used.

Correction verification: the real installed engine synthesized a complete 1,946-character fictional contribution into 128.05 seconds of audio and replayed it from the cache. All project checks in the repeated local audit passed: 188 backend tests, 150 foundation checks and nine browser flows. The existing four Chroma advisories remain separately reported.
