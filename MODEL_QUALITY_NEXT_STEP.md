# Proposed next local-model test

13 October 2026. Approved experiment completed; no production adoption.

The installed-model comparison does not pass usefulness: retained llama3.1 validates 6/9; llama3 validates 3/9, with zero complete analyst usefulness passes for either. These are development repetitions, not a general model ranking. Another prompt round on the same cases would not establish transfer.

One bounded candidate is `qwen2.5:14b-instruct-q4_K_M`. The [official Ollama tag](https://ollama.com/library/qwen2.5:14b-instruct-q4_K_M) lists 14.8B parameters, Q4_K_M and a 9.0GB download, and describes improved instruction following/JSON generation. Those are publisher claims, not measured project results. Its [license artifact](https://ollama.com/library/qwen2.5:14b-instruct-q4_K_M/blobs/832dd9e00a68) is Apache 2.0. The old Qwen2.5 GitHub URL redirects to Qwen3, so the current README is not treated as evidence about this exact older checkpoint. Last commit date and issue responsiveness for this artifact remain unknown; displayed relative tag age is not a commit date.

Read-only hardware checks report Apple M4, 24GiB physical memory and about 215GiB free disk. Storage is sufficient for the listed model. Whether runtime memory, speed and background classroom apps remain comfortable is unmeasured; this is a feasible experiment, not a performance guarantee. No new Python or frontend package is required; the existing Ollama runtime would load additional weights.

If the owner authorizes the download, use only `ollama pull qwen2.5:14b-instruct-q4_K_M`, then resolve and freeze the full installed digest before inference. The public tag currently displays the short identifier 7cdf5a0187d5; it is mutable and is not an immutable version guarantee. Freeze the existing helper/assets/options and the same development cases; run nine samples without repair. Compare actual usefulness and critical factual/authority errors, not only schema validity. Do not alter the app default, .env, company databases, role registrations, remote-model privacy gate, approval/execution rules or active CI. All business prompts stay on loopback; the registry only supplies public model weights.

The prepared runner can select this tag only after it is installed; identity lookup fails before generation if it is absent. No automatic pull or cloud fallback exists. Keep failed outputs. Only a candidate passing the existing development gate can proceed to reserved transfer assessment; owner acceptance, full team and integration remain separate.

Permission is needed because the saved project boundary excludes model downloads. The next action would download about 9GB and occupy local storage. The model itself has no purchase price; no paid service or cloud inference is proposed. If permission is not given, keep current models and leave model usefulness blocked while working on independent maintenance.

Research scope: one candidate, three unique resolved primary pages (Qwen repository redirect, official model tag and license), generic queries, no private text transmitted, no cloning/install/source copying. No “best model” or guaranteed quality claim.

## Owner authorization

On 13 October 2026 the owner explicitly approved downloading this exact local model and running the same private tests. Download and frozen nine-sample comparison completed; see BE59_QWEN_COMPARISON.md. This authorization does not change production defaults, privacy gates or deployment/merge requirements.
