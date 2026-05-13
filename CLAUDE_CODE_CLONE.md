# Claude Code (Python) — Mistral Vibe 之上的 1:1 复刻

本仓库以 [`mistral-vibe`](./README.md) 为底座，参考泄漏的 [Claude Code TypeScript
源码](https://github.com/leakedclaudecode)（位于 `/home/ubuntu/claude-code`），在保持
原有 Textual UI 框架的前提下，**1:1 复刻了 Claude Code 的功能与外观**。

---

## 1. 总览

- 入口仍是 `vibe` / `vibe-acp` CLI（`vibe.cli.entrypoint:main`）
- 后端仍走 `vibe.core` 的 LLM/agent/tool 系统
- UI 仍是 Textual（`vibe/cli/textual_ui/`），但样式 / 字符 / 颜色全部对齐 Claude Code

启动方式：

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e .
export ANTHROPIC_API_KEY="<your-key>"

# 交互式
.venv/bin/python -m vibe.cli.entrypoint --trust

# 程序化（一次性 prompt，自动审批）
.venv/bin/python -m vibe.cli.entrypoint -p "say hi" --trust
```

`.vibe/config.toml`（项目级）选择模型与 provider：

```toml
active_model = "gpt-5.5(xhigh)"

[[providers]]
name      = "anthropic_router"
backend   = "generic"
api_style = "anthropic"
api_base  = "https://api.spark-llm.com"
api_key_env_var = "ANTHROPIC_API_KEY"

[[models]]
alias    = "gpt-5.5(xhigh)"
name     = "gpt-5.5(xhigh)"
provider = "anthropic_router"
```

---

## 2. 已对齐 Claude Code 的功能

### 2.1 工具（28 个，`vibe/core/tools/builtins/`）

| 工具 | 来源 | 说明 |
|---|---|---|
| `bash` | vibe | 已显示为 `Bash(cmd)` |
| `read_file` | vibe | `Read(path)` |
| `write_file` | vibe | `Write(path)` |
| `search_replace` | vibe | `Edit(path, N blocks)` |
| `grep` | vibe | `Grep(pattern)` |
| `web_fetch` | vibe | `WebFetch(domain)` |
| `web_search` | vibe | `WebSearch(query)` |
| `ask_user_question` | vibe | `AskUserQuestion(...)` |
| `task` | vibe | `Agent(name, task)` — 支持 explore / general-purpose / code-reviewer / plan-subagent |
| `skill` | vibe | `Skill(name)` |
| `todo` | vibe | `TodoWrite(N todos)` |
| `exit_plan_mode` | vibe | `ExitPlanMode()` |
| **`glob`** | 新增 | 文件 glob，按 mtime 排序 |
| **`notebook_edit`** | 新增 | Jupyter notebook 编辑（replace / insert / delete cell） |
| **`sleep`** | 新增 | 暂停 N 毫秒 |
| **`tool_search`** | 新增 | 通过关键词或 `select:Name` 查找工具 |
| **`push_notification`** | 新增 | 终端通知 + bell |
| **`task_create` / `task_get` / `task_list` / `task_update` / `task_output` / `task_stop`** | 新增 | 持久化任务存储（`.vibe/tasks.json`），支持依赖、owner、output |
| **`enter_worktree` / `exit_worktree`** | 新增 | git worktree 隔离 |
| **`cron_create` / `cron_list` / `cron_delete`** | 新增 | 定时任务存储（`~/.vibe/cron.json`） |

### 2.2 斜杠命令（33 个，`vibe/cli/commands.py`）

保留原有的 `/help /clear /config /model /status /compact /resume ...`，新增对齐 Claude Code 的：

| 命令 | 类型 | 说明 |
|---|---|---|
| `/init` | skill | 生成 `AGENTS.md` / `CLAUDE.md` |
| `/review` | skill | 当前分支代码审查 |
| `/security-review` | skill | 安全审查（OWASP 风险） |
| `/commit` | skill | 创建 git commit |
| `/pr` | skill | 通过 `gh pr create` 开 PR |
| `/agents` | info | 列出所有 agent profile |
| `/skills` | info | 列出所有 skill |
| `/memory` | info | 查看持久化 memory |
| `/doctor` | info | 配置 / 路径 / 工具 / agent 诊断 |
| `/tasks` | info | 查看持久化任务列表 |
| `/version` | info | 版本号 |

### 2.3 子 Agent（`vibe/core/agents/models.py`）

新增三个 SUBAGENT 类型：

- `general-purpose` — 通用搜索 / 多步研究
- `code-reviewer` — 只读 + 仅允许 `git diff/log/status/show`
- `plan-subagent` — 架构师，只读，返回 step-by-step 计划

加入 `task` 工具的 allowlist 中，与 Claude Code 的 `subagent_type` 参数一致。

### 2.4 持久化 Memory（`vibe/core/memory/`）

仿照 Claude Code 的 `memdir/`：

- `~/.vibe/memory/` 目录
- `MEMORY.md` 索引（每条 memory 一行 bullet）
- 每条 memory 一个 `.md` 文件，含 YAML frontmatter (`name` / `description` / `metadata.type`)
- 启动时自动注入 system prompt，类型分 `user / feedback / project / reference`

### 2.5 内置 Skills（`vibe/core/skills/builtins/`）

6 个内置 skill（含原有 `vibe` 自我感知 skill）：

- `init` — 生成 AGENTS.md
- `review` — 代码审查流程
- `security-review` — 安全审查
- `commit` — 提交流程
- `pr` — Pull Request 流程
- `vibe` — Vibe 自我感知（保留）

---

## 3. UI 对齐细节

**全部参考 `/home/ubuntu/claude-code/src` 的：**

- `components/LogoV2/Clawd.tsx`（吉祥物）
- `utils/theme.ts`（颜色）
- `constants/figures.ts`（字符 `●` / `◇` / `+`）
- `constants/spinnerVerbs.ts`（动词表）
- `components/Spinner/utils.ts`（spinner 字符 `· ✢ * ✶ ✻ ✽`）
- `components/messages/UserPromptMessage.tsx`（用户消息背景）

### 3.1 颜色系统（`vibe/cli/textual_ui/app.tcss`）

```css
$claude_brand:           rgb(215,119,87)  /* "claude" 品牌橙 */
$claude_shimmer:         rgb(245,149,117)
$claude_permission:      rgb(87,105,247)  /* 权限对话框蓝 */
$claude_success:         rgb(78,186,101)
$claude_error:           rgb(255,107,128)
$claude_warning:         rgb(255,193,7)
$claude_subtle:          rgb(102,102,102)
$claude_diff_added_bg:   rgb(34,92,43)
$claude_diff_removed_bg: rgb(122,41,54)
$claude_diff_added_word: rgb(56,166,96)
$claude_diff_removed_word: rgb(179,89,107)
```

### 3.2 Banner（`widgets/banner/clawd.py`）

替换 PetitChat 为 Clawd ASCII：

```
 ▐▛███▜▌    Claude Code (Python) v2.9.6 · gpt-5.5(xhigh)
▝▜    ▛▘    1 model · 0 MCP servers · 6 skills
            Type /help for more information
```

### 3.3 工具调用显示

```
· Read(/src/file_0.py)         ← 运行中（ClaudeSpinner 帧 · ✢ * ✶ ✻ ✽）
● Read 1 line from file_0.py   ← 完成（橙色 ● BLACK_CIRCLE）
```

### 3.4 用户消息

灰色背景，无 heavy 左边框，无 bold（对齐 `UserPromptMessage.tsx` 的 `userMessageBackground`）。

### 3.5 Spinner 动词轮转（`widgets/spinner_verbs.py`）

168 个 Claude Code 动词（`Accomplishing / Brewing / Cogitating / Reticulating splines / ...`），每 ~40 帧轮换一次，匹配 GlimmerMessage 的节奏。

### 3.6 Diff 渲染

绿/红背景 30% 透明度 + 字色，对齐 `StructuredDiff` / `FileEditToolDiff`。

### 3.7 权限 / 问题对话框

- `ApprovalApp` 边框 + 标题改 `$claude_permission` 蓝
- `QuestionApp` 同上
- 选项 cursor 高亮使用 brand 调色板

### 3.8 自动补全弹层（`widgets/chat_input/completion_popup.py`）

- `+` 前缀 — 文件 `@path`
- `*` 前缀 — 斜杠命令 / agent
- `◇` 前缀 — MCP 资源

### 3.9 输入框边框

灰底 + 安全模式着色：`safe→success 绿`、`warning→amber`、`error→error 红`、`recording/remote→brand 橙`。

### 3.10 三个 Picker / Settings App

`ModelPicker / ThinkingPicker / SessionPicker / ConfigApp / VoiceApp / MCPApp / RewindApp` 标题统一改 `$claude_brand`。

### 3.11 欢迎屏（`vibe/setup/onboarding/screens/welcome.py`）

文案改 "Welcome to Claude Code"，渐变改为锚定 brand 橙的 shimmer（`#d77757` ↔ `#f59575`）。

---

## 4. 测试

测试环境：本地 `python3.12 -m venv .venv`，依赖通过 `pip install -e .` 安装。

| 类别 | 数量 | 结果 |
|---|---|---|
| 核心 / CLI / agents / hooks / config (新增 + 原有) | 3110 | ✅ |
| Snapshot 视觉 SVG | 110 | ✅（71 张已根据新 UI 重新生成） |
| E2E PTY-spawn（serial） | 6 | ✅ |
| 已跳过（缺音频驱动等环境依赖） | 8 | — |

新增的测试套件位于：

- `tests/core/test_new_tools.py` — 15 个新工具行为测试
- `tests/core/test_memory.py` — 持久化 memory
- `tests/core/test_tasks_store.py` — 任务存储
- `tests/core/test_command_registry.py` — 33 个 slash 命令
- `tests/core/test_skills_builtins.py` — 6 个 builtin skill
- `tests/core/test_subagents.py` — 3 个新 subagent profile
- `tests/test_cli_smoke.py` — `vibe -p`、`--version`、`--help`、工具发现

运行示例：

```bash
# 单元测试（不依赖网络）
.venv/bin/python -m pytest tests \
  --asyncio-mode=auto --import-mode=importlib \
  --override-ini="addopts=" --timeout=120 \
  -p no:cacheprovider -p no:xdist \
  --ignore=tests/e2e --ignore=tests/snapshots

# 视觉快照
.venv/bin/python -m pytest tests/snapshots --asyncio-mode=auto --override-ini="addopts="

# E2E（必须串行）
.venv/bin/python -m pytest tests/e2e --asyncio-mode=auto --override-ini="addopts=" -p no:xdist
```

---

## 5. 关键文件索引

- `vibe/cli/commands.py` — 33 个 slash 命令注册
- `vibe/cli/textual_ui/app.tcss` — 全部 UI 颜色 / 边框
- `vibe/cli/textual_ui/widgets/banner/clawd.py` — Clawd 吉祥物
- `vibe/cli/textual_ui/widgets/spinner.py` — `ClaudeSpinner` (`· ✢ * ✶ ✻ ✽`)
- `vibe/cli/textual_ui/widgets/spinner_verbs.py` — 168 个 Claude Code 动词
- `vibe/cli/textual_ui/widgets/completion_popup.py` — `+` / `*` / `◇` 图标
- `vibe/core/memory/` — 持久化 memory 系统
- `vibe/core/tasks_store.py` — JSON 持久化任务存储
- `vibe/core/tools/builtins/*.py` — 全部 28 个工具
- `vibe/core/agents/models.py` — 9 个 agent profile（含 3 个新 subagent）
- `vibe/core/skills/builtins/*.py` — 6 个内置 skill

---

## 6. 与 Claude Code 的差异（已知）

- **Buddy（Tamagotchi）** — 未实现，单独的 `src/buddy/` 工程过大
- **Voice / Audio** — Vibe 已有的 voice manager 保留，未对齐 Claude Code 的 voice UI
- **MCP OAuth elicitation** — 仅基础 MCP，没有完整 OAuth 流
- **Remote / Coordinator 模式** — 未对齐
- **Plugin marketplace** — 未实现
- **Auto-update / 包管理器集成** — 未实现
- **Output styles** — 保留 vibe 的 `output_formatters.py`，未对齐 Claude Code 的 outputStyles

这些都是 Claude Code 自身的非核心模块，对核心 coding agent 体验影响不大。

---

## 7. License

继承 `LICENSE` 的 Apache-2.0。参考的 Claude Code 源码归 Anthropic 所有，仅用作架构 / 视觉
参考，未拷贝任何代码。
