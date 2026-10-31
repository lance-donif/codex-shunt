# Codex Shunt

[简体中文](#简体中文) · [English](#english)

## 简体中文

让 Codex 把**大文件阅读、重复代码生成**交给成本更低的 AI Worker。支持多个厂家、自动故障转移和 Ollama，无需 Spotify Portal。要求 **Codex CLI + Python 3.9+**。

### 1. 安装

```bash
codex plugin marketplace add lance-donif/codex-shunt
codex
```

在 Codex 里输入 `/plugins`，安装 **Codex Shunt**，然后开启新任务。

### 2. 配置

先创建私有配置目录：

```bash
mkdir -p ~/.codex/shunt
chmod 700 ~/.codex/shunt
```

然后新建 `~/.codex/shunt/config.json`（**不是** Codex 的 `config.toml`）。参考仓库的 [config.example.json](config.example.json)，配置格式如下：

```json
{
  "models": [
    {"name": "A", "api_base": "https://provider-a.example/v1", "model": "model-a", "api_key": "KEY_A"},
    {"name": "B", "api_base": "https://provider-b.example/v1", "model": "model-b", "api_key": "KEY_B"},
    {"name": "C", "api_base": "https://provider-c.example/v1", "model": "model-c", "api_key": "KEY_C"}
  ],
  "current_model": 0,
  "first_failure_at": null,
  "second_failure_at": null,
  "context_tokens": 256000,
  "input_tokens": 256000,
  "reply_tokens": 128000,
  "max_payload_bytes": 512000,
  "chunk_summary_tokens": 8192,
  "timeout_seconds": 300,
  "min_lines": 350
}
```

将厂家地址、模型名和密钥替换成真实值。**模型按数组顺序 A → B → C → A 循环**；成功后保持当前模型，失败才切换。每次最多尝试每个模型一次。

| 参数 | 用途 |
| --- | --- |
| `current_model` | 当前模型下标：`0` 为 A、`1` 为 B、`2` 为 C；插件自动保存 |
| `first_failure_at` | 全部失败一次后的时间；30 分钟内暂停请求 |
| `second_failure_at` | 冷却后再全部失败则永久停用；**把两个时间改回 `null` 才恢复** |
| `context_tokens` | **总上下文**，默认 256000；输入与输出共享 |
| `input_tokens` / `reply_tokens` | 最大输入 / 输出：256000 / 128000（并非可以同时用满） |
| `max_payload_bytes` | HTTP 请求大小上限，默认 512000 字节 |
| `chunk_summary_tokens` | 每个分片及中间汇总的最大输出，默认 **8192**，仍受模型 `reply_tokens` 和上下文限制 |
| `timeout_seconds` | **每个模型**超时，默认 300 秒（深度思考可单独设 600） |
| `min_lines` | Hook 自动拦截完整文件读取的阈值，默认 350 行 |

每个模型还可单独设置 `context_tokens`、`input_tokens`、`reply_tokens`、`timeout_seconds`，以及可选的 `reasoning_effort`（如 `low`、`medium`、`high`）和 `token_field`（`max_tokens` 或 `max_completion_tokens`，按厂家要求选择）。**不支持的思考参数不要填写。** 分片按所有模型中最小的有效上下文预算计算；深度思考模型可以调大 `chunk_summary_tokens`，但会增加调用成本。

保存配置后：

```bash
chmod 600 ~/.codex/shunt/config.json
```

本地 **Ollama** 将 `api_base` 设为 `http://127.0.0.1:11434/v1`、`api_key` 设为 `""`。不使用 `export` 环境变量。

### 3. 使用

在 Codex 里说“用 `shunt-bulk-reader` 分析大文件”或“用 `shunt-code-writer` 参考已有测试生成新测试”。
也能直接调用脚本（在源码目录运行）：

```bash
python3 plugins/shunt/scripts/shunt.py bulk-read --question "这个模块做什么？" --paths src/app.py
python3 plugins/shunt/scripts/shunt.py code-write --spec "生成单元测试" --reference tests/existing.py --target tests/new.py
```


**注意：** 冷却或停用时 Hook 会放行 Codex 自己读取文件；不会后台重试。远程 Worker 会收到选中的源文件，切勿委托密钥或敏感内容。超时切换可能重复计费；摘要可能漏掉跨分片细节。生成代码不会覆盖已有文件。

测试（开发者克隆仓库后）：`python3 -m unittest discover -s tests -v`。

## English

Codex plugin for low-cost AI workers, with ordered multi-provider fallback and Ollama support. Requires Codex CLI and Python 3.9+.

**Install:** `codex plugin marketplace add lance-donif/codex-shunt`, then install **Codex Shunt** via `/plugins` and start a new task. Two standalone Python CLI commands (`bulk-read`, `code-write`) are also available in `plugins/shunt/scripts/shunt.py`.

**Configure:** Create `~/.codex/shunt/config.json` using [config.example.json](config.example.json). Models cycle A → B → C on failure; success keeps the pointer. A complete failure pauses calls for 30 minutes. Another complete failure after cooldown disables Worker calls until **both** failure timestamps are manually set to `null`. Timeout defaults to 300 seconds per model. Set model-specific reasoning parameters and context limits if your provider supports them. `chunk_summary_tokens` defaults to **8192** (capped by each model’s reply budget). On Unix, protect the directory (`700`) and file (`600`). No environment variables are used.

**Safety:** Remote providers receive selected source files. Fallback after timeouts may cause duplicate charges; chunk summaries may omit details. Hooks do not intercept every read.

---

Inspired by [Spotify Shunt](https://github.com/spotify/portal-ai-plugins/tree/main/plugins/shunt) (Apache-2.0). Independent community adaptation, not affiliated with Spotify. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
