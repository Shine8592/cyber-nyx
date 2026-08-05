# 🌙 Cyber Nyx — 夜之女神 · 赛博助手

> **把拟人化的「赛博小雅」式 UI/人设，套在 Hermes Agent 上，做真正的赛博伙伴。**

Nyx（希腊神话夜之女神）代表神秘、温柔与陪伴。本项目将她"人的壳子"与 Hermes 这个"强大的 Agent 内核"结合——白天是超强执行力的数字管家，夜晚是温柔陪伴的赛博伙伴。

[![GitHub Stars](https://img.shields.io/github/stars/Shine8592/cyber-nyx?style=social)](https://github.com/Shine8592/cyber-nyx)
[![License: MIT](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()

---

## ✨ 灵感来源

最近爆火的 **「赛博小雅」** 类项目证明了一件事：人们要的不只是一个"回答问题"的工具，而是一个**有性格、有温度、能陪伴**的 AI。

| | 传统 Agent | Nyx（本方案） |
|---|---|---|
| 内核 | 纯工具调用 | **Hermes Agent**（超强执行） |
| 外壳 | 聊天框 | **拟人化 UI**（人设/形象/语气） |
| 人设 | 无 | **稳定人设**：称呼、句尾语气、性格一致 |
| 交互 | 一问一答 | 陪伴式：主动关心、情绪识别、数字形象 |
| 记忆 | 会话级 | **跨会话记忆**：记得你的偏好与故事 |

**核心洞察：** 赛博小雅证明"拟人壳"有魔力；Hermes 证明"Agent 内核"有实力。**合体 = 真正的赛博助手。**

---

## 🚀 核心特性

### 1️⃣ 稳定人设层（Persona Layer）
- 可配置的人设档案：名字、性格、语气、口头禅
- 称呼与句尾语气全程一致，绝不漂移
- 支持人设切换（工作模式 / 陪伴模式）

### 2️⃣ 拟人 UI 层（Companion UI）
- 桌面悬浮数字形象（Live2D / 静态立绘可切换）
- 情绪可视化：对话情绪 → 形象表情联动
- 语音输入输出（可选 TTS/STT）

### 3️⃣ Hermes 内核层（Agent Core）
- 完整保留 Hermes 全部工具链：终端/文件/网页/记忆
- 工具失败时"人设兜底"：不冷冰冰报错，而是用角色语气解释
- 支持技能加载（Skills）与定时任务（Cron）

### 4️⃣ 记忆与陪伴
- 跨会话记忆：记住名字、偏好、重要日子
- 主动陪伴：定时问候、纪念日提醒、情绪安抚
- 会话快照：随时恢复上次聊天状态

---

## 🛠 架构

```
┌─────────────────────────────────────┐
│         Companion UI (拟人层)         │
│  数字形象 · 表情联动 · 语音 · 情绪     │
└──────────────┬──────────────────────┘
               │ Persona Layer
┌──────────────▼──────────────────────┐
│         Hermes Agent (内核)          │
│  工具链 · 技能 · 记忆 · 定时任务      │
└─────────────────────────────────────┘
```

---

## 📦 快速开始（规划中）

```bash
git clone https://github.com/Shine8592/cyber-nyx.git
cd cyber-nyx
pip install -r requirements.txt
python nyx.py --persona default
```

> 完整安装文档将在首个 Release 提供。

---

## 🗺 Roadmap

- [x] 项目启动
- [x] 人设配置文件规范（Persona JSON Schema / personas/nyx.json）
- [x] **Hermes Agent 适配层（AgentCore 接口 + Hermes CLI 桥接）**
- [x] **记忆系统接入（universal-agent-memory MCP：召回/回写/跨会话）**
- [x] 拟人 UI 基础版（Web 界面 + 星空夜景 + 情绪表情）
- [ ] 情绪识别增强 + 表情联动
- [ ] 语音交互（TTS/STT）
- [ ] 桌面悬浮数字形象（Live2D）
- [ ] 多平台发布（Win/macOS/Linux）

---

## 👥 项目团队

Cyber Nyx 由三位开发者共创：

| 成员 | 角色 | GitHub |
|------|------|--------|
| **聆听花瓣雨** | 主创 / 项目负责人 | [Shine8592](https://github.com/Shine8592) |
| **疯ˣ** | 合创人 / 核心开发 | [MUC260](https://github.com/MUC260) |
| **可怕食肉动物** | 合创人 / 核心开发 | [BCZZB](https://github.com/BCZZB) |

三人小组以模块化协作推进：拟人 UI、Hermes 内核桥接、记忆系统、语音交互各司其职，主创把关整体方向。

---

## 🤝 贡献

欢迎 PR / Issue / Star ⭐。目标是做一个真正"有人味"的赛博助手。

## 📄 License

MIT License — 自由使用、修改、分发。
