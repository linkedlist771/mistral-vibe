# 第三方源码运行 Vibe + 自定义模型

把 Mistral Vibe 接到自建/三方 LLM 网关（如 `https://api.spark-llm.com`），从仓库源码直接启动、免审批、免信任提示的最小操作手册。

---

## 1. 准备工作

### 1.1 拉依赖

仓库已经带了 `.venv`，直接用即可；首次或想重建：

```bash
cd /Users/dingli/Desktop/GitHubProjects/mistral-vibe
uv sync                          # 推荐
# 或
python3.12 -m venv .venv && .venv/bin/pip install -e .
```

### 1.2 配置 Provider + 模型

在项目根目录的 `.vibe/config.toml`（**项目级**，优先生效）或 `~/.vibe/config.toml`（**用户级**，全局兜底）写入：

```toml
active_model = "gpt-5.5(xhigh)"

[[providers]]
name = "anthropic"
backend = "generic"
api_style = "anthropic"
api_base = "https://api.spark-llm.com"
api_key_env_var = "ANTHROPIC_API_KEY"

[[models]]
alias = "gpt-5.5(xhigh)"
name = "gpt-5.5(xhigh)"
provider = "anthropic"
input_price = 5.0
output_price = 25.0
thinking = "off"
auto_compact_threshold = 200000

[[models]]
alias = "gpt-5.5(high)"
name = "gpt-5.5(high)"
provider = "anthropic"
input_price = 5.0
output_price = 25.0
thinking = "off"
auto_compact_threshold = 200000
```

字段说明（对应 `vibe/core/config/_settings.py`）：

| 字段 | 含义 |
|------|------|
| `backend` | `generic` / `mistral`；接三方网关用 `generic` |
| `api_style` | `anthropic` / `openai`；告诉 Vibe 用什么协议格式打请求 |
| `api_base` | 三方网关 HTTP 入口（不含 `/v1/messages` 这类后缀，Vibe 自己拼） |
| `api_key_env_var` | Vibe 读哪个环境变量当 API key（不是直接填 key） |
| `active_model` | 默认激活的模型 alias，必须能在 `[[models]]` 里找到 |

> ⚠️ `api_key_env_var = "ANTHROPIC_API_KEY"` 意味着 Vibe 启动时会读 `os.environ["ANTHROPIC_API_KEY"]`，**配置文件里不存 key**。

---

## 2. 启动

### 2.1 一行命令（推荐写法）

```bash
export ANTHROPIC_BASE="https://api.spark-llm.com"   # 备用，部分 SDK 会读
export ANTHROPIC_API_KEY="local-router-key"

.venv/bin/python -m vibe.cli.entrypoint --agent auto-approve --trust
```

### 2.2 直接跑入口文件（等价）

```bash
export ANTHROPIC_API_KEY="local-router-key"
.venv/bin/python vibe/cli/entrypoint.py --agent auto-approve --trust
```

### 2.3 用 uv 接管（如果依赖能正常解析）

```bash
ANTHROPIC_API_KEY="local-router-key" \
  uv run python -m vibe.cli.entrypoint --agent auto-approve --trust
```

> 三种写法等价，对应 `pyproject.toml` 里的入口：
> `vibe = "vibe.cli.entrypoint:main"`

---

## 3. 关键开关

### 3.1 `--agent auto-approve` —— 跳过所有工具审批

内置 agent，会把 `bypass_tool_permissions` 打开，bash / 写文件 / 网络请求等 tool call 直接执行，无弹窗。

- 等价 Claude Code 的 `--dangerously-skip-permissions`
- 仅在受信任目录 + 信任的 prompt 来源下使用
- 想持久化：在 `.vibe/config.toml` 加 `default_agent = "auto-approve"`

### 3.2 `--trust` —— 跳过目录信任提示

第一次进某目录时 Vibe 会弹「是否信任此目录」对话框。脚本/无人值守必须加 `--trust`：

- 仅本次会话有效，不写 `trusted_folders.toml`
- 想永久信任：交互模式下选 "Yes" 持久化，或手动编辑 `~/.vibe/trusted_folders.toml`

### 3.3 `-p / --prompt` —— 一次性程序化模式

```bash
.venv/bin/python -m vibe.cli.entrypoint \
  -p "把 README 翻译成英文" --trust
```

`-p` 模式默认就是 auto-approve（不用再加 `--agent`），跑完直接退出，适合 CI / 脚本。

---

## 4. 常用组合

```bash
# 完全无人值守 + 自定义 base + 自定义 key
export ANTHROPIC_API_KEY="local-router-key"
.venv/bin/python -m vibe.cli.entrypoint -p "做点啥" --trust

# 交互式 + 免审批 + 指定工作目录
.venv/bin/python -m vibe.cli.entrypoint \
  --workdir /some/project \
  --agent auto-approve --trust

# 续接最近会话 + 免审批
.venv/bin/python -m vibe.cli.entrypoint -c --agent auto-approve

# 临时切到另一个模型 alias（不改配置文件）
VIBE_ACTIVE_MODEL='gpt-5.5(high)' \
  .venv/bin/python -m vibe.cli.entrypoint --agent auto-approve --trust
```

> 环境变量覆盖配置：任何 `vibe.core.config._settings.Settings` 里的字段都可以用 `VIBE_<FIELD>` 覆盖，例如 `VIBE_ACTIVE_MODEL`、`VIBE_DEFAULT_AGENT` 等。

---

## 5. 验证连通性

最快的检查：

```bash
export ANTHROPIC_API_KEY="local-router-key"
.venv/bin/python -m vibe.cli.entrypoint -p "say hi in one word" --trust
```

- 看到模型返回的一个单词 → 网关、key、`api_style`、`active_model` 全部 OK
- 401/403 → `ANTHROPIC_API_KEY` 没传或网关不认这个 key
- `Unknown model` / `model not found` → `active_model` 的 alias 和 `[[models]].alias` 不一致
- 连接超时 → `api_base` 错或网络不通；也可用 `HTTP_PROXY` / `HTTPS_PROXY` 走代理（见 [docs/proxy-setup.md](docs/proxy-setup.md)）

---

## 6. 排错速查

| 现象 | 可能原因 |
|------|---------|
| `mistralai==2.4.4` 解析失败 | 用 `.venv/bin/python` 跑（仓库自带的 venv 已装好），不要重新走 `uv run` |
| 启动弹「是否信任此目录」 | 忘加 `--trust`，或想永久信任就选 Yes |
| 工具调用还是弹审批 | 没用 `--agent auto-approve`，或被 `default_agent` 配置覆盖 |
| 走了 mistral.ai 而不是三方网关 | `active_model` 指向了 mistral provider 的模型，检查 `[[models]].provider` 是否指向你新建的 provider |
| 想用 OpenAI 协议而不是 Anthropic | 把 `api_style = "anthropic"` 改成 `api_style = "openai"` |

---

## 7. 相关文件 / 参考

- 入口：`vibe/cli/entrypoint.py`（命令行参数定义在 `parse_arguments`）
- 配置模型：`vibe/core/config/_settings.py`（`ProviderConfig` / `ModelConfig` / `Settings`）
- 内置 agent：`vibe/core/agents/models.py`（`AUTO_APPROVE` 定义）
- 代理设置：[docs/proxy-setup.md](docs/proxy-setup.md)
- 源码运行通用说明：[docs/run-from-source.md](docs/run-from-source.md)
