# Codex Shunt (independent adaptation of Spotify Shunt)

Codex plugin to delegate bulky source reads and boilerplate generation to a low-cost **OpenAI-compatible Chat Completions API**. No Spotify Portal, AiKA, npm, jq or third-party Python dependencies. Python **3.9+** required (for `Path.unlink(missing_ok=True)`).

Derived from the architecture and workflow of [Spotify Shunt](https://github.com/spotify/portal-ai-plugins/tree/main/plugins/shunt) (Apache-2.0): two Skills, two command entry points, one worker transport, and a read-redirect Hook. This is an unofficial independent adaptation, not affiliated with Spotify. Modified code is rewritten and source paths are identified here; the included Apache-2.0 LICENSE governs the adaptation.

## 1. Configure the worker

In the shell **before starting Codex**, set the worker's API URL and model. Keys are deliberately never placed in config files.

```bash
# Example: OpenAI-compatible hosted Chat Completions
export SHUNT_API_BASE='https://api.openai.com/v1'
export SHUNT_MODEL='gpt-4o-mini'              # choose an available economical model
export SHUNT_API_KEY='YOUR_API_KEY'           # supply your real API key locally

# Alternative: OpenRouter (choose a provider-supported model)
# export SHUNT_API_BASE='https://openrouter.ai/api/v1'
# export SHUNT_MODEL='provider/model-name'

# Alternative: Ollama's OpenAI-compatible endpoint; key is optional on loopback
# export SHUNT_API_BASE='http://127.0.0.1:11434/v1'
# export SHUNT_MODEL='your-installed-model'
# unset SHUNT_API_KEY
```

Provider must support `POST {SHUNT_API_BASE}/chat/completions` with `choices[0].message.content` string. This does **not** support the Responses API, provider SDKs, tool calls, streaming, or multimodal replies.

## 2. Install in Codex

From the unzipped `codex-shunt` directory:

```bash
python3 -m unittest discover -s tests -v
codex plugin marketplace add "$PWD"
codex
```

In Codex, open `/plugins`, select marketplace `Codex Shunt (local)`, and install **Codex Shunt**. Review/trust its `PreToolUse` hook, then start a **new task** so the Skills are discovered. Plugins containing Hooks may only be supported by local clients; see Codex's plugin documentation.

Alternatively, for just CLI use (no Codex installation), run from this extracted directory:

```bash
python3 plugins/shunt/scripts/shunt.py bulk-read --question 'Explain the module' --paths src/app.py
python3 plugins/shunt/scripts/shunt.py code-write --spec 'Make a test' --reference tests/test_existing.py --target tests/test_new.py
```

`codex plugin marketplace add` only **registers the local source**; you still must install/enable it from `/plugins`. The original `spotify/portal-ai-plugins` marketplace is **not** modified by this archive.

## 3. How it works

- `shunt-bulk-reader` Skill: send selected UTF-8 files as bounded request body, get a short answer. A small request makes one Worker call; a large request is automatically split by line (or by characters for oversized single lines), summarized per chunk, then reduced in bounded passes. No source text is truncated during splitting (intermediate summaries may still omit details). Default context setting is 8,192 tokens with 1,024 reserved for output, using the conservative approximation **one UTF-8 byte per input token** (the exact model tokenizer is not available). Also honors the 512,000-byte HTTP request cap (`SHUNT_MAX_PAYLOAD_BYTES`).
- `shunt-code-writer` Skill: generate boilerplate from a required reference. `--target` creates a new file atomically, refusing to overwrite existing files. Omit it to print stdout.
- Codex `PreToolUse` Hook: rejects straightforward full reads (`cat`, `nl`, `less`, `more`, large `head`/`tail` ranges, common printing `sed`/`awk` invocations and literal Python `print(open(...).read())` / `print(Path(...).read_text())` expressions) on files over 350 lines, pointing the agent to the bulk-reader skill. Small targeted reads remain allowed. Set `SHUNT_MIN_LINES` to change threshold.

Worker input limits (inherited from the shell before starting Codex):

```bash
# Set this to your worker's *actual* context window; 8192 is the safe default.
export SHUNT_CONTEXT_TOKENS=8192
export SHUNT_REPLY_TOKENS=1024        # reserve enough for the final answer
export SHUNT_MAX_PAYLOAD_BYTES=512000 # hard HTTP request limit per Worker call
```

`bulk-read` checks the serialized JSON request against the **smaller** of `SHUNT_MAX_PAYLOAD_BYTES` and `SHUNT_CONTEXT_TOKENS - SHUNT_REPLY_TOKENS` in bytes. `code-write` retains its original payload ceiling and does not auto-split generated-code context. Byte counting is deliberately conservative and does not determine the model's exact token count; providers may impose additional limits. Intermediate chunk summaries request at most 512 output tokens using Chat Completions `max_tokens`, so your provider must accept that field. Each chunk incurs an extra paid API call; there is no automatic retry.

Optional `SHUNT_TIMEOUT_SECONDS` default 90 **per call**. API and Hook configuration comes from the shell environment inherited by Codex.

## Security and practical limits

- **External worker sees the full content of every selected file**, not just the summary. Review sensitive, proprietary, personal, and secret data before delegating; minimal filename checks are not a DLP system. HTTP is permitted only for localhost; remote API requires HTTPS and a key. Redirects are disabled.
- Hook is an optimization, **not a security boundary**. Pipelines, complex shell commands, Python scripts/heredocs, dynamic Python reads, MCP reads, and arbitrary custom tools are not automatically intercepted. `exec_command` uses the `Bash` Hook alias in Codex. The hook uses the session cwd, which may differ from a command-specific working directory; explicit paths remain the safest way to avoid ambiguity. Full-file input can still enter Codex context through such paths.
- Codex's local plugin/hook trust and environment may vary by client/version. This archive includes offline unit and mock-HTTP integration tests, not a live Codex or paid-model run.
- The adapter is stateless, does not automatically retry paid calls, and never overwrites existing target files. Intermediate summaries may lose cross-chunk details; verify exact code using targeted reads. Model output is untrusted code: review and test it before executing.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Tests use only Python standard library and a loopback mock server. No API key or external network required.
