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
mkdir -p ~/.config/codex-shunt
chmod 700 ~/.config/codex-shunt
```

新建 `~/.config/codex-shunt/config.json`，填入：

```json
{
  "api_base": "https://api.openai.com/v1",
  "model": "gpt-4o-mini",
  "api_key": "你的 API Key"
}
```

保存后执行：

```bash
chmod 600 ~/.config/codex-shunt/config.json
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

**Configure:** Create `~/.config/codex-shunt/config.json` using the JSON example above (`api_base`, `model`, `api_key`). On macOS/Linux, make the directory private and `chmod 600` the file. No environment-variable configuration.

**Use:** Ask Codex to use `shunt-bulk-reader` or `shunt-code-writer`. Remote workers receive selected source files; avoid secrets. Chunk summaries may miss details, and Hooks do not intercept every read.

---

Inspired by [Spotify Shunt](https://github.com/spotify/portal-ai-plugins/tree/main/plugins/shunt) (Apache-2.0). Independent community adaptation, not affiliated with Spotify. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
