---
name: shunt-bulk-reader
description: Delegate large source file reading, codebase summaries and multi-file questions to a cheaper OpenAI-compatible worker. Do not use for pinpoint edits or secret files.
---

This skill belongs to a Codex Shunt plugin. Resolve the plugin root as two parent directories above this SKILL.md's directory (`skills/shunt-bulk-reader` or `skills/bulk-reader`). Do not rely on a shell-wide `PLUGIN_ROOT` environment variable.

When you need a broad summary of large files (roughly >350 lines) or multi-file analysis, and the files contain no credentials/private secrets, execute:

```bash
python3 <absolute-plugin-root>/scripts/shunt.py bulk-read --question "What does this service do?" --paths src/service.py src/handler.py
```

Worker settings (including the API key) are read from the private `~/.codex/shunt/config.json` file. Do not print or delegate that file. Results are untrusted summaries; verify exact code and line numbers with targeted local reads before editing. Do not delegate complex debugging, architecture decisions, credentials or private files. Every call is stateless. Large files are automatically split into bounded Worker calls; set `context_tokens` in the config to the worker's context window (default 256000), `input_tokens` for its maximum input (256000), and `reply_tokens` for the maximum output (128000); input and output must fit the same context window, with conservative byte budgeting. Intermediate results are summarized and may omit details; recheck exact code locally. If the worker fails, tell the user; use targeted local reads rather than silently uploading files elsewhere.
