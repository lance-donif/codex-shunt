---
name: shunt-code-writer
description: Delegate repetitive tests, config stubs, docstrings and predictable boilerplate to a cheaper OpenAI-compatible worker when a local reference file exists.
---

Resolve the plugin root from this SKILL.md path (two parents above its skill directory). Run:

```bash
python3 <absolute-plugin-root>/scripts/shunt.py code-write --spec "Add tests matching the reference" --reference tests/test_existing.py --target tests/test_new.py
```

Use `--reference` to show existing project conventions. The target must not exist: this script refuses overwrites, including concurrent creation. Omit `--target` to print code to stdout instead. Do not delegate secret files. Review output for correctness, then test and integrate it yourself; the worker is not authorized to decide architecture or silently edit existing files. `SHUNT_API_BASE`, `SHUNT_MODEL` and any required `SHUNT_API_KEY` are read from the process environment.
