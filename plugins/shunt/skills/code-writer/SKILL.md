---
name: shunt-code-writer
description: Delegate repetitive tests, config stubs, docstrings and predictable boilerplate to a cheaper OpenAI-compatible worker when a local reference file exists.
---

Resolve the plugin root from this SKILL.md path (two parents above its skill directory). Run:

```bash
python3 <absolute-plugin-root>/scripts/shunt.py code-write --spec "Add tests matching the reference" --reference tests/test_existing.py --target tests/test_new.py
```

**Do not run Codex Shunt's own test suite** (`tests/test_shunt.py` or `python3 -m unittest discover -s tests`) during normal plugin use or when working on a user's project. Those tests are for maintainers changing Shunt itself, and should run only when explicitly requested. This does not prohibit running the user's project's tests when needed for the task.

Use `--reference` to show existing project conventions. The target must not exist: this script refuses overwrites, including concurrent creation. Omit `--target` to print code to stdout instead. Do not delegate secret files. Review output for correctness, then test and integrate it yourself; the worker is not authorized to decide architecture or silently edit existing files. Worker providers, per-model reasoning options, and persistent failover state are automatically read and updated in the private `~/.codex/shunt/config.json`; never delegate the config file. When the Worker is cooling down or disabled, report the status rather than repeatedly invoking it. When every Worker reaches its concurrent request limit, generate the code yourself in Codex instead; do not wait, queue, or flag the providers as failed.

If every Worker provider is at its `max_concurrency` limit (default 5 requests per provider), do not retry or wait. Read and solve the task with Codex directly. Capacity exhaustion is not a model failure and must not advance failure timestamps.
