# Codex Shunt (independent adaptation of Spotify Shunt)

Codex plugin to delegate bulky source reads and boilerplate generation to a low-cost **OpenAI-compatible Chat Completions API**. No Spotify Portal, AiKA, npm, jq or third-party Python dependencies. Python **3.9+** required (for `Path.unlink(missing_ok=True)`).

Derived from the architecture and workflow of [Spotify Shunt](https://github.com/spotify/portal-ai-plugins/tree/main/plugins/shunt) (Apache-2.0): two Skills, two command entry points, one worker transport, and a read-redirect Hook. This is an unofficial independent adaptation, not affiliated with Spotify. Modified code is rewritten and source paths are identified here; the included Apache-2.0 LICENSE governs the adaptation.

## 1. Configure the worker (no `export` needed)

Create a private user-level config file once. **Do not place your real key in the repository.**

```bash
mkdir -p ~/.config/codex-shunt
cp config.example.json ~/.config/codex-shunt/config.json
chmod 600 ~/.config/codex-shunt/config.json
```

Edit `~/.config/codex-shunt/config.json` and replace `api_key` with your real key:

```json
{
  "api_base": "https://api.openai.com/v1",
  "model": "gpt-4o-mini",
  "api_key": "YOUR_API_KEY",
  "context_tokens": 8192,
  "reply_tokens": 1024,
  "max_payload_bytes": 512000,
  "timeout_seconds": 90,
  "min_lines": 350
}
```

For **Ollama on the same machine**, instead use `"api_base": "http://127.0.0.1:11434/v1"`, a locally installed `"model"`, and `"api_key": ""`. Other providers with an OpenAI-compatible Chat Completions endpoint (e.g. OpenRouter) work by changing `api_base`, `model`, and `api_key`.

The config is loaded automatically by the CLI and the Codex read Hook. Settings may be omitted to use the defaults shown above, except that `api_base` and `model` must be provided. The config is rejected if it is a symlink, invalid JSON, contains unknown fields, or is group/world-accessible on Unix (`chmod 600` fixes permissions). The config file is required; environment variables cannot set or override worker options.

Provider must support `POST {api_base}/chat/completions` with `choices[0].message.content` string. This does **not** support the Responses API, provider SDKs, tool calls, streaming, or multimodal replies.

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

- `shunt-bulk-reader` Skill: send selected UTF-8 files as bounded request body, get a short answer. A small request makes one Worker call; a large request is automatically split by line (or by characters for oversized single lines), summarized per chunk, then reduced in bounded passes. No source text is truncated during splitting (intermediate summaries may still omit details). Default context setting is 8,192 tokens with 1,024 reserved for output, using the conservative approximation **one UTF-8 byte per input token** (the exact model tokenizer is not available). Also honors the 512,000-byte HTTP request cap (`max_payload_bytes`).
- `shunt-code-writer` Skill: generate boilerplate from a required reference. `--target` creates a new file atomically, refusing to overwrite existing files. Omit it to print stdout.
- Codex `PreToolUse` Hook: rejects straightforward full reads (`cat`, `nl`, `less`, `more`, large `head`/`tail` ranges, common printing `sed`/`awk` invocations and literal Python `print(open(...).read())` / `print(Path(...).read_text())` expressions) on files over 350 lines, pointing the agent to the bulk-reader skill. Small targeted reads remain allowed. Set `min_lines` in the user config to change the threshold.

Worker limits are configured in `~/.config/codex-shunt/config.json` using `context_tokens`, `reply_tokens`, and `max_payload_bytes`. The defaults are 8192, 1024, and 512000 respectively.

`bulk-read` checks the serialized JSON request against the **smaller** of `max_payload_bytes` and `context_tokens - reply_tokens` in bytes. `code-write` retains its original payload ceiling and does not auto-split generated-code context. Byte counting is deliberately conservative and does not determine the model's exact token count; providers may impose additional limits. Intermediate chunk summaries request at most 512 output tokens using Chat Completions `max_tokens`, so your provider must accept that field. Each chunk incurs an extra paid API call; there is no automatic retry.

Optional `timeout_seconds` defaults to 90 **per call**. Both the API and the Hook use the private config file. Environment-variable overrides are not supported.

## Security and practical limits

- **External worker sees the full content of every selected file**, not just the summary. Review sensitive, proprietary, personal, and secret data before delegating; minimal filename checks are not a DLP system. The Shunt config itself is explicitly blocked from delegation. HTTP is permitted only for localhost; remote API requires HTTPS and a key. Redirects are disabled.
- Hook is an optimization, **not a security boundary**. Pipelines, complex shell commands, Python scripts/heredocs, dynamic Python reads, MCP reads, and arbitrary custom tools are not automatically intercepted. `exec_command` uses the `Bash` Hook alias in Codex. The hook uses the session cwd, which may differ from a command-specific working directory; explicit paths remain the safest way to avoid ambiguity. Full-file input can still enter Codex context through such paths.
- Codex's local plugin/hook trust and environment may vary by client/version. This archive includes offline unit and mock-HTTP integration tests, not a live Codex or paid-model run.
- The adapter is stateless, does not automatically retry paid calls, and never overwrites existing target files. Intermediate summaries may lose cross-chunk details; verify exact code using targeted reads. Model output is untrusted code: review and test it before executing.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Tests use only Python standard library and a loopback mock server. No API key or external network required.
