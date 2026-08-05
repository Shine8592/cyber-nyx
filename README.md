# 🌙 Cyber Nyx — 夜之女神 · 赛博助手

> **基于 Hermes Agent 的再开发：以拟人化的「赛博小雅」式 UI/人设，构建真正的赛博伙伴。**

Nyx（希腊神话夜之女神）代表神秘、温柔与陪伴。本项目将她"人的壳子"与 Hermes 这个"强大的 Agent 内核"结合——白天是超强执行力的数字管家，夜晚是温柔陪伴的赛博伙伴。

[![GitHub Stars](https://img.shields.io/github/stars/Shine8592/cyber-nyx?style=social)](https://github.com/Shine8592/cyber-nyx)
[![License: MIT](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()
[![v0.7](https://img.shields.io/badge/version-0.7-blue.svg)]()

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

**核心洞察：** 赛博小雅证明"拟人壳"有魔力；Hermes 证明"Agent 内核"有实力。**在 Hermes 之上再开发，= 真正的赛博助手。**

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

### 5️⃣ LLM 增强（v0.3）
- **自动重试**：指数退避，最多 3 次（`NYX_RETRY_MAX` / `NYX_RETRY_BASE`）
- **SSE 流式输出**：逐字推送，感知更自然（`NYX_STREAM=1`）
- **多格式兼容**：支持 `text`（默认）、`json`、`sse` 三种响应格式

### 6️⃣ 主动关心（v0.4）
- **空闲提醒**：主人 30 分钟没说话时主动打招呼
- **时段问候**：早安 / 午安 / 晚安 / 深夜休息提醒（每时段一次）
- **情绪关怀**：上次对话情绪低落时第二天温柔安抚
- **首次问候**：新访客自动欢迎

### 7️⃣ 多会话与打字机（v0.5）
- **多会话管理**：session_id 幂等创建/复用，TTL 过期清理，最近 N 轮上下文
- **历史接口**：`/api/session/new`、`/api/session/{id}/history`、DELETE 删除
- **打字机效果**：Nyx 回复逐字显示 + 金色光标
- **新对话按钮**：一键开启新会话（自动清理旧会话）

### 8️⃣ 会话历史持久化（v0.6）
- **跨重启恢复**：会话历史存入 universal-agent-memory，服务重启后同一 `session_id` 自动恢复上下文
- **原子快照**：每个会话一条快照记忆（JSON），保存前先删旧快照避免重复
- **滚动压缩**：只保留最近 50 条、单条截 400 字符，防止超长快照无法检索
- **降级安全**：记忆系统不可用时自动回退纯内存模式，不阻塞对话
- **内部隔离**：会话快照（`[chat-session:xxx]`）不进入用户记忆召回，原始 JSON 不会泄漏给 LLM/用户

### 9️⃣ 历史恢复 + 记忆面板 + WS 实时关心（v0.7）
- **前端刷新恢复聊天历史**：`/api/session/{id}/history` 用 get_or_create 触发记忆恢复，刷新页面聊天记录不丢
- **记忆可视化/管理**：🧠 记忆按钮打开记忆面板，查看 Nyx 记住了什么、可逐条"忘掉"（会话快照已过滤，不泄漏内部 JSON）
- **WebSocket 实时推送**：`/ws?session_id=xxx` 长连接，主动关心由服务端实时推送（每 30 秒检查），前端 WS 断线自动回退 5 分钟轮询
- **防重复关怀**：首次问候 / 空闲提醒 / 情绪关怀触发后视为一次互动，不再刷屏

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

## 📦 快速开始

```bash
git clone https://github.com/Shine8592/cyber-nyx.git
cd cyber-nyx
pip install -r requirements.txt
python app.py
```

访问 http://127.0.0.1:8000

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `NYX_API_BASE` | OpenAI 兼容 API 地址 | - |
| `NYX_API_KEY` | API 密钥 | - |
| `NYX_MODEL` | 模型名称 | gpt-4o-mini |
| `NYX_HERMES_BIN` | Hermes CLI 路径 | 自动探测 |
| `NYX_HERMES_MODEL` | Hermes 模型 | - |
| `NYX_STREAM` | 启用 SSE 流式 | 0 |
| `NYX_RETRY_MAX` | LLM 重试次数 | 3 |
| `NYX_RETRY_BASE` | 重试基础秒数 | 1.0 |

---

## 🔌 API

### 文本模式（默认）
```
POST /api/chat
Body: { "message": "你好", "format": "text" }
Response: { "reply": "...", "emotion": "neutral", "recalled": 0 }
```

### JSON 模式
```
POST /api/chat
Body: { "message": "你好", "format": "json" }
Response: { "reply": "...", "emotion": "neutral", "recalled": 0, "format": "json" }
```

### SSE 流式模式
```
POST /api/chat/stream
Body: { "message": "你好", "format": "sse" }
Response: text/event-stream
```

### 状态
```
GET /api/status
```

---

## 🗺 Roadmap

- [x] 项目启动
- [x] 人设配置文件规范（Persona JSON Schema / personas/nyx.json）
- [x] **Hermes Agent 适配层（AgentCore 接口 + Hermes CLI 桥接）**
- [x] **记忆系统接入（universal-agent-memory MCP：召回/回写/跨会话）**
- [x] 拟人 UI 基础版（Web 界面 + 星空夜景 + 情绪表情）
- [x] LLM 重试 + 流式输出
- [x] 多格式 API 兼容（text/json/sse）
- [x] 主动关心（空闲提醒 / 时段问候 / 情绪关怀）
- [x] 多会话上下文管理
- [x] 前端打字机效果
- [x] 情绪识别增强 + 表情联动
- [x] 会话历史持久化（跨重启恢复，universal-agent-memory 快照）
- [x] 前端刷新恢复聊天历史（v0.7）
- [x] 记忆可视化/管理（记忆面板，查看 + 删除，v0.7）
- [x] WebSocket 主动关心实时推送（v0.7）
- [ ] 语音交互（TTS/STT）
- [ ] 桌面悬浮数字形象（Live2D）
- [ ] 多平台发布（Win/macOS/Linux）

---

## 👥 项目团队

Cyber Nyx 由「**夜之女神项目组**」三位开发者共创：

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
