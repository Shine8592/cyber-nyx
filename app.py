#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""Cyber Nyx — FastAPI 拟人助手服务（v0.9：本地 STT + 默认 GUI 窗口）

启动：
    python app.py                                  # 默认独立 GUI 窗口
    python app.py --web                            # 浏览器模式（http://127.0.0.1:8000）
    NYX_HERMES_MODEL=... python app.py             # 启用 Hermes 内核
    NYX_STREAM=1 python app.py                     # 启用流式输出
"""

import asyncio
import json
import os
import secrets
import sys
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

import nyx_llm
import settings as app_settings
import training
from bridges.agent_core import NoCore
from bridges.hermes_adapter import HermesCore
from bridges.memory_bridge import MCPMemoryStore, NullMemoryStore
from emotion import infer_emotion as _infer_emotion
from nyx import NyxAgent
from proactive import ProactiveCare
from session import SessionManager

import hermes_setup
import stt

if getattr(sys, "frozen", False):
    BASE = Path(sys.executable).resolve().parent
    RES_DIR = Path(sys._MEIPASS)
else:
    BASE = Path(__file__).resolve().parent
    RES_DIR = BASE

# 启动时加载 config.json → 环境变量（环境变量优先，不覆盖）
app_settings.load_to_env()


def _gui_requested() -> bool:
    """运行模式判定：默认 GUI 独立窗口；`--web` 强制浏览器模式。

    - `--web`：强制浏览器模式（支持局域网访问，需访问令牌）
    - `--gui`：强制 GUI 窗口（兼容旧参数）
    - 默认：GUI 窗口（frozen 打包 或 本机装有 pywebview）
    - 本机未装 pywebview 时自动降级为浏览器模式（不崩溃）
    """
    if "--web" in sys.argv:
        return False
    if "--gui" in sys.argv:
        return True
    if getattr(sys, "frozen", False):
        return True
    try:
        import webview  # noqa: F401

        return True
    except Exception:
        return False


# GUI 窗口模式只监听 127.0.0.1，无需令牌
RUN_GUI = _gui_requested()

# --- 鉴权：访问令牌（NYX_AUTH_DISABLE=1 可关闭，测试用） ---
AUTH_DISABLED = os.environ.get("NYX_AUTH_DISABLE", "0") == "1" or RUN_GUI


def _ensure_auth_token() -> str:
    """未配置令牌时自动生成随机 token，写入 config.json 并在日志打印。"""
    tok = os.environ.get("NYX_AUTH_TOKEN", "")
    if not tok:
        tok = app_settings.load().get("auth", {}).get("token", "")
    if not tok:
        tok = "nyx-" + secrets.token_urlsafe(24)
        cfg = app_settings.load()
        cfg.setdefault("auth", {})["token"] = tok
        app_settings.save(cfg)
        os.environ["NYX_AUTH_TOKEN"] = tok
        print(f"🔑 访问令牌（请转发给使用者）：{tok}")
    return tok


AUTH_TOKEN = "" if AUTH_DISABLED else _ensure_auth_token()

nyx = NyxAgent(str(RES_DIR / "personas" / "nyx.json"))
LLM_ON = nyx_llm.available()

# --- 内核桥接（Hermes） ---
CORE_ENABLED = True
try:
    _hbin = hermes_setup.find_hermes_bin()
    if _hbin:
        os.environ.setdefault("NYX_HERMES_BIN", _hbin)
    core = HermesCore()
    if not core.health():
        core = NoCore()
except Exception:
    core = NoCore()

# --- 记忆系统（universal-agent-memory MCP） ---
MEM_ENABLED = True
try:
    memory = MCPMemoryStore()
    memory.status()  # 探活，失败则降级
except Exception:
    memory = NullMemoryStore()
    MEM_ENABLED = False

# --- 主动关心 ---
proactive = ProactiveCare(nyx_agent=nyx, memory_store=memory if MEM_ENABLED else None)

# --- 多会话上下文管理（可选记忆持久化） ---
sessions = SessionManager(
    max_sessions=200,
    ttl=3600,
    memory_store=memory if MEM_ENABLED else None,
)


# --- WebSocket 连接管理（主动关心实时推送） ---
class CareWSManager:
    """session_id → WebSocket 映射，后台任务用 WS 推送关心消息。"""

    def __init__(self):
        self.connections: dict[str, WebSocket] = {}

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.connections[session_id] = ws

    def disconnect(self, session_id: str):
        self.connections.pop(session_id, None)

    def active(self) -> list[str]:
        return list(self.connections.keys())

    async def push_care(self, session_id: str, message: str) -> bool:
        ws = self.connections.get(session_id)
        if ws is None:
            return False
        try:
            await ws.send_json({"type": "care", "message": message})
            return True
        except Exception:
            self.disconnect(session_id)
            return False


ws_manager = CareWSManager()


async def _care_loop():
    """后台任务：每 30 秒检查活跃 WS 会话，触发主动关心并推送。"""
    while True:
        await asyncio.sleep(30)
        for sid in ws_manager.active():
            with suppress(Exception):
                msg = proactive.check_and_notify(sid)
                if msg:
                    await ws_manager.push_care(sid, msg)


@asynccontextmanager
async def lifespan(_: FastAPI):
    task = asyncio.create_task(_care_loop())
    yield
    task.cancel()


app = FastAPI(title="Cyber Nyx", version="0.9.0", lifespan=lifespan)


@app.middleware("http")
async def auth_middleware(request, call_next):
    """鉴权：/api/* 需要 Authorization: Bearer <token>（除 /api/settings 外统一保护）。"""
    if not AUTH_DISABLED and request.url.path.startswith("/api/"):
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            auth = auth[7:]
        if auth != AUTH_TOKEN:
            return JSONResponse({"detail": "unauthorized"}, status_code=401)
    return await call_next(request)

SYSTEM_PROMPT = (
    f"你叫{nyx.display}（{nyx.title}），现在是深夜陪伴时刻。"
    f"你的人设：{'、'.join(nyx.persona.get('personality', []))}。"
    "说话温柔神秘，称呼对方为主人，句尾常用'呀/呢/~'。"
    "如果主人要求执行任务（查资料/写代码/改文件等），先简单确认，"
    "说明你会交给内核（Agent 内核）处理，再用你的语气回应。保持人设一致。"
    + nyx.get_mode_prompt()
)


class ChatIn(BaseModel):
    message: str
    format: str | None = "text"  # text | json | sse
    session_id: str | None = None  # 复用已有会话；不传则新建


@app.get("/", response_class=HTMLResponse)
def index():
    return (RES_DIR / "web" / "index.html").read_text(encoding="utf-8")


# --- 静态资源（头像/音频等） ---
from fastapi.staticfiles import StaticFiles as _StaticFiles

_ASSETS_DIR = RES_DIR / "web" / "assets"
if _ASSETS_DIR.is_dir():
    app.mount("/assets", _StaticFiles(directory=str(_ASSETS_DIR)), name="assets")


# --- 会话管理端点 ---


@app.get("/api/session/new")
def session_new():
    """新建一个会话，返回 session_id。"""
    session = sessions.get_or_create()
    return JSONResponse({"session_id": session.id})


@app.get("/api/mode")
def mode_get():
    """查看当前模式。"""
    return JSONResponse({"mode": nyx.mode})


@app.post("/api/mode")
def mode_set(body: dict):
    """切换模式：{"mode": "companion" | "work"}"""
    mode = (body or {}).get("mode", "")
    msg = nyx.switch_mode(mode)
    return JSONResponse({"mode": nyx.mode, "message": msg})


# --- 设置：内核 / LLM 接入配置 ---


@app.get("/api/settings")
def settings_get():
    """查看当前配置（API Key 脱敏）。"""
    cfg = app_settings.load()
    llm = cfg["llm"]
    return JSONResponse(
        {
            "llm": {
                "base": llm["base"],
                "key": app_settings.mask_key(llm["key"]),
                "model": llm["model"],
                "configured": bool(llm["base"] and llm["key"]),
            },
            "hermes": {
                "bin": cfg["hermes"]["bin"],
                "model": cfg["hermes"]["model"],
                "provider": cfg["hermes"]["provider"],
                "online": core.name == "hermes",
            },
            "memory": {"enabled": MEM_ENABLED},
            "version": "0.9.0",
        }
    )


@app.post("/api/settings")
def settings_set(body: dict):
    """保存配置：写 config.json + 更新环境变量 + 热重建 Hermes 内核。

    key 传空或含脱敏标记（...）时视为不修改（保留已存密钥）。
    """
    global core, LLM_ON, CORE_ENABLED
    llm = (body or {}).get("llm") or {}
    hermes = (body or {}).get("hermes") or {}

    cur = app_settings.load()
    key_val = (llm.get("key") or "").strip()
    if not key_val or "..." in key_val:
        key_val = cur["llm"]["key"]  # 未修改，保留原密钥

    cfg = {
        "llm": {
            "base": (llm.get("base") or "").strip(),
            "key": key_val,
            "model": (llm.get("model") or "").strip() or "gpt-4o-mini",
        },
        "hermes": {
            "bin": (hermes.get("bin") or "").strip(),
            "model": (hermes.get("model") or "").strip(),
            "provider": (hermes.get("provider") or "").strip(),
        },
    }
    app_settings.save(cfg)
    app_settings.apply_to_env(cfg)

    # 热更新 LLM 可用状态（nyx_llm 每次调用都重读环境变量，立即生效）
    LLM_ON = nyx_llm.available()

    # 热重建 Hermes 内核（探活失败自动降级）
    try:
        new_core = HermesCore()
        if not new_core.health():
            new_core = NoCore()
    except Exception:
        new_core = NoCore()
    core = new_core
    CORE_ENABLED = core.name == "hermes"

    return JSONResponse(
        {
            "ok": True,
            "llm": {"configured": LLM_ON},
            "hermes": {"online": core.name == "hermes", "bin": getattr(core, "bin", "")},
            "message": "设置已保存并生效"
            + ("，Agent 内核已接入" if core.name == "hermes" else "，Agent 内核未检测到"),
        }
    )


@app.delete("/api/session/{session_id}")
def session_delete(session_id: str):
    """删除一个会话（前端"新对话"按钮使用）。"""
    sessions.delete(session_id)
    return JSONResponse({"ok": True})


@app.get("/api/session/{session_id}/history")
def session_history(session_id: str):
    """返回会话历史（供前端恢复上下文 / 调试）。

    用 get_or_create 触发记忆恢复：服务重启后同一 session_id
    也能从 universal-agent-memory 拉回历史，前端刷新不再丢。
    """
    session = sessions.get_or_create(session_id)
    msgs = [
        {
            "role": m.role,
            "content": m.content,
            "emotion": m.emotion,
            "timestamp": m.timestamp,
        }
        for m in session.messages
    ]
    return JSONResponse({"session_id": session_id, "messages": msgs})


# --- 记忆可视化 / 管理 ---


@app.get("/api/memory")
def memory_list(limit: int = 30):
    """列出最近记忆（前端记忆面板）。"""
    if not MEM_ENABLED:
        return JSONResponse({"ok": True, "memories": [], "enabled": False})
    try:
        items = memory.list_recent(limit=min(limit, 100))
        return JSONResponse({"ok": True, "memories": items, "enabled": True})
    except Exception:
        return JSONResponse(
            {"ok": False, "memories": [], "enabled": True, "error": "记忆读取失败"}
        )


@app.delete("/api/memory/{memory_id}")
def memory_delete(memory_id: str):
    """删除一条记忆（按 id 反查内容，以完整内容为关键词删除）。"""
    if not MEM_ENABLED:
        return JSONResponse({"ok": False, "error": "记忆系统未启用"})
    try:
        items = memory.list_recent(limit=100)
    except Exception:
        return JSONResponse({"ok": False, "error": "记忆读取失败"})
    target = next((m for m in items if m["id"] == memory_id), None)
    if not target:
        return JSONResponse({"ok": False, "error": "未找到该记忆"})
    try:
        ok = memory.forget(target["content"])
    except Exception:
        ok = False
    return JSONResponse({"ok": ok, "deleted": target["content"][:40]})


# --- WebSocket：主动关心实时推送 ---


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """WebSocket 长连接：Nyx 主动关心通过 WS 实时推送。

    前端连接：ws://host/ws?session_id=xxx&token=xxx
    服务端推送：{"type": "care", "message": "..."}
    """
    # 鉴权：WS 不走 HTTP 中间件，单独校验 query token
    if not AUTH_DISABLED:
        tok = websocket.query_params.get("token", "")
        if tok != AUTH_TOKEN:
            await websocket.close(code=4401)
            return
    session_id = websocket.query_params.get("session_id", "")
    if not session_id:
        await websocket.close(code=4400)
        return
    await ws_manager.connect(session_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # 保持连接（客户端心跳/忽略消息）
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id)
    except Exception:
        ws_manager.disconnect(session_id)


@app.post("/api/chat")
def chat(body: ChatIn):
    msg = body.message.strip()
    if not msg:
        return JSONResponse({"reply": "嗯？主人没有说话呢~", "emotion": "neutral"})

    # 0) 会话管理：获取或创建会话
    session = sessions.get_or_create(body.session_id)

    # 1) 记忆召回
    recalled = []
    if MEM_ENABLED:
        try:
            recalled = memory.recall(msg)
        except Exception:
            recalled = []

    # 2) 判断是否为任务请求
    is_task = _looks_like_task(msg)

    if is_task and CORE_ENABLED and isinstance(core, HermesCore):
        ctx = ""
        if recalled:
            ctx = (
                "（主人过去提及："
                + "；".join(r["content"][:40] for r in recalled[:2])
                + "）"
            )
        persona_inject = (
            "你是赛博助手Nyx(夜之女神/小夜)，性格"
            + "、".join(nyx.persona.get("personality", []))
            + "。请以稳定人设语气、称呼主人为'主人'，完成任务后简洁回答。"
            + f"\n主人过去的上下文：{ctx}"
            if ctx
            else "你是赛博助手Nyx(夜之女神/小夜)，性格"
            + "、".join(nyx.persona.get("personality", []))
            + "。请以稳定人设语气、称呼主人为'主人'，完成任务后简洁回答。"
        )
        result = core.submit(f"{msg}", persona_inject=persona_inject)
        raw = (
            result.output
            if result.ok
            else f"唔，任务没跑成（{result.error}），我再看看~"
        )
    else:
        mem_note = ""
        if recalled:
            mem_note = f"（我记得你之前提过:{recalled[0]['content'][:30]}…）"
        if LLM_ON:
            try:
                care_prompt = nyx.get_proactive_prompt()
                user_msg = mem_note + msg
                if care_prompt:
                    user_msg = f"{care_prompt}\n{user_msg}"
                raw = nyx_llm.chat(
                    SYSTEM_PROMPT,
                    user_msg,
                    history=session.context(max_turns=8),
                )
            except Exception as e:
                raw = (
                    "唔，我这边网络打了个盹呢"
                    f"（{type(e).__name__}）。稍后再试试好不好？"
                )
        else:
            raw = nyx_llm.local_reply(msg) + mem_note

    reply = nyx.wrap(raw)
    emotion, intensity = _infer_emotion(msg)
    nyx.update_emotion(emotion)

    # 3) 记录会话：user 消息 + assistant 回复
    session.add("user", msg, emotion=emotion)
    session.add("assistant", reply)

    # 3.5) 持久化会话历史（universal-agent-memory）
    sessions.persist(session)

    # 4) 更新主动关心状态
    proactive.touch(session_id=session.id, emotion=emotion)

    # 5) 记忆保存
    if _looks_important(msg) and MEM_ENABLED:
        try:
            memory.remember(f"主人说：{msg}", "from-chat")
        except Exception:
            pass

    fmt = body.format or "text"
    if fmt == "json":
        return JSONResponse(
            {
                "reply": reply,
                "emotion": emotion,
                "intensity": intensity,
                "recalled": len(recalled),
                "format": "json",
                "session_id": session.id,
            }
        )
    return JSONResponse(
        {
            "reply": reply,
            "emotion": emotion,
            "intensity": intensity,
            "recalled": len(recalled),
            "session_id": session.id,
        }
    )


@app.post("/api/chat/stream")
def chat_stream(body: ChatIn):
    """SSE 流式输出，逐字推送。"""
    msg = body.message.strip()
    if not msg:

        async def empty():
            yield (
                "data: "
                + json.dumps({"reply": "嗯？主人没有说话呢~", "emotion": "neutral"})
                + "\n\n"
            )

        return StreamingResponse(empty(), media_type="text/event-stream")

    async def generate():
        # 会话管理：获取或创建会话，记录 user 消息
        session = sessions.get_or_create(body.session_id)
        emotion, intensity = _infer_emotion(msg)
        session.add("user", msg, emotion=emotion)

        recalled = []
        if MEM_ENABLED:
            try:
                recalled = memory.recall(msg)
            except Exception:
                recalled = []

        is_task = _looks_like_task(msg)
        raw = ""

        if is_task and CORE_ENABLED and isinstance(core, HermesCore):
            ctx = ""
            if recalled:
                ctx = (
                    "（主人过去提及："
                    + "；".join(r["content"][:40] for r in recalled[:2])
                    + "）"
                )
            persona_inject = (
                "你是赛博助手Nyx(夜之女神/小夜)，性格"
                + "、".join(nyx.persona.get("personality", []))
                + "。请以稳定人设语气、称呼主人为'主人'，完成任务后简洁回答。"
                + f"\n主人过去的上下文：{ctx}"
                if ctx
                else "你是赛博助手Nyx(夜之女神/小夜)，性格"
                + "、".join(nyx.persona.get("personality", []))
                + "。请以稳定人设语气、称呼主人为'主人'，完成任务后简洁回答。"
            )
            result = core.submit(f"{msg}", persona_inject=persona_inject)
            raw = (
                result.output
                if result.ok
                else f"唔，任务没跑成（{result.error}），我再看看~"
            )
        else:
            mem_note = ""
            if recalled:
                mem_note = f"（我记得你之前提过:{recalled[0]['content'][:30]}…）"
            if LLM_ON:
                try:
                    streamed = ""
                    care_prompt = nyx.get_proactive_prompt()
                    user_msg = mem_note + msg
                    if care_prompt:
                        user_msg = f"{care_prompt}\n{user_msg}"
                    for chunk in nyx_llm.chat_stream(
                        SYSTEM_PROMPT,
                        user_msg,
                        history=session.context(max_turns=8),
                    ):
                        streamed += chunk
                        yield (
                            "data: "
                            + json.dumps(
                                {
                                    "chunk": chunk,
                                    "emotion": emotion,
                                    "intensity": intensity,
                                }
                            )
                            + "\n\n"
                        )
                    raw = streamed
                except Exception as e:
                    raw = (
                        "唔，我这边网络打了个盹呢"
                        f"（{type(e).__name__}）。稍后再试试好不好？"
                    )
            else:
                raw = nyx_llm.local_reply(msg) + mem_note
                yield (
                    "data: "
                    + json.dumps(
                        {"chunk": raw, "emotion": emotion, "intensity": intensity}
                    )
                    + "\n\n"
                )

        # 记录 assistant 回复 + 更新主动关心状态
        reply = nyx.wrap(raw)
        nyx.update_emotion(emotion)
        session.add("assistant", reply)
        proactive.touch(session_id=session.id, emotion=emotion)
        sessions.persist(session)

        if _looks_important(msg) and MEM_ENABLED:
            try:
                memory.remember(f"主人说：{msg}", "from-chat")
            except Exception:
                pass

        yield (
            "data: "
            + json.dumps(
                {
                    "reply": reply,
                    "emotion": emotion,
                    "intensity": intensity,
                    "recalled": len(recalled),
                    "session_id": session.id,
                    "done": True,
                }
            )
            + "\n\n"
        )

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/care")
def care(session_id: str | None = None):
    """主动关心端点。前端轮询调用，返回关心消息或空。"""
    sid = session_id or "default"
    msg = proactive.check_and_notify(sid)
    if msg:
        return JSONResponse({"care": True, "message": msg, "session_id": sid})
    return JSONResponse({"care": False, "session_id": sid})


@app.get("/api/status")
def status():
    return {
        "name": nyx.name,
        "display": nyx.display,
        "title": nyx.title,
        "llm": "connected" if LLM_ON else "local-demo",
        "core": core.name,
        "core_health": core.health(),
        "memory": "universal-agent-memory" if MEM_ENABLED else "none",
        "persona": nyx.persona["name"],
        "mode": nyx.mode,
        "version": app.version,
        "tts": "edge-tts" if _tts_available() else "none",
        "clone": {
            "available": _gsv_available(),
            "profiles": _clone_list(),
        },
    }


# --- TTS：微软 edge-tts + GPT-SoVITS 克隆 ---
_TTS_VOICES = {
    "night": "zh-CN-XiaoxiaoNeural",
    "dawn": "zh-CN-XiaoyiNeural",
}

GSV_URL = "http://127.0.0.1:9880"
CLONE_DIR = (BASE / "train_data" / "clones").resolve()
CLONE_DIR.mkdir(parents=True, exist_ok=True)
CLONE_PROFILES: dict = {}


def _scan_clone_profiles():
    if not CLONE_DIR.is_dir():
        return
    for f in CLONE_DIR.iterdir():
        if f.suffix.lower() not in (".wav", ".mp3", ".flac", ".ogg"):
            continue
        txt = f.with_suffix(".txt")
        prompt_text = ""
        if txt.exists():
            try:
                prompt_text = txt.read_text(encoding="utf-8").strip()
            except Exception:
                pass
        CLONE_PROFILES[f.stem] = {"audio": str(f), "prompt_text": prompt_text}


_scan_clone_profiles()

TTS_VOICE_LIB = [
    {"id": "zh-CN-XiaoxiaoNeural", "name": "晓晓", "gender": "女", "style": "温暖细腻（小夜默认）"},
    {"id": "zh-CN-XiaoyiNeural", "name": "晓伊", "gender": "女", "style": "元气活力（晨晓默认）"},
    {"id": "zh-CN-YunxiNeural", "name": "云希", "gender": "男", "style": "阳光开朗"},
    {"id": "zh-CN-YunjianNeural", "name": "云健", "gender": "男", "style": "成熟沉稳"},
    {"id": "zh-CN-YunyangNeural", "name": "云扬", "gender": "男", "style": "新闻播报"},
    {"id": "zh-CN-YunxiaNeural", "name": "云夏", "gender": "男", "style": "小男孩童声"},
    {"id": "zh-CN-liaoning-XiaobeiNeural", "name": "晓北", "gender": "女", "style": "东北腔"},
    {"id": "zh-CN-shaanxi-XiaoniNeural", "name": "晓妮", "gender": "女", "style": "陕西腔"},
    {"id": "zh-HK-HiuGaaiNeural", "name": "曉佳", "gender": "女", "style": "粤语"},
    {"id": "zh-HK-HiuMaanNeural", "name": "曉曼", "gender": "女", "style": "粤语"},
    {"id": "zh-HK-WanLungNeural", "name": "雲龍", "gender": "男", "style": "粤语"},
    {"id": "zh-TW-HsiaoChenNeural", "name": "曉臻", "gender": "女", "style": "台湾腔"},
    {"id": "zh-TW-YunJheNeural", "name": "雲哲", "gender": "男", "style": "台湾腔"},
    {"id": "zh-TW-HsiaoYuNeural", "name": "曉雨", "gender": "女", "style": "台湾腔"},
]


def _clone_list() -> list:
    return [
        {"name": k, "prompt_text": v["prompt_text"], "audio": os.path.basename(v["audio"])}
        for k, v in CLONE_PROFILES.items()
    ]


def _gsv_available() -> bool:
    try:
        import urllib.request

        with urllib.request.urlopen(f"{GSV_URL}/", timeout=3) as r:
            return r.status < 500
    except Exception:
        return False


def _tts_available() -> bool:
    try:
        import edge_tts

        return True
    except Exception:
        return False


def _strip_md(text: str) -> str:
    import re

    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#*_>~]", "", text)
    return text.strip()[:500]


def _clone_tts(text: str, profile: dict) -> bytes:
    import urllib.request

    payload = json.dumps(
        {
            "text": text,
            "text_lang": "zh",
            "ref_audio_path": profile["audio"],
            "prompt_text": profile["prompt_text"],
            "prompt_lang": "zh",
            "text_split_method": "cut5",
            "batch_size": 1,
            "media_type": "wav",
            "streaming_mode": False,
        }
    ).encode()
    req = urllib.request.Request(
        f"{GSV_URL}/tts",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        if r.status != 200:
            raise RuntimeError(f"GSV tts failed: {r.status}")
        return r.read()


class TTSIn(BaseModel):
    text: str
    voice: str | None = None
    rate: str | None = "+0%"


@app.get("/api/voices")
def voices():
    return {"voices": TTS_VOICE_LIB, "clones": _clone_list(), "gsv": _gsv_available()}


@app.post("/api/tts")
async def tts(body: TTSIn):
    text = _strip_md(body.text or "")
    if not text:
        return JSONResponse({"error": "text 为空"}, status_code=400)
    voice = body.voice or "night"
    if voice.startswith("clone:"):
        name = voice[6:]
        profile = CLONE_PROFILES.get(name)
        if not profile:
            return JSONResponse({"error": f"克隆音色不存在: {name}"}, status_code=404)
        try:
            return Response(content=_clone_tts(text, profile), media_type="audio/wav")
        except Exception as e:
            return JSONResponse({"error": f"克隆合成失败: {e}"}, status_code=502)
    try:
        import edge_tts
    except Exception:
        return JSONResponse({"error": "edge-tts 未安装"}, status_code=501)
    vid = _TTS_VOICES.get(voice, voice)
    try:
        engine = edge_tts.Communicate(text, vid, rate=body.rate or "+0%")
        audio = bytearray()
        async for chunk in engine.stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
        if not audio:
            return JSONResponse({"error": "edge-tts 无输出"}, status_code=502)
        return Response(content=bytes(audio), media_type="audio/mpeg")
    except Exception as e:
        return JSONResponse({"error": f"edge-tts 失败: {e}"}, status_code=502)


@app.post("/api/clone")
async def clone_voice(request: Request):
    form = await request.form()
    name = (form.get("name") or "").strip()
    prompt_text = (form.get("prompt_text") or "").strip()
    audio = form.get("audio")
    if not name:
        return JSONResponse({"error": "缺少音色名字"}, status_code=400)
    if audio is None or not audio.filename:
        return JSONResponse({"error": "缺少参考音频"}, status_code=400)
    safe = "".join(c for c in name if c.isalnum() or c in "-_") or "clone"
    ext = os.path.splitext(audio.filename)[1].lower()
    if ext not in (".wav", ".mp3", ".flac", ".ogg"):
        ext = ".wav"
    path = CLONE_DIR / f"{safe}{ext}"
    data = await audio.read()
    if len(data) > 30 * 1024 * 1024:
        return JSONResponse({"error": "音频过大>30MB"}, status_code=400)
    path.write_bytes(data)
    if prompt_text:
        (CLONE_DIR / f"{safe}.txt").write_text(prompt_text, encoding="utf-8")
    CLONE_PROFILES[name] = {"audio": str(path), "prompt_text": prompt_text}
    return {"ok": True, "name": name, "path": path.name}


@app.delete("/api/clone")
async def clone_voice_delete(name: str = ""):
    profile = CLONE_PROFILES.pop(name, None)
    if profile:
        audio = profile.get("audio")
        if audio and os.path.exists(audio):
            try:
                os.remove(audio)
            except Exception:
                pass
        base = os.path.splitext(audio)[0] if audio else str(CLONE_DIR / name)
        txt = base + ".txt"
        if os.path.exists(txt):
            try:
                os.remove(txt)
            except Exception:
                pass
        return {"ok": True, "deleted": name}
    return {"ok": False, "error": "音色不存在"}


# --- 训练：环境检测 / 一键安装 / 一键训练 ---
@app.get("/api/env")
def env_detect():
    d = training.detect_env()
    d["stt"] = stt.get_status()["installed"]
    return d


# --- 语音输入（本地 STT 识别） ---
@app.get("/api/stt/status")
def stt_status():
    return stt.get_status()


@app.post("/api/stt/setup")
def stt_setup_start():
    return stt.install_start()


@app.post("/api/stt")
async def stt_recognize(request: Request):
    try:
        data = await request.body()
        if not data:
            return JSONResponse({"error": "缺少音频数据"}, status_code=400)
        text = stt.transcribe(data)
        return {"text": text}
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": "识别失败：%s" % e}, status_code=500)


@app.post("/api/setup")
def setup_start():
    return training.setup_start()


@app.get("/api/train/install-info")
def train_install_info():
    """GPT-SoVITS 个性化克隆选装说明（资源成本），供前端选装前提示用户。"""
    return training.install_info()


@app.get("/api/setup/status")
def setup_status():
    return training.setup_status()


@app.post("/api/train")
async def train_start(request: Request):
    form = await request.form()
    name = (form.get("name") or "").strip()
    audio = form.get("audio")
    if not name:
        return JSONResponse({"error": "缺少模型名称"}, status_code=400)
    if audio is None or not audio.filename:
        return JSONResponse({"error": "缺少录音文件"}, status_code=400)
    try:
        s1_epochs = int(form.get("s1_epochs") or 20)
        s2_epochs = int(form.get("s2_epochs") or 60)
    except Exception:
        s1_epochs, s2_epochs = 20, 60
    raw_work = BASE / "train_data" / "raw_work"
    raw_work.mkdir(parents=True, exist_ok=True)
    ext = os.path.splitext(audio.filename)[1].lower() or ".wav"
    if ext not in (".wav", ".mp3", ".m4a", ".flac", ".ogg"):
        ext = ".wav"
    safe = "".join(c for c in name if c.isalnum() or c in "-_") or "voice"
    path = raw_work / f"{safe}_{int(time.time())}{ext}"
    data = await audio.read()
    if len(data) > 200 * 1024 * 1024:
        return JSONResponse({"error": "录音过大>200MB"}, status_code=400)
    path.write_bytes(data)
    return training.train_start(name, str(path), s1_epochs, s2_epochs)


@app.get("/api/train/status")
def train_status():
    return training.train_status()


@app.get("/api/hermes/status")
def hermes_status():
    return hermes_setup.hermes_status()


@app.post("/api/hermes/deploy")
def hermes_deploy():
    return hermes_setup.deploy_hermes()


@app.get("/api/hermes/deploy/status")
def hermes_deploy_status():
    return hermes_setup.deploy_status()


def _looks_like_task(msg: str) -> bool:
    task_kw = [
        "帮我",
        "查",
        "算",
        "写",
        "改",
        "列出",
        "搜索",
        "打开",
        "整理",
        "生成",
        "下载",
        "运行",
        "建",
        "做",
        "翻译",
        "总结",
    ]
    return any(k in msg for k in task_kw)


def _looks_important(msg: str) -> bool:
    kw = ["我的电话", "记得", "生日", "喜欢", "讨厌", "重要", "约定", "地址"]
    return any(k in msg for k in kw)


if __name__ == "__main__":
    import uvicorn

    print(
        "🌙 Cyber Nyx v0.9 · "
        f"llm={'在线' if LLM_ON else '本地演示'} · "
        f"core={core.name} · "
        f"memory={'universal-agent-memory' if MEM_ENABLED else 'none'}"
    )

    if RUN_GUI:
        import socket
        import threading

        import webview

        def _free_port() -> int:
            s = socket.socket()
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
            s.close()
            return port

        port = _free_port()
        print(f"   内部服务 http://127.0.0.1:{port} （独立窗口模式）")
        threading.Thread(
            target=lambda: uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning"),
            daemon=True,
        ).start()
        webview.create_window(
            "Cyber Nyx · 小夜",
            f"http://127.0.0.1:{port}/",
            width=1080,
            height=720,
            min_size=(920, 640),
            background_color="#0d0f17",
        )
        webview.start()
        os._exit(0)
    else:
        print("   访问 http://127.0.0.1:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
