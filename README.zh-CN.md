# Sub-Agent Delegation 控制层

**主 Agent 什么时候该把任务交给 sub-agent？sub-agent 在运行时到底被什么真正约束？**

[English](README.md) | **中文**

[![Made for OpenCode](https://img.shields.io/badge/made%20for-OpenCode-000000?style=flat-square)](https://opencode.ai)
[![类型：Delegation 控制层](https://img.shields.io/badge/type-control%20layer-6f42c1?style=flat-square)](#)
[![运行时格式：JSON](https://img.shields.io/badge/contract-JSON%20only-success?style=flat-square)](#)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

> 一个面向 coding agent 的 delegation 决策框架与运行时强制层。
> 不是“更多 Agent = 更先进”。这是关于**谁被允许做什么，由运行时来强制**。

---

## 核心思想

> **Sub-agent 不是能力扩展，而是运行时上下文分裂（runtime context fork）。**
> **Agent 可以决定“要不要 delegation”，但不能决定 delegation 获得什么权限。**

```text
Instructions 告诉 Agent 它应该做什么。
Runtime policy 决定它被允许做什么。
```

---

## 强制模型（先读这段）

本仓库有三层，互不等价：

| 层级 | 含义 | 位置 |
|---|---|---|
| **RUNTIME ENFORCED** | 违规会在 OpenCode 进程内、在工具执行前或无论模型意图如何被中止。 | OpenCode `permission` 配置、plugin `tool.execute.before` |
| **PARTIALLY ENFORCED** | 只覆盖部分情况，可以绕过。 | `bash` 命令前缀规则、post-tool 检测 |
| **DOCUMENTATION ONLY** | 只是“要求”模型遵守，没有任何东西阻止它。 | `SKILL.md`、`AGENTS.md`、`/delegate` prompt |

### 真实执行链

```text
Agent（LLM 发出 tool call）
   ↓
OpenCode runtime
   ├─ permission 检查（config.permission / agent frontmatter）   [原生，RUNTIME ENFORCED]
   ├─ plugin hook  tool.execute.before（throw = 中止）            [原生，RUNTIME ENFORCED]
   ↓
Tool 实现（bash / edit / write / read / task / ...）
   ├─ plugin hook  tool.execute.after（仅检测）                  [原生，DETECTION ONLY]
   ↓
OS / filesystem / shell   ← bash 启动后唯一的硬边界
```

`bin/subagent-guard`（Python）**不在**这条链上。它是离线 verifier。
只有 Agent 主动调用它时它才起作用——那属于 DOCUMENTATION ONLY。

---

## 仓库内容

| 路径 | 用途 | 层级 |
|---|---|---|
| `plugin/guard.js` | OpenCode plugin。在 `tool.execute.before` 强制契约；越权的 `read`/`edit`/`write` 直接中止。 | **RUNTIME ENFORCED** |
| `contracts/opencode.permission.example.jsonc` | 原生 `permission` 基线（外部目录、密钥、破坏性前缀）。 | 合并后 **RUNTIME ENFORCED** |
| `contracts/agent.example.md` | 原生 per-subagent `permission` frontmatter。 | 使用后 **RUNTIME ENFORCED** |
| `contracts/schema.json`、`contracts/example-contract.json` | Delegation Contract schema 与示例。JSON 是唯一运行时格式。 | — |
| `test/guard-plugin.test.mjs` | 测试真实 plugin hook：范围内放行，越权/穿越/受保护路径拒绝，bash 检测。 | — |
| `guard/`、`bin/subagent-guard` | 离线 verifier / policy 计算器。不是边界。 | DOCUMENTATION ONLY |
| `SKILL.md` | delegation 决策模型（7 价值、13 因子、5 触发、5 否决、分层授权）。 | DOCUMENTATION ONLY |
| `global/AGENTS.md`、`global/command/delegate.md` | 全局钩子 + `/delegate` prompt。 | DOCUMENTATION ONLY |
| `demo/` | 通过离线 verifier 跑的边界 demo（6 用例）。 | — |
| `install.sh` | 纯本地安装脚本（钩子、命令、plugin、verifier 软链）。 | — |

---

## 安装（本地、离线、不碰密钥）

```bash
git clone https://github.com/henryliu443/subagent-delegation.git
cd subagent-delegation
./install.sh
```

会把 plugin 放到 `~/.config/opencode/plugins/guard.js`，OpenCode 自动加载。
**没有契约时 plugin 完全惰性**，不会影响无关项目。

按项目激活：

```bash
# 方式 A：项目内契约
mkdir -p .opencode
cp /path/to/example-contract.json .opencode/delegation-contract.json

# 方式 B：显式路径
export DELEGATION_CONTRACT=/abs/path/contract.json
```

---

## Delegation Contract（JSON —— 唯一运行时格式）

```json
{
  "delegation": {
    "id": "delegate-001",
    "goal": "审计 JWT 过期处理并补充负向测试",
    "context": {
      "include": ["src/auth/**", "tests/auth/**"],
      "exclude": [".git/**", "secrets/**", "**/.env*"]
    },
    "authority": {
      "read": ["src/auth/**", "tests/auth/**"],
      "write": ["tests/auth/**"],
      "execute": ["pytest tests/auth"],
      "deny": ["git push*", "git reset --hard*", "git clean*", "rm -rf*", "delete", ".git/**"]
    },
    "return": { "format": "structured", "required": ["status", "findings", "evidence", "uncertainty"] },
    "verification": { "required": true, "commands": ["pytest tests/auth"] },
    "budget": { "max_tokens": 20000, "max_duration_seconds": 300 }
  }
}
```

> YAML 可出现在文档里便于阅读，但**运行时永不解析 YAML**。运行时只解析 JSON。

---

## plugin 如何强制

在 `tool.execute.before`（已在实际 `app.asar` 中验证：该 hook 在 `tool.execute` **之前**被 await），
对 `read` / `edit` / `write` / `patch`：

1. 用 workspace root 解析 `args.filePath`。
2. 路径含 `..` → **DENY**。
3. 解析后逃出 workspace root → **DENY**。
4. 触碰 `.git` → **DENY**。
5. 命中 `context.exclude` 或 `authority.deny` → **DENY**。
6. 不匹配 `authority.read`（读）或 `authority.write`（写）→ **DENY**。
7. 否则放行。

任何 DENY 都会 throw，工具调用不会执行。

`tool.execute.after` 只对 `bash` 运行，且是 **DETECTION ONLY**——报告 `authority.write` 之外被改动的文件，
无法阻止 bash 已经做出的改动。

---

## 原生 OpenCode permission

能用原生 `permission` 静态表达的都交给它。见 `contracts/opencode.permission.example.jsonc`
（基线）与 `contracts/agent.example.md`（per-subagent frontmatter）。要点：

- `external_directory` —— workspace 之外的路径。
- `read` —— 密钥文件模式。
- `bash` —— 命令前缀规则。**PARTIALLY ENFORCED**：前缀是字符串匹配，可用 `python3 -c`、变量拼接、base64 绕过。

---

## 验证

```bash
node test/guard-plugin.test.mjs   # plugin 强制（before + after）
./demo/run_demo.sh                # 离线 verifier 边界 demo
```

---

## 强制级别对照表（准确版）

| 机制 | 层级 | 支撑 |
|---|---|---|
| 契约的 `read`/`edit`/`write` 路径边界 | **RUNTIME ENFORCED** | plugin `tool.execute.before`（执行前 throw） |
| `..` 穿越 / 逃出 workspace | **RUNTIME ENFORCED** | plugin `tool.execute.before` |
| `.git` 保护 | **RUNTIME ENFORCED** | plugin `tool.execute.before` |
| `external_directory` | **RUNTIME ENFORCED** | 原生 `permission` |
| per-subagent `edit: deny` 等 | **RUNTIME ENFORCED** | 原生 agent frontmatter |
| `bash` 破坏性命令 | **PARTIALLY ENFORCED** | 原生 `permission.bash` 前缀 + plugin after-hook 检测 |
| `bash` 的文件系统效果 | **PARTIALLY ENFORCED** | after-hook 只能检测，无法阻止 |
| post-tool 变更审计 | **DETECTION ONLY** | plugin `tool.execute.after` |
| `bin/subagent-guard` CLI | **DOCUMENTATION ONLY** | 仅在主动调用时生效 |
| delegation 决策 / `/delegate` 输出 | **DOCUMENTATION ONLY** | prompt |

---

## 威胁模型：agent 能否关掉 guard？

针对实际安装布局审计。“Agent” = 持有 `bash` + `edit`/`write` 的 subagent。

| 攻击 | 走 `edit`/`write` 工具 | 走 `bash` |
|---|---|---|
| 覆写 `~/.config/opencode/plugins/guard.js` | **已阻断**（路径逃出 workspace） | **可绕过**（已实测：bash 改写了文件） |
| 修改 `~/.config/opencode/opencode.jsonc` | **已阻断** | **可绕过** |
| 修改契约 `<ws>/.opencode/delegation-contract.json` | **已阻断** | **可绕过** |
| 先放宽契约再操作 | 先阻断，但契约会被重读 | **可绕过**（每次调用都重读契约） |
| 在子 shell 里 `export DELEGATION_CONTRACT=...` | — | **已阻断**（子进程环境不影响 OpenCode 进程） |
| 把 `export` 写进 `~/.zshrc` | — | **下次重启后可绕过** |
| 往 `.opencode/plugins/` 丢新 plugin | — | **未验证**（需要重启才加载） |

对持有 `bash` 的 agent 而言，guard **不是信任边界**：plugin、原生配置、契约都是普通用户可写文件，
而 post-tool 检测看不到它们（它们在 git 仓库之外）。

---

## 已知绕过路径（如实列出）

1. **`bash` 是最大缺口。** plugin 看到的 `bash` 是不透明字符串。持有 `bash` 的 subagent 可以覆写 `guard.js`、OpenCode 配置或契约。这是**实测复现**，不是推测。真正隔离需要 OS 沙箱（容器/`bwrap`/受限用户），或把 `bash` 限制在安全前缀白名单内。
2. **契约每次调用都重读。** 它是可变文件；放宽它会立刻改变后续 tool call 的策略。guard 不会对自身契约做 pin 或 hash。
3. **post-tool 检测被限制在仓库内。** `git status` 看不到仓库之外的写入，因此对 plugin 或全局配置的篡改对 after-hook 不可见。
4. **契约作用域是进程级。** hook 处没有 per-session 身份。per-subagent 作用域必须靠原生 agent frontmatter。
5. **`DELEGATION_CONTRACT` 是进程环境变量。** 子 shell 无法在运行时改它，但写进 shell profile 并重启 OpenCode 后就会生效。

**结论：** 路径边界对 `read`/`edit`/`write` 工具是真实的；但对能执行任意 `bash` 的 agent **不是**边界。
要关闭它需要 OS 级隔离；在同一个进程、同一套文件权限下无法关闭。

---

## 许可证

MIT
