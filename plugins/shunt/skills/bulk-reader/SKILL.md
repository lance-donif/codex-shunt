---
name: shunt-bulk-reader
description: Delegate large source file reading, codebase summaries and multi-file questions to a cheaper OpenAI-compatible worker. Do not use for pinpoint edits or secret files.
---

This skill belongs to a Codex Shunt plugin. Resolve the plugin root as two parent directories above this SKILL.md's directory (`skills/shunt-bulk-reader` or `skills/bulk-reader`). Do not rely on a shell-wide `PLUGIN_ROOT` environment variable.

When you need a broad summary of large files (roughly >350 lines) or multi-file analysis, and the files contain no credentials/private secrets, execute:

```bash
python3 <absolute-plugin-root>/scripts/shunt.py bulk-read --question "What does this service do?" --paths src/service.py src/handler.py
```

Ordered Worker providers, the current-model pointer and failure timestamps live in the private `~/.codex/shunt/config.json` file. The plugin rotates to the next provider after a failed call, waits 30 minutes after an all-provider outage, and disables itself after a second all-provider outage; users reset both timestamps to null. Do not print or delegate that file. Results are untrusted summaries; verify exact code and line numbers with targeted local reads before editing. Do not delegate complex debugging, architecture decisions, credentials or private files. Every call is stateless. Large files are automatically split into bounded Worker calls; set `context_tokens` in the config to the worker's context window (default 256000), `input_tokens` for its maximum input (256000), and `reply_tokens` for the maximum output (128000); input and output must fit the same context window, with conservative byte budgeting. All configured providers participate in the minimum chunk budget. Intermediate results are summarized and may omit details; recheck exact code locally. If the worker fails, tell the user; use targeted local reads rather than silently uploading files elsewhere.

Chunk summaries use `chunk_summary_tokens` (default 8192) from the user JSON config, capped by each model’s `reply_tokens`. Deep reasoning may consume output tokens; configure this limit for the provider.
