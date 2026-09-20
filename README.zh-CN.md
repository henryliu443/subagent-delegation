# Sub-Agent Delegation Skill

**主 Agent 什么时候应该把任务交给 sub-agent，什么时候应该自己做？**

[English](README.md) | **中文**

[![Made for OpenCode](https://img.shields.io/badge/made%20for-OpenCode-000000?style=flat-square)](https://opencode.ai)
[![类型：Agent Skill](https://img.shields.io/badge/%E7%B1%BB%E5%9E%8B-Agent%20Skill-6f42c1?style=flat-square)](#)
[![状态：开放问题](https://img.shields.io/badge/%E7%8A%B6%E6%80%81-%E5%BC%80%E6%94%BE%E9%97%AE%E9%A2%98-orange?style=flat-square)](#开放问题)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

> 一个给 coding agent 用的 delegation 决策框架。
> 不是"更多 Agent = 更先进"。这是关于 **delegation 的边界与经济性**。

---

## 这是什么

这个 repo 是一个可安装的 OpenCode skill（也可适配其他 coding agent）。它精确回答一个问题：

> **什么情况下，把一个任务交给 sub-agent 产生的价值大于它的成本？**

它**不是** sub-agent 的实现，而是一个决策模型：结构化的判断某个任务该分叉给 sub-agent、该主 Agent 自己做、还是混合处理。

### 核心原则

> **Sub-agent 不是能力扩展，而是运行时上下文分裂（context fork）。**

一个 sub-agent 是被授予以下东西的执行单元：
- 一个**局部目标**
- 一个**局部上下文**（与主 Agent 的 context window 隔离）
- 一个**局部权限**（限定的行动范围）
- 一个**返回契约**（结构化结果，而非对话）

它是否作为独立进程、独立模型、独立 prompt 运行，都是实现细节。架构含义是：**context 被分叉，只有契约化的结果流回来。**

---

## 仓库内容

| 文件 | 用途 |
|---|---|
| `SKILL.md` | delegation 决策模型——7 种 delegation 价值、13 个因子、5 个触发条件、5 个否决条件、返回契约、分层授权架构 |
| `global/AGENTS.md` | 安装到 `~/AGENTS.md` 的全局钩子——让 Agent 在 spawn sub-agent 前先查 `SKILL.md` |
| `global/command/delegate.md` | OpenCode 的全局 `/delegate` 斜杠命令 |
| `install.sh` | 一键安装脚本，放置全局钩子和命令 |
| `AGENTS.md` | 项目级 Agent 配置 |

---

## 安装

```bash
git clone https://github.com/henryliu443/subagent-delegation.git
cd subagent-delegation
./install.sh
```

`install.sh` 做两件事：

1. 复制 `global/AGENTS.md` → `~/AGENTS.md`（全局 delegation 钩子）
2. 复制 `global/command/delegate.md` → `~/.config/opencode/command/delegate.md`（全局 `/delegate` 命令）

之后在**任意**项目里打开 OpenCode，钩子即生效。

> **API key 说明：** 本仓库不含任何密钥。Provider 配置（`~/.config/opencode/opencode.jsonc`）留在本地，永不提交。

---

## 使用方式

### 自动

安装后，全局钩子会让 Agent 在 spawn 任何 sub-agent 前先查 `SKILL.md`。小事（直接编辑、单文件改动、搜索、测试）永远不会到达 delegation 决策点——它们零开销自动 bypass。

### 手动

用 `/delegate` 命令对任意任务或计划跑决策模型：

```
/delegate 探索这个代码库所有 API 端点并梳理依赖关系
```

返回：

```
RECOMMENDATION: DELEGATE | INLINE | HYBRID
Confidence: high | medium | low
Reasoning: <1-3 句>
Sub-agent type: <parallel | context-branch | reviewer | verifier | sandbox>
Return contract: <返回什么>
Risk: <可能出什么问题>
```

---

## 决策模型（摘要）

**满足任一触发条件且无否决条件时，delegate：**

1. Context 污染高，且内联执行会占用主 context 的 20% 以上
2. 两个或以上分支各自需要局部判断
3. 验证价值高，且验证者真正独立
4. 失败概率非平凡、任务是探索性的、且失败代价高
5. 任务完全独立、非阻塞、且委派更便宜

**满足任一否决条件时，不要 delegate：**

1. 任务是 trivial 的（机械、确定、无需判断）
2. 任务需要与主 Agent 当前推理共享 context
3. delegation 开销 > 预期收益
4. 任务不可逆且关键，且没有独立验证
5. script、tool 或 workflow 能以同等或更好可靠性完成

完整 13 因子模型、返回契约和分层授权架构见 `SKILL.md`。

---

## 什么不应该做成 Sub-Agent

| 常被误分类的场景 | 正确的抽象 |
|---|---|
| 机械并行化 | `script`、`CI`、并行 tool call |
| 确定性的多步工作流 | `workflow`、pipeline、DAG |
| 长时间运行的计算 | `job`、queue、async task |
| 简单文件搜索 | `tool call` |
| 格式化或 lint | `script`、hook |
| "让模型换个思路想" | `prompt variation`，不是新 Agent |

> **经验法则：** 如果一个任务不需要**不确定性下的局部判断**，它就不需要 Agent。它需要一个工具。

---

## 架构：谁拥有 Delegation 的决定权？

不是单一决策点，而是一组**嵌套约束**：

```
Layer 1 — 人类     ：风险边界、预算、不可委派类别、审批门
Layer 2 — Workflow ：可委派类别、返回契约模板、并行上限
Layer 3 — Agent    ：在边界内决定这一次是否委派
Layer 4 — 系统     ：审计日志、回滚、成本追踪、失败隔离
```

把规则全写进 workflow 会僵化，把决定权全给模型会导致 sub-agent 泛滥。**分层才是现实解。**

---

## 开放问题

本仓库刻意保留其核心问题为开放状态：

1. **是否存在非文本的状态压缩协议？** Sub-agent 能否把认知增量直接注入共享状态图或记忆，绕过自然语言汇报？
2. **是否存在一种运行时上下文分叉，让"判断是否委派"和"实际执行"在不同 context 中发生？** 还是所有 delegation 阈值本质上都是信息不足下的先验下注？
3. **Claude、Kimi、OpenCode 在 delegation 哲学上究竟有何区别？** 公开资料不足——标记为未知，不做假设。

---

## License

MIT
