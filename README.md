# 🌙 Cyber Nyx — 夜之女神 · 赛博助手

> **基于 Hermes Agent 的再开发：以拟人化的「赛博小雅」式 UI/人设，构建真正的赛博伙伴。**

Nyx（希腊神话夜之女神）代表神秘、温柔与陪伴。本项目将她"人的壳子"与 Hermes 这个"强大的 Agent 内核"结合——白天是超强执行力的数字管家，夜晚是温柔陪伴的赛博伙伴。

[![GitHub Stars](https://img.shields.io/github/stars/Shine8592/cyber-nyx?style=social)](https://github.com/Shine8592/cyber-nyx)
[![License: MIT](https://img.shields.io/badge/License-MIT-brightgreen.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()
[![v0.9](https://img.shields.io/badge/version-0.9-blue.svg)]()

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

### 🔟 声音克隆 + 语音合成（v0.8）
- **GPT-SoVITS v2 声音克隆**：一键安装 / 一键训练 / 一键推理（`training.py`），上传少量音频即可克隆你自己的声音
- **选装提示**：安装前明确提示模型体积 / 下载量 / 磁盘占用 / 预计耗时，默认免费微软 edge-tts 电子音无需安装（v0.9）
- **国内镜像自动降级**：预训练权重 hf-mirror → HF、GPT-SoVITS 源码 ghfast.top → GitHub、PyPI 清华 → 官方，国内网络开箱即用
- **edge-tts 即时语音**：无需训练即可用微软 Edge 语音合成（`/api/tts`）
- **声音档案管理**：`/api/voices` 列出可用音色，`/api/clone` 管理克隆档案，前端可视化面板

### 1️⃣1️⃣ Hermes Agent 自动部署（v0.8）
- **一键部署**：`hermes_setup.py` 自动探测本机 Hermes CLI，未安装则自动安装（uv / Python 3.11 / Node / ffmpeg / PortableGit）
- **内核直连**：部署完成后自动写入 `config.json`，Nyx 直接以 Hermes 为内核运行（`/api/hermes/deploy`）

### 1️⃣2️⃣ 本地语音输入 STT（v0.9，疯ˣ 交付）
- **本地离线识别**：`sherpa-onnx` + zipformer-zh 14M 流式中文模型，纯 CPU 推理，无 GPU/联网依赖
- **一键安装**：引擎清华源安装 + 模型 GitHub Release 下载，自动解压，约 1~2 分钟
- **麦克风识别**：前端 🎤 按钮按住说话 → 浏览器降采样 16kHz 单声道 → `/api/stt` 识别填入输入框
- **与 TTS 形成完整语音闭环**：语音输入 → 对话 → 语音输出

### 1️⃣3️⃣ 数字形象 + 语音对口型（v0.9）
- **多形象可切换**：内置 SVG 月亮精灵（零依赖）+ Live2D 模型（Miyara / Kei 基础 / Kei 元音对口型），顶部 🎭 下拉一键切换，记忆上次选择
- **右下角悬浮**：Live2D 形象以桌宠风格固定在右下角，不占聊天区；无模型时回退顶部 SVG 月亮精灵
- **语音对口型（Lip Sync）**：Web Audio 分析声音能量 → 实时驱动 `ParamMouthOpenY`，Nyx 说话时嘴巴随语音开合（kei 元音版最佳）
- **表情联动**：对话情绪（happy/sad/curious 等）自动驱动形象表情与嘴型眉毛
- **模型放置**：`.model3.json` + 贴图放入 `web/assets/live2d/`（或子目录）即自动出现在切换列表，完全离线可用
- **依赖说明**：需要 `edge-tts`（`pip install -r requirements.txt`）才能合成语音并驱动口型；未安装时 TTS 返回 501、口型不工作

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

### 🔧 环境要求

| 项 | 最低要求 | 推荐 |
|---|---|---|
| 操作系统 | Windows 10 / macOS / Linux | Windows 11 |
| Python | 3.10+ | 3.11/3.12 |
| 内存 | 4 GB | 8 GB+（训练时 8 GB+） |
| 磁盘 | 1 GB 可用 | 10 GB（含可选装模型） |
| 浏览器 | Chrome / Edge 任意现代浏览器 | Edge / Chrome |
| GPU（可选） | 无 GPU 可运行 | NVIDIA 4GB+（个性化声音克隆加速） |

### 一、安装（3 分钟）

```bash
git clone https://github.com/Shine8592/cyber-nyx.git
cd cyber-nyx
pip install -r requirements.txt
```

> 💡 国内网络加速：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

### 二、启动

```bash
python app.py
```

**默认打开独立 GUI 桌面窗口（「Cyber Nyx · 小夜」）**，即软件形态：

- **桌宠模式**（透明悬空小夜，推荐）：`python app.py --pet`
- **浏览器模式**（`http://127.0.0.1:8000`，可局域网访问）：`python app.py --web`
- GUI / 桌宠模式只监听本机 `127.0.0.1`，无需访问令牌
- 本机未安装 `pywebview` 时自动降级为浏览器模式（并打印提示），`pip install -r requirements.txt` 已包含该依赖

### 二·甲、桌宠模式（`python app.py --pet`）

让 Live2D 小人「悬空」在电脑桌面上，像真人一样陪着你：

- **透明悬浮**：只有小人的透明窗口，置顶显示，不占任务栏
- **随意拖拽**：鼠标按住小人即可拖到屏幕任意位置
- **右键菜单**：说句话（卡片对话）/ 完整面板 / 置顶切换 / 打招呼 / 退出
- **卡片对话**：右键 → 输入框 → 小夜回复（TTS 语音 + 口型同步）
- **完整面板**：一键切换到完整聊天界面（iframe 复用主 UI）
- **语音输入**：卡片内 🎤 按住说话（本地 STT 识别）

> 💡 桌宠窗口约 220×280 透明，Windows WebView2 原生支持透明；macOS 需额外配置。

### 三、接入大脑（LLM，必做才能正常对话）

打开页面右上角 **⚙️ 设置** → 填入 API 地址与密钥 → 保存即生效，无需重启。

- **OpenAI 兼容 API**：任意 `base_url` + `api_key` + 模型名
- 没有 Key 时 Nyx 进入「本地演示模式」，回复为预设人设模板，无法真正对话

### 四、可选装：语音（默认免费微软电子音）

Nyx 语音输出**默认走微软免费 API（edge-tts）电子音，开箱即用无需安装**，仅需在页面右上角打开 🎙️ 语音开关。

**想要个性化声音克隆（GPT-SoVITS v2）才是可选安装**：
1. 设置面板 → 「声音克隆 · 一键安装」→ 点击后**先弹提示框**，明示将下载约 2.2GB、占用磁盘 4.4GB、约 20-40 分钟
2. 确认后自动安装（国内镜像自动切换）
3. 安装完成 → 上传 10~60 秒人声 → 一键训练 → 生成专属音色（需 NVIDIA GPU 加速，CPU 慢速）

### 五、可选装：本地语音输入（STT 听写）

- 设置面板 → 「语音输入」→ 一键安装 `sherpa-onnx` 中文识别（约 70MB，1~2 分钟）
- 安装后点击输入框旁的 🎤 按钮即可按住说话识别

### 六、可选装：Agent 内核（工具链）

- 设置面板 → 「Agent 内核」→ 一键自动部署（约 5~20 分钟）
- 部署后 Nyx 具备终端 / 文件 / 网页 / 记忆等 Agent 能力

### 七、切换数字形象（Live2D）

Nyx 默认显示内置 **SVG 月亮精灵**（零依赖）。页面顶部有 🎭 形象下拉框，可选：

| 形象 | 说明 |
|---|---|
| 🌙 月亮精灵 | 内置 SVG，表情联动 + 眨眼呼吸动画 |
| 🎭 Miyara | Live2D 高清立绘 |
| 🎭 Kei（基础） | Live2D 官方示例，含中/日/英/韩语音动作 |
| 🎭 Kei（元音对口型） | **说话时嘴巴随语音开合**（推荐） |

- 切换即时生效，浏览器记住上次选择
- 想换其他模型：把 `.model3.json` + 贴图放进 `web/assets/live2d/`（支持子目录），重启即出现在列表
- **口型依赖**：需 `edge-tts` 正常合成语音（`pip install -r requirements.txt`），说话时才对口型

### 访问令牌（鉴权）

- 首次启动自动生成 `nyx-...` 令牌，写入 `config.json` 并在控制台日志打印
- 首次打开页面要求输入令牌（浏览器会记住）
- 测试环境关闭：`NYX_AUTH_DISABLE=1 python app.py`
- 自定义令牌：环境变量 `NYX_AUTH_TOKEN` 或 `config.json` 的 `auth.token`

### 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `NYX_API_BASE` | OpenAI 兼容 API 地址 | - |
| `NYX_API_KEY` | API 密钥 | - |
| `NYX_MODEL` | 模型名称 | gpt-4o-mini |
| `NYX_HERMES_BIN` | 内核 CLI 路径 | 自动探测 |
| `NYX_HERMES_MODEL` | 内核模型 | - |
| `NYX_STREAM` | 启用 SSE 流式 | 0 |
| `NYX_RETRY_MAX` | LLM 重试次数 | 3 |
| `NYX_RETRY_BASE` | 重试基础秒数 | 1.0 |
| `NYX_MCP_SCRIPT` | 记忆引擎 mcp_server.py 路径（覆盖内嵌探测） | 自动 |
| `MEMORY_STORE` | 记忆数据目录 | ~/.config/opencode/memory |
| `MEMORY_PROJECT_ROOT` / `MEMORY_GLOBAL_DIR` | 记忆项目根目录 | 用户主目录 |

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

### 语音（v0.8 / v0.9）
```
GET  /api/voices              # 列出可用音色（edge-tts + 克隆档案）
POST /api/tts                 # 语音合成（edge-tts 即时合成）
POST /api/clone               # 上传音频创建声音克隆档案
DELETE /api/clone             # 删除克隆档案
POST /api/train               # 一键训练（GPT-SoVITS v2）
GET  /api/train/status        # 训练进度
GET  /api/train/install-info  # 声音克隆选装资源说明（下载量/磁盘/耗时，选装前提示）
POST /api/stt                 # 本地语音识别（16kHz 单声道 WAV → 文本）
GET  /api/stt/status          # STT 引擎/模型安装状态
POST /api/stt/setup           # 一键安装 STT（sherpa-onnx zipformer-zh）
```

### 内核部署（v0.8）
```
POST /api/hermes/deploy         # 一键部署 Agent 内核
GET  /api/hermes/deploy/status  # 部署进度
```

### 环境与设置（v0.8）
```
GET  /api/env          # 查看运行环境
POST /api/setup        # 环境自检/配置
GET  /api/setup/status # 设置状态
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
- [x] 语音交互基础版（edge-tts 合成 + GPT-SoVITS v2 声音克隆，v0.8）
- [x] Hermes Agent 一键部署（v0.8）
- [x] 本地语音输入（sherpa-onnx 中文 STT，一键安装 + 麦克风识别，v0.9）
- [x] 声音克隆选装提示（安装前明示资源占用，v0.9）
- [ ] 声音克隆全自动训练增强（训练进度可视化 / 多音色切换 / 克隆质量优化）
- [x] 数字形象（内置 SVG 月亮精灵 + Live2D 多模型切换 + 语音对口型，v0.9）
- [x] 桌宠模式（透明悬空小夜 + 右键对话 + 置顶切换，v0.9）
- [ ] 多平台发布（Win/macOS/Linux）

---

## 👥 项目团队

Cyber Nyx 由「**夜之女神项目组**」三位开发者共创：

| 成员 | 角色 | GitHub |
|------|------|--------|
| **聆听花瓣雨** | 主创 / 项目负责人 | [Shine8592](https://github.com/Shine8592) |
| **疯ˣ** | 合创人 / 核心开发 | [MUC260](https://github.com/MUC260) |
| **可怕食肉动物** | 合创人 / 核心开发 | [BCZZB](https://github.com/BCZZB) |

三人小组以模块化协作推进：拟人 UI、Agent 内核桥接、记忆系统、语音交互各司其职，主创把关整体方向。

---

## 🙏 鸣谢

本项目基于 **Hermes Agent** 进行二次开发——其强大的 Agent 工具链（终端 / 文件 / 网页 / 记忆 / 技能 / 定时任务）是 Nyx「赛博伙伴」能力的底层基础。在此向 Hermes Agent 项目及其开发者致以诚挚感谢。

同时感谢以下开源项目为 Nyx 提供的能力支撑：

| 项目 | 用途 |
|---|---|
| Hermes Agent | 内核：Agent 工具链与执行能力 |
| edge-tts | 微软免费语音合成（默认电子音） |
| GPT-SoVITS v2 | 个性化声音克隆引擎（可选装） |
| sherpa-onnx | 本地语音识别引擎（STT，可选装） |
| universal-agent-memory | 跨会话记忆引擎（内嵌） |
| FastAPI / Uvicorn | Web 服务框架 |

---

## 🤝 贡献

欢迎 PR / Issue / Star ⭐。目标是做一个真正"有人味"的赛博助手。

## 📄 License

MIT License — 自由使用、修改、分发。
