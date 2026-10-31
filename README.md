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

**日常使用不要运行 Shunt 插件自身的测试**（`tests/test_shunt.py` / `python3 -m unittest discover -s tests`）。这些测试只用于明确要求开发或验证 Shunt 插件本身的维护任务；**用户项目的测试不受影响**，Codex 在修改用户代码后仍应按任务需要运行。

**安装后在 `/hooks` 审查并信任 Shunt 的 `PreToolUse` Hook**，否则它不会执行。之前安装过旧版的，请刷新并重装一次（不会删除 `~/.codex/shunt/config.json`）：

```bash
codex plugin marketplace upgrade codex-shunt-local
codex plugin remove shunt@codex-shunt-local
codex plugin add shunt@codex-shunt-local
```

升级后重新启动 Codex，并在 `/hooks` 检查。旧版根目录 `plugin.json` 会触发 [Codex 已知的 Hook 加载问题](https://github.com/openai/codex/issues/47925)；现在改用 `.codex-plugin/plugin.json` 兼容格式。

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
  "max_concurrency": 5,
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
| `max_concurrency` | 每个模型同时最多 5 个 Worker 请求；A 满额转 B，全部满额交由 Codex 处理，不记录模型故障 |
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


**进度：** CLI 会向 `stderr` 报告文件数、分片序号、模型请求与耗时；请求等待期间每 10 秒发送心跳，不污染 `stdout`。完整读取、分片和汇总请求均携带由插件生成的 `source_file_count`、路径、`source_id`，不再添加容易误导的行号标记；需要精确位置时由 Codex 读取原文件定位。不使用 SSE 流式输出。

**注意：** Windows 上 CLI 的标准输出和错误输出强制使用 UTF-8；Worker HTTP 响应按 `Content-Type` 字符集（未声明时 UTF-8）解码。全部模型并发满额时，不等待、不排队，Codex 应直接完成任务。请求占用的是跨进程系统文件锁，进程退出自动释放。冷却或停用时 Hook 会放行 Codex 自己读取文件；不会后台重试。远程 Worker 会收到选中的源文件，切勿委托密钥或敏感内容。超时切换可能重复计费；摘要可能漏掉跨分片细节。生成代码不会覆盖已有文件。

仅限插件维护者：明确需要开发或验证 **Shunt 本身**时才执行 `python3 -m unittest discover -s tests -v`，普通使用者及 Codex 处理其他项目时不应运行该测试。

## English

Codex plugin for low-cost AI workers, with ordered multi-provider fallback and Ollama support. Requires Codex CLI and Python 3.9+.

**Install:** `codex plugin marketplace add lance-donif/codex-shunt`, then install **Codex Shunt** via `/plugins` and start a new task. Review and trust `PreToolUse` in `/hooks`. If upgrading from an older version, run `codex plugin marketplace upgrade codex-shunt-local`, remove `shunt@codex-shunt-local`, and install it again. Two standalone Python CLI commands (`bulk-read`, `code-write`) are also available in `plugins/shunt/scripts/shunt.py`.

**Tests:** Do not automatically run the Shunt plugin's own tests (`tests/test_shunt.py` or `python3 -m unittest discover -s tests`) while using the plugin. They are maintainer-only unless explicitly requested. Run tests belonging to the user's project when appropriate.

**Configure:** Create `~/.codex/shunt/config.json` using [config.example.json](config.example.json). Models cycle A → B → C on failure; success keeps the pointer. A complete failure pauses calls for 30 minutes. Another complete failure after cooldown disables Worker calls until **both** failure timestamps are manually set to `null`. Timeout defaults to 300 seconds per model. `max_concurrency` defaults to 5 requests per provider; when all are busy Codex should handle the task itself without marking providers failed. Set model-specific reasoning parameters and context limits if your provider supports them. `chunk_summary_tokens` defaults to **8192** (capped by each model’s reply budget). On Unix, protect the directory (`700`) and file (`600`). No environment variables are used.

**Progress:** stderr reports file counts, chunk stages, provider timings and a 10-second heartbeat during requests; stdout stays answer-only. Requests retain a source manifest with source IDs and paths, without generated line-number markers. Codex must locate exact code in the original files. No SSE dependency.

**Windows:** CLI stdout/stderr use UTF-8 regardless of console codepage; HTTP JSON decoding honors response charset or defaults to UTF-8.

**Safety:** Remote providers receive selected source files. Fallback after timeouts may cause duplicate charges; chunk summaries may omit details. Hooks do not intercept every read.

---

Inspired by [Spotify Shunt](https://github.com/spotify/portal-ai-plugins/tree/main/plugins/shunt) (Apache-2.0). Independent community adaptation, not affiliated with Spotify. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
