---
name: shunt-bulk-reader
description: Delegate large source file reading, codebase summaries and multi-file questions to a cheaper OpenAI-compatible worker. Do not use for pinpoint edits or secret files.
---

This skill belongs to a Codex Shunt plugin. Resolve the plugin root as two parent directories above this SKILL.md's directory (`skills/shunt-bulk-reader` or `skills/bulk-reader`). Do not rely on a shell-wide `PLUGIN_ROOT` environment variable.

When you need a broad summary of large files (roughly >350 lines) or multi-file analysis, and the files contain no credentials/private secrets, execute:

```bash
python3 <absolute-plugin-root>/scripts/shunt.py bulk-read --question "What does this service do?" --paths src/service.py src/handler.py
```

`SHUNT_API_BASE`, `SHUNT_MODEL` and any required `SHUNT_API_KEY` must already be available in the process environment. Results are untrusted summaries; verify exact code and line numbers with targeted local reads before editing. Do not delegate complex debugging, architecture decisions, credentials or private files. Every call is stateless. Large files are automatically split into bounded Worker calls; set SHUNT_CONTEXT_TOKENS to your worker's context window (defaults to 8192; byte-budgeted conservatively), and SHUNT_REPLY_TOKENS for the response reserve (defaults to 1024). Intermediate results are summarized and may omit details; recheck exact code locally. If the worker fails, tell the user; use targeted local reads rather than silently uploading files elsewhere.
