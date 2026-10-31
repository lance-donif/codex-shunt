# Codex Shunt

[简体中文](#简体中文) · [English](#english)

## 简体中文

**让 Codex 把大文件阅读和重复代码生成交给更便宜的 AI 模型。** 支持 OpenAI 兼容的 Chat Completions API 和本地 Ollama，不需要 Spotify Portal。

**要求：** Python 3.9+、Codex CLI。

### 1. 安装

```bash
git clone https://github.com/lance-donif/codex-shunt.git
cd codex-shunt
codex plugin marketplace add "$PWD"
codex
```

在 Codex 输入 `/plugins` → 选择 **Codex Shunt (local)** → 安装 **Codex Shunt**。确认 Hook 权限后，新建一个任务。

### 2. 配置（不用 `export`）

```bash
mkdir -p ~/.config/codex-shunt
cp config.example.json ~/.config/codex-shunt/config.json
chmod 600 ~/.config/codex-shunt/config.json
```

编辑 `~/.config/codex-shunt/config.json`，重点修改这三项，其余设置可保留默认值：

```json
{
  "api_base": "https://api.openai.com/v1",
  "model": "gpt-4o-mini",
  "api_key": "填入你的 API Key"
}
```

使用 **Ollama**：将 `api_base` 改为 `http://127.0.0.1:11434/v1`，`model` 改为已下载的模型名，`api_key` 设为 `""`。

> 配置文件只保存在本机，**不要上传真实 API Key**。只支持配置文件，不支持用环境变量设置 Worker。

### 3. 使用

直接在 Codex 里说：

- **分析大文件**：“用 `shunt-bulk-reader` 分析 `src/app.py` 的主要逻辑。”
- **生成测试代码**：“用 `shunt-code-writer` 参考现有测试，生成新的测试文件。”

也可以在项目目录运行命令：

```bash
python3 plugins/shunt/scripts/shunt.py bulk-read --question "这个文件做什么？" --paths src/app.py
python3 plugins/shunt/scripts/shunt.py code-write --spec "生成单元测试" --reference tests/test_existing.py --target tests/test_new.py
```

### 注意

- 大文件会自动分片、汇总；**摘要可能遗漏细节**，修改代码前请核对原文件。
- 常见完整文件读取会触发 Hook，但**不是所有读取方式都能拦截**。
- 远程 Worker 会收到所选文件内容；不要委托敏感代码或密钥。代码生成不会覆盖已有目标文件。

测试：`python3 -m unittest discover -s tests -v`（不需要真实 API Key）。

## English

**Codex Shunt** delegates large source-file analysis and boilerplate generation to a cheaper OpenAI-compatible Chat Completions worker (including local Ollama). No Spotify Portal required. Python 3.9+.

1. **Install:** Clone this repository, run `codex plugin marketplace add "$PWD"` inside it, then install **Codex Shunt** via `/plugins` in Codex and start a new task.
2. **Configure:** Copy `config.example.json` to `~/.config/codex-shunt/config.json`, set file permissions to `600` on macOS/Linux, and edit `api_base`, `model`, `api_key`. Environment-variable configuration is not supported.
3. **Use:** Ask Codex to use `shunt-bulk-reader` for large files or `shunt-code-writer` for repetitive code generation. See the CLI examples above.

**Limits:** Large files are chunked and summarized, which can miss details. Hooks do not catch every read. Remote workers receive the selected source code; do not send secrets.

---

Inspired by [Spotify Shunt](https://github.com/spotify/portal-ai-plugins/tree/main/plugins/shunt) (Apache-2.0). This is an independent community adaptation, not affiliated with Spotify. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
