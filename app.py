#!/usr/bin/env python3
# Cyber Nyx · 三人共创：主创聆听花瓣雨 · 合创疯ˣ · 合创可怕食肉动物
"""Cyber Nyx — FastAPI 拟人助手服务（v0.7：历史恢复 + 记忆面板 + WS 推送）

启动：
    python app.py                                  # 演示模式
    NYX_HERMES_MODEL=... python app.py             # 启用 Hermes 内核
    NYX_STREAM=1 python app.py                     # 启用流式输出

访问： http://127.0.0.1:8000
"""

import asyncio
import json
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

import nyx_llm
from bridges.agent_core import NoCore
from bridges.hermes_adapter import HermesCore
from bridges.memory_bridge import MCPMemoryStore, NullMemoryStore
from emotion import infer_emotion as _infer_emotion
from nyx import NyxAgent
from proactive import ProactiveCare
from session import SessionManager

BASE = Path(__file__).resolve().parent

nyx = NyxAgent(str(BASE / "personas" / "nyx.json"))
LLM_ON = nyx_llm.available()

# --- 内核桥接（Hermes） ---
CORE_ENABLED = True
try:
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


app = FastAPI(title="Cyber Nyx", version="0.7.0", lifespan=lifespan)

SYSTEM_PROMPT = (
    f"你叫{nyx.display}（{nyx.title}），现在是深夜陪伴时刻。"
    f"你的人设：{'、'.join(nyx.persona.get('personality', []))}。"
    "说话温柔神秘，称呼对方为主人，句尾常用'呀/呢/~'。"
    "如果主人要求执行任务（查资料/写代码/改文件等），先简单确认，"
    "说明你会交给 Hermes 内核处理，再用你的语气回应。保持人设一致。"
    + nyx.get_mode_prompt()
)


class ChatIn(BaseModel):
    message: str
    format: str | None = "text"  # text | json | sse
    session_id: str | None = None  # 复用已有会话；不传则新建


@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE / "web" / "index.html").read_text(encoding="utf-8")


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

    前端连接：ws://host/ws?session_id=xxx
    服务端推送：{"type": "care", "message": "..."}
    """
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
    }


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
        "🌙 Cyber Nyx v0.6 · "
        f"llm={'在线' if LLM_ON else '本地演示'} · "
        f"core={core.name} · "
        f"memory={'universal-agent-memory' if MEM_ENABLED else 'none'}"
    )
    print("   访问 http://127.0.0.1:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
