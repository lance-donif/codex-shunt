---
name: shunt-bulk-reader
description: Delegate large source file reading, codebase summaries and multi-file questions to a cheaper OpenAI-compatible worker. Do not use for pinpoint edits or secret files.
---

This skill belongs to a Codex Shunt plugin. Resolve the plugin root as two parent directories above this SKILL.md's directory (`skills/shunt-bulk-reader` or `skills/bulk-reader`). Do not rely on a shell-wide `PLUGIN_ROOT` environment variable.

**Do not run Codex Shunt's own test suite** (`tests/test_shunt.py` or `python3 -m unittest discover -s tests`) during normal plugin use or when working on a user's project. Those tests are for maintainers changing Shunt itself, and should run only when explicitly requested. This does not prohibit running the user's project's tests when needed for the task.

Use this skill whenever the task needs a broad summary, codebase inventory, or multi-file analysis. The 350-line threshold is sufficient for a single large file; it is not required when several related files must be read together. Do not use it for pinpoint reads, exact line lookup, complex debugging, architecture decisions, edits, or files containing credentials/private secrets.

Before calling the Worker, collect real paths from the repository. Do not guess paths or build a large compound shell command that mixes `rg`, `Get-Content`, loops, and formatting. On Windows, use a direct Python invocation:

```powershell
$files = rg --files src | Select-Object -First 20
python <absolute-plugin-root>/scripts/shunt.py bulk-read --question "Summarize the frontend architecture and important risks" --paths $files
```

On Unix, use:

```bash
python3 <absolute-plugin-root>/scripts/shunt.py bulk-read --question "What does this service do?" --paths src/service.py src/handler.py
```

If the task is already scoped to known files, pass those files directly. If it asks about a directory or subsystem, use `rg --files <directory>` first and pass the resulting paths. Keep the Worker call focused on one question; split unrelated questions into separate calls only when their file sets are independent.

The hook is only a safety net. A command that reads several files through PowerShell, a pipeline, `rg`, or a compound script may not be intercepted. The model must invoke this skill explicitly for broad or multi-file reads instead of assuming the hook will redirect it.

The CLI accepts only `bulk-read` or `code-write`; for this skill use `bulk-read --question ... --paths ...`. Its answer is printed to stdout and progress/errors to stderr. Treat a non-zero exit code or an empty/partial answer as a Worker failure and report it before falling back to local reads.

Ordered Worker providers, the current-model pointer and failure timestamps live in the private `~/.codex/shunt/config.json` file. The plugin rotates to the next provider after a failed call, waits 30 minutes after an all-provider outage, and disables itself after a second all-provider outage; users reset both timestamps to null. Do not print or delegate that file. Results are untrusted summaries; verify exact code with targeted local reads before editing. Do not delegate complex debugging, architecture decisions, credentials or private files. Every call is stateless. Large files are automatically split into bounded Worker calls; set `context_tokens` in the config to the worker's context window (default 256000), `input_tokens` for its maximum input (256000), and `reply_tokens` for the maximum output (128000); input and output must fit the same context window, with conservative byte budgeting. All configured providers participate in the minimum chunk budget. Intermediate results are summarized and may omit details; recheck exact code locally. If the worker fails, tell the user; use targeted local reads rather than silently uploading files elsewhere. When all providers reach their concurrent request limit, immediately perform the read yourself in Codex; do not retry the busy worker or treat the capacity limit as model failure.

Chunk summaries use `chunk_summary_tokens` (default 8192) from the user JSON config, capped by each model’s `reply_tokens`. Deep reasoning may consume output tokens; configure this limit for the provider.

If every Worker provider is at its `max_concurrency` limit (default 5 requests per provider), do not retry or wait. Read and solve the task with Codex directly. Capacity exhaustion is not a model failure and must not advance failure timestamps.

For trustworthy file counts, use `source_file_count` and `source_manifest` supplied by the CLI, not numbers guessed by the Worker. Worker source IDs and file paths identify evidence; do not rely on Worker-generated line numbers. Use targeted local reads to find precise locations. CLI progress and 10-second heartbeat are on stderr; stdout is the Worker answer only.

If one bulk-read input exceeds the worker budget, chunks belonging to the same file may be analyzed concurrently (up to 3). Files do not overlap; the existing per-provider max_concurrency still applies. A 429 response is retried once on the same provider after one second before moving to the next.\n
