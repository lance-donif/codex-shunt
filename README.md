# Codex Shunt

[简体中文](#简体中文) · [English](#english)

## 简体中文

**让 Codex 把大文件分析、重复代码生成交给更便宜的 AI 模型。** 支持 OpenAI 兼容接口和 Ollama，不需要 Spotify Portal。

要求：Codex CLI、Python 3.9+。

### 1. 安装（无需下载项目）

```bash
codex plugin marketplace add lance-donif/codex-shunt
codex
```

进入 Codex 后输入 `/plugins`，找到 **Codex Shunt** 并安装，随后开启新任务。

### 2. 配置模型

创建本地配置目录：

```bash
mkdir -p ~/.codex/shunt
chmod 700 ~/.codex/shunt
```

新建 `~/.codex/shunt/config.json`，填入：

```json
{
  "api_base": "https://api.openai.com/v1",
  "model": "your-256k-context-model",
  "api_key": "你的 API Key",
  "context_tokens": 256000,
  "input_tokens": 256000,
  "reply_tokens": 128000,
  "max_payload_bytes": 512000,
  "timeout_seconds": 90,
  "min_lines": 350
}
```

| 参数 | 作用 |
| --- | --- |
| `api_base` | 模型 API 地址 |
| `model` | Worker 模型名称 |
| `api_key` | API 密钥（本地 Ollama 可留空） |
| `context_tokens` | 模型总窗口，默认 256000 |
| `input_tokens` | 最大输入上限，默认 256000（还要扣除输出预留） |
| `reply_tokens` | 最大输出上限，默认 128000 |
| `max_payload_bytes` | 单次请求大小上限，默认 512000 字节 |
| `timeout_seconds` | 每次 Worker 请求超时，默认 90 秒 |
| `min_lines` | Hook 自动拦截完整读取的行数阈值，默认 350 |

**总上下文只有 256000：输入与输出预留之和不能超过总窗口。** 默认长回复预留 128000 时，单次请求的有效输入最多约 128000（按保守字节估算）；分片摘要只预留 512 输出，因此可使用更大的输入片段。

仅 `api_base` 和 `model` 必填；其余参数省略时使用默认值。请填支持 256k 总上下文的模型，否则调低配置。

保存后执行：

```bash
chmod 600 ~/.codex/shunt/config.json
```

使用 **Ollama**：把 `api_base` 改为 `http://127.0.0.1:11434/v1`、`model` 改为已安装的模型名，`api_key` 设为 `""`。只需配置 JSON，不用 `export`。

### 3. 使用

在 Codex 中直接说：

- “使用 `shunt-bulk-reader` 分析 `src/app.py`。”
- “使用 `shunt-code-writer` 参考现有测试生成新测试。”

**注意：** 大文件会自动分片，但摘要可能遗漏细节；Hook 不会拦截所有文件读取方式。远程 Worker 会收到被委托的源代码，**不要发送密钥或敏感文件**。生成代码不会覆盖已有目标文件。

运行测试：`python3 -m unittest discover -s tests -v`（开发者克隆仓库后使用）。

## English

Delegate large source reads and boilerplate generation to an inexpensive OpenAI-compatible AI worker, including Ollama. Requires **Codex CLI** and **Python 3.9+**.

**Install directly from GitHub (no manual clone):**

```bash
codex plugin marketplace add lance-donif/codex-shunt
codex
```

Run `/plugins`, install **Codex Shunt**, and start a new task.

**Configure:** Create `~/.codex/shunt/config.json` with the nine options above: API address/model/key, context/input/output token limits, request size, timeout, and Hook threshold. The 256k total context is shared: a 128k maximum output leaves at most about 128k input for full-length replies. Only `api_base` and `model` are required; others have defaults. On macOS/Linux, keep the directory private and `chmod 600` the file. Environment variables are not supported.

**Use:** Ask Codex to use `shunt-bulk-reader` or `shunt-code-writer`. Remote workers receive selected source files; avoid secrets. Chunk summaries may miss details, and Hooks do not intercept every read.

---

Inspired by [Spotify Shunt](https://github.com/spotify/portal-ai-plugins/tree/main/plugins/shunt) (Apache-2.0). Independent community adaptation, not affiliated with Spotify. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
